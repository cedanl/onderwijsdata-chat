import contextlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from core.pseudoniem import VERSIE, pseudoniem

logger = logging.getLogger(__name__)

_MAX_CONVERSATIONS = 15
# A cursor before every conversation, so the first page needs no separate query.
_FIRST_PAGE = (2**62, "")
_USE_POSTGRES = bool(os.getenv("POSTGRES_URI"))
# Zoveel Postgres-verbindingen houdt het proces tegelijk open; een aanroep daarboven wacht op een vrije (#508).
_POOL_SIZE = int(os.getenv("POSTGRES_POOL_SIZE", "8"))


def _db_path() -> Path:
    configured = os.getenv("DATABASE_PATH")
    if configured:
        return Path(configured)
    azure_home = Path("/home")
    if azure_home.exists() and os.access(str(azure_home), os.W_OK):
        return azure_home / "onderwijsdata.db"
    return Path(__file__).parent.parent / "onderwijsdata.db"


class DatabaseStartFout(RuntimeError):
    """Een databasefout met een eigen tekst zonder host, gebruiker of wachtwoord; die tekst mag in het log (#1155)."""


# Wat een Postgres-fout van de driver zegt, als vaste tekst. De driver citeert host, poort, gebruiker en databasenaam,
# dus de fouttekst zelf komt niet in het log: alleen de eerste categorie die erin past.
_POSTGRES_OORZAKEN = (
    (r"connection refused", "verbinding geweigerd (poort dicht of de server draait niet)"),
    (r"timeout expired|timed out", "time-out bij het verbinden"),
    (
        r"could not translate host name|name or service not known|temporary failure in name resolution",
        "hostnaam onbekend",
    ),
    (
        r"password authentication failed|no password supplied|role \".*\" does not exist|no pg_hba\.conf entry",
        "authenticatie mislukt (gebruiker of wachtwoord) of toegang geweigerd",
    ),
    (r"database \".*\" does not exist", "database bestaat niet"),
    (r"invalid dsn|invalid connection option|missing \"=\" after|invalid uri", "ongeldige URI"),
    (
        r"server does not support ssl|ssl error|sslmode",
        "TLS-verbinding mislukt (sslmode=require, de server moet TLS bieden)",
    ),
)
# sqlite3 meldt een pad dat niet te openen of te beschrijven is zonder het pad te noemen.
_SQLITE_PAD_FOUTEN = ("unable to open database file", "readonly database", "disk i/o error")


def startfout_oorzaak(e: BaseException) -> str | None:
    """Een veilige oorzaak van een mislukte databasestart voor het log, of None als de fout geen herkenbare categorie heeft.

    Een beheerder met een pod in CrashLoopBackOff ziet zo wat er mis is zonder LOG_LEVEL=DEBUG (dat zet ook vraag- en
    antwoordtekst in het log), en de tekst van de driverfout, met host en databasenaam, blijft uit het log (#817, #1155).
    """
    if isinstance(e, DatabaseStartFout):
        return str(e)
    tekst = str(e).lower()
    if _USE_POSTGRES:
        return next((oorzaak for patroon, oorzaak in _POSTGRES_OORZAKEN if re.search(patroon, tekst)), None)
    if isinstance(e, sqlite3.Error) and any(f in tekst for f in _SQLITE_PAD_FOUTEN):
        return f"SQLite-pad niet te openen of niet schrijfbaar (of een map): {_db_path()}"
    return None


def _tls_verplicht(uri: str) -> dict:
    """`sslmode=require` als de URI zelf geen sslmode noemt (#683).

    De URI uit het secret noemt er geen, en de default van psycopg2 (`prefer`) valt stil terug op een
    onversleutelde verbinding. Test en playground praten al TLS 1.3 (gemeten met `pg_stat_ssl`), dus
    `require` breekt daar niets; een URI met een eigen sslmode (lokaal `sslmode=disable`) houdt die.
    """
    return {} if "sslmode=" in uri else {"sslmode": "require"}


# Wat een nieuwe Postgres-verbinding meekrijgt als de URI het niet zelf zet (#764). Zonder connect_timeout wachtte een
# aanroep naar een server die niet antwoordt op de TCP-time-out van het OS. Met de keepalives merkt de kernel een
# verbinding die in de pool ligt en waarvan de server weg is (failover), na een minuut op.
_VERBINDINGSOPTIES = {
    "connect_timeout": 5,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}


def _verbindingsopties(uri: str) -> dict:
    """De TLS-eis (#683) en de opties uit `_VERBINDINGSOPTIES` die de URI niet zelf noemt."""
    return {**_tls_verplicht(uri), **{k: v for k, v in _VERBINDINGSOPTIES.items() if f"{k}=" not in uri}}


def _connect() -> Any:
    if _USE_POSTGRES:
        try:
            import psycopg2
            import psycopg2.extras

            uri = os.getenv("POSTGRES_URI") or ""
            conn = psycopg2.connect(uri, **_verbindingsopties(uri))
            conn.autocommit = False
            return conn
        except ImportError:
            raise DatabaseStartFout("psycopg2 ontbreekt: installeer het met `uv sync --extra postgres`") from None
    else:
        conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        # Verwijderde en overschreven tekst gaat uit de pagina zelf, niet pas als er iets overheen komt (#1116).
        conn.execute("PRAGMA secure_delete=ON")
        return conn


class _Geleend:
    """Een verbinding uit de pool, voor één aanroep (#764).

    Na een herstart of failover van PostgreSQL zijn de vrije verbindingen in de pool dood, en psycopg2 merkt dat pas
    bij een statement. Tot `POSTGRES_POOL_SIZE` aanroepen faalden zo (500, een mislukte WebSocket-handshake, /ready
    rood). Faalt het eerste statement op een hergebruikte verbinding en is die daarna dicht (`closed` geldt ook voor
    een gebroken verbinding), dan komt er een nieuwe voor in de plaats en gaat dat statement opnieuw. Dat is veilig:
    vóór het eerste statement liep er in deze aanroep niets, dus er is niets half gecommit. Een SQL-fout laat de
    verbinding open en gaat zoals altijd naar de aanroeper, net als een fout op een verse verbinding (dan is de
    database echt weg) of op een later statement. Commit, rollback en cursor gaan naar de verbinding zelf.
    """

    def __init__(self, conn: Any, connect: Callable[[], Any], hergebruikt: bool) -> None:
        self.conn = conn
        self._connect = connect
        self._mag_opnieuw = hergebruikt

    def uitvoeren(self, sql: str, params: tuple) -> Any:
        mag_opnieuw, self._mag_opnieuw = self._mag_opnieuw, False
        try:
            return _uitvoeren(self.conn, sql, params)
        except Exception:
            if not (mag_opnieuw and self.conn.closed):
                raise
        logger.warning("Dode verbinding uit de pool vervangen (database herstart of failover?)")
        with contextlib.suppress(Exception):
            self.conn.close()
        self.conn = self._connect()
        return _uitvoeren(self.conn, sql, params)

    def __getattr__(self, naam: str) -> Any:
        return getattr(self.conn, naam)


class _Pool:
    """Hergebruikt Postgres-verbindingen over aanroepen heen (#508).

    Elke aanroep opende een eigen verbinding (TCP, TLS, authenticatie). Een verbinding gaat na
    gebruik met een rollback terug, zodat een leesactie geen transactie open laat staan; na een
    commit is die rollback niets. Een verbinding die niet meer werkt (server herstart, netwerk weg)
    gaat dicht in plaats van terug; een die al dood in de pool lag, vervangt `_Geleend` (#764).
    Meer dan `size` aanroepen tegelijk wachten op een vrije.
    """

    def __init__(self, connect: Callable[[], Any], size: int) -> None:
        self._connect = connect
        self._idle: list[Any] = []
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(size)

    @contextmanager
    def connection(self) -> Generator[_Geleend]:
        with self._slots:
            geleend = self._take()
            try:
                yield geleend
            finally:
                self._give_back(geleend.conn)

    def _take(self) -> _Geleend:
        with self._lock:
            if self._idle:
                return _Geleend(self._idle.pop(), self._connect, hergebruikt=True)
        return _Geleend(self._connect(), self._connect, hergebruikt=False)

    def _give_back(self, conn: Any) -> None:
        try:
            if conn.closed:
                return
            conn.rollback()
        except Exception:
            # Onbruikbaar: dicht en weg, de volgende aanroep maakt een nieuwe.
            with contextlib.suppress(Exception):
                conn.close()
            return
        with self._lock:
            self._idle.append(conn)

    def close_all(self) -> None:
        with self._lock:
            idle, self._idle = self._idle, []
        for conn in idle:
            with contextlib.suppress(Exception):
                conn.close()


_pool: _Pool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> _Pool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = _Pool(_connect, _POOL_SIZE)
        return _pool


@contextmanager
def _connection() -> Generator[Any]:
    """De verbinding voor één aanroep: uit de pool bij Postgres; bij SQLite nieuw, en daarna dicht.

    SQLite kent geen verbindingskosten die een pool waard zijn, en een verbinding per aanroep houdt
    de WAL-lezers en -schrijvers uit elkaar.
    """
    if _USE_POSTGRES:
        with _get_pool().connection() as conn:
            yield conn
        return
    conn = _connect()
    try:
        yield conn
    finally:
        if conn.total_changes:
            _leeg_wal(conn)
        conn.close()


def _leeg_wal(conn: sqlite3.Connection) -> None:
    """Na een wijziging het WAL-bestand leegmaken, zodat verwijderde tekst daar niet in achterblijft (#1116).

    `secure_delete` maakt de pagina in het databasebestand leeg, maar een eerdere versie van die pagina staat nog in
    het `-wal`-bestand tot het is leeggemaakt. Sluit de laatste verbinding, dan doet SQLite dat zelf; staat er nog een
    andere open, dan blijft de tekst in het WAL tot het wordt overschreven. Best effort en zonder te wachten
    (`busy_timeout=0`): een lezer die nog bezig is, houdt de aanroep niet op, en de volgende wijziging probeert het
    opnieuw.
    """
    with contextlib.suppress(sqlite3.Error):
        conn.execute("PRAGMA busy_timeout=0")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()


def close() -> None:
    """Sluit de open Postgres-verbindingen; bij het afsluiten van de app (server.py)."""
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is not None:
        pool.close_all()


def ping() -> None:
    """Eén rondje naar de database; een uitzondering betekent dat ze niet bereikbaar is (/ready)."""
    with _connection() as conn:
        _execute(conn, "SELECT 1").fetchone()


def _execute(conn: Any, sql: str, params: tuple = ()) -> Any:
    """Run a query with SQLite '?' placeholders, on either driver; on a pool connection via `_Geleend` (#764)."""
    if isinstance(conn, _Geleend):
        return conn.uitvoeren(sql, params)
    return _uitvoeren(conn, sql, params)


def _uitvoeren(conn: Any, sql: str, params: tuple = ()) -> Any:
    """Run a query with SQLite '?' placeholders, on either driver.

    sqlite3.Connection has a convenience .execute(); psycopg2 connections
    don't — they need an explicit cursor, and Postgres uses '%s' placeholders
    instead of '?'. RealDictCursor keeps rows dict-convertible like
    sqlite3.Row, so callers can use dict(row) either way.
    """
    if _USE_POSTGRES:
        import psycopg2.extras

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(sql.replace("?", "%s"), params)
        return cursor
    return conn.execute(sql, params)


def _thread(messages_json: str) -> list[tuple] | None:
    """A stored thread as comparable (role, content) pairs; None when unreadable."""
    try:
        messages = json.loads(messages_json)
    except (TypeError, ValueError):
        return None
    if not isinstance(messages, list) or not all(isinstance(m, dict) for m in messages):
        return None
    return [(m.get("role"), json.dumps(m.get("content"), sort_keys=True)) for m in messages]


def _is_legacy_id(conv_id: str) -> bool:
    """Pre-#69 ids were Date.now(): 13 digits. Since then a conversation gets a UUID."""
    return len(conv_id) == 13 and conv_id.isdigit()


def _dedupe_conversations(conn: Any) -> None:
    """Remove pre-#69 duplicate conversations: snapshots of one growing thread.

    Before #69 every save got a new id (#151), so one conversation was stored
    once per save, also when nothing had changed. A row is such a snapshot only
    when it has a legacy id and its messages, role and content, are the start of
    (or equal to) another row of the same user and title (case-insensitive).
    Anything less is no proof: a UUID row is never a snapshot, so two separate
    conversations with the same content both stay (#198); neither do two that
    open with the same question but got another answer (#178, #184), nor a row
    whose messages cannot be read. The richest row wins, tie-break on the newest
    timestamp.

    Databases that ran this migration before #184 used a looser rule (same user
    questions only); the schema_migrations marker keeps it from running again.
    """
    rows = [
        dict(r)
        for r in _execute(
            conn,
            "SELECT id, username, title, timestamp, messages FROM conversations",
        ).fetchall()
    ]
    groups: dict = {}
    for r in rows:
        r["thread"] = _thread(r["messages"])
        if r["thread"] is not None:
            groups.setdefault((r["username"].lower(), r["title"].lower()), []).append(r)

    doomed: list[tuple[str, str]] = []
    for group in groups.values():
        group.sort(key=lambda r: (len(r["thread"]), r["timestamp"]), reverse=True)
        kept: list[list[tuple]] = []
        for r in group:
            thread = r["thread"]
            if _is_legacy_id(str(r["id"])) and any(k[: len(thread)] == thread for k in kept):
                doomed.append((r["id"], r["username"]))
            else:
                kept.append(thread)

    for conv_id, username in doomed:
        _execute(conn, "DELETE FROM conversations WHERE id = ? AND username = ?", (conv_id, username))
    logger.info("dedupe: %d legacy duplicate conversations removed", len(doomed))


def _run_once(conn: Any, name: str, migration: Callable[[Any], None]) -> None:
    """Run a data migration exactly once per database, recorded in schema_migrations.

    Data migrations may delete rows, so unlike the idempotent schema checks in
    _migrate they must not re-run on every start-up against newer data (#178).
    Replicas starting together may both run it; the migration must therefore be
    idempotent, and the second marker insert is a no-op.
    """
    if _execute(conn, "SELECT 1 FROM schema_migrations WHERE name = ?", (name,)).fetchone():
        return
    migration(conn)
    _execute(conn, "INSERT INTO schema_migrations (name) VALUES (?) ON CONFLICT (name) DO NOTHING", (name,))
    conn.commit()


def _migrate(conn: Any) -> None:
    if _USE_POSTGRES:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='workbooks' AND column_name='dashboard_spec'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE workbooks ADD COLUMN dashboard_spec TEXT")
            conn.commit()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='workbooks' AND column_name='laatst_gebruikt'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE workbooks ADD COLUMN laatst_gebruikt BIGINT")
            conn.commit()

        cursor.execute("SELECT 1 FROM conversations WHERE timestamp > 1000000000000 LIMIT 1")
        if cursor.fetchone():
            cursor.execute(
                "UPDATE conversations SET timestamp = CAST(timestamp / 1000 AS INTEGER) WHERE timestamp > 1000000000000"
            )
            conn.commit()
        cursor.close()
    else:
        cursor = conn.execute("PRAGMA table_info(workbooks)")
        columns = {row[1] for row in cursor.fetchall()}
        if "dashboard_spec" not in columns:
            conn.execute("ALTER TABLE workbooks ADD COLUMN dashboard_spec TEXT")
            conn.commit()
        if "laatst_gebruikt" not in columns:
            conn.execute("ALTER TABLE workbooks ADD COLUMN laatst_gebruikt BIGINT")
            conn.commit()

        has_ms = conn.execute("SELECT 1 FROM conversations WHERE timestamp > 1000000000000 LIMIT 1").fetchone()
        if has_ms:
            conn.execute(
                "UPDATE conversations SET timestamp = CAST(timestamp / 1000 AS INTEGER) WHERE timestamp > 1000000000000"
            )
            conn.commit()

    _voeg_kolom_toe(conn, "feedback", "instelling", "TEXT NOT NULL DEFAULT ''")
    _voeg_kolom_toe(conn, "beurtbewijs", "bronnen", "TEXT NOT NULL DEFAULT '{}'")
    _voeg_kolom_toe(conn, "beurtbewijs", "figuren", "TEXT NOT NULL DEFAULT '[]'")
    _verwijder_kolom(conn, "beurtbewijs", "controle")
    _verwijder_kolom(conn, "beurtbewijs", "kaarten")
    _begin_bewaartermijn_werkboeken(conn)
    _run_once(conn, "160_dedupe_legacy_conversations", _dedupe_conversations)
    _verwijder_tabel(conn, "answer_feedback")
    _verwijder_kale_hashes_tokengebruik(conn)


def _voeg_kolom_toe(conn: Any, tabel: str, kolom: str, definitie: str) -> None:
    """Een kolom die later bij een bestaande tabel kwam; bestaande rijen krijgen de standaardwaarde uit `definitie`.

    Idempotent, dus veilig bij elke start: `instelling` bij feedback, `bronnen` (#987) en `figuren` (#993) bij
    beurtbewijs.
    """
    if _USE_POSTGRES:
        cursor = conn.cursor()
        cursor.execute(f"ALTER TABLE {tabel} ADD COLUMN IF NOT EXISTS {kolom} {definitie}")
        conn.commit()
        cursor.close()
    elif kolom not in {row[1] for row in conn.execute(f"PRAGMA table_info({tabel})")}:
        conn.execute(f"ALTER TABLE {tabel} ADD COLUMN {kolom} {definitie}")
        conn.commit()


def _verwijder_kolom(conn: Any, tabel: str, kolom: str) -> None:
    """Een kolom die niet meer bestaat, met haar waarden: `controle` bij beurtbewijs (#876, weg sinds #983, besluit 09-11)
    en `kaarten` bij beurtbewijs (#648, weg sinds #1044: niets las haar nog na #993).

    Idempotent, dus veilig bij elke start. PostgreSQL kent `DROP COLUMN IF EXISTS`; SQLite (vanaf 3.35) alleen
    `DROP COLUMN`, dus daar eerst kijken of de kolom er nog is.
    """
    if _USE_POSTGRES:
        cursor = conn.cursor()
        cursor.execute(f"ALTER TABLE {tabel} DROP COLUMN IF EXISTS {kolom}")
        conn.commit()
        cursor.close()
    elif kolom in {row[1] for row in conn.execute(f"PRAGMA table_info({tabel})")}:
        conn.execute(f"ALTER TABLE {tabel} DROP COLUMN {kolom}")
        conn.commit()


def _verwijder_tabel(conn: Any, tabel: str) -> None:
    """Een tabel die niet meer bestaat, met haar rijen: `answer_feedback`, de duimpjes per antwoord (#248, weg sinds
    #983, besluit 09-11).

    Idempotent, dus veilig bij elke start en bij twee replica's tegelijk: `IF EXISTS` kennen SQLite en PostgreSQL allebei.
    """
    _execute(conn, f"DROP TABLE IF EXISTS {tabel}")
    conn.commit()


def _verwijder_kale_hashes_tokengebruik(conn: Any) -> None:
    """Een rij van vóór #1112 draagt een kale sha256 van de accountnaam als sleutel: met één hash van een bekend
    e-mailadres is het account terug te vinden. Ze gaat weg; de rijen onder de HMAC (`h1:`, core/pseudoniem.py) blijven.

    De tellers van de lopende dag en maand beginnen daarmee eenmalig opnieuw: de oude sleutel is zonder de accountnamen
    niet naar de nieuwe om te zetten, en meenemen betekent de kale hash laten staan. Idempotent, dus veilig bij elke
    start en bij twee replica's tegelijk; een pod van de vorige versie die tijdens de uitrol nog onder de oude sleutel
    schrijft, laat rijen achter die na `TOKENGEBRUIK_DAGEN` verlopen.
    """
    _execute(conn, "DELETE FROM tokengebruik WHERE sleutel NOT LIKE ?", (f"{VERSIE}%",))
    conn.commit()


def _begin_bewaartermijn_werkboeken(conn: Any) -> None:
    """Een werkboek van vóór #485 krijgt nu als laatst gebruikt: wanneer het is geopend, is niet bekend.

    Zo begint zijn bewaartermijn (persistence/opschonen.py) bij deze migratie en verdwijnt er niets eerder dan
    de termijn na de invoering. Alleen lege waarden: upsert_workbook en werkboek_geopend vullen hem altijd.
    """
    _execute(conn, "UPDATE workbooks SET laatst_gebruikt = ? WHERE laatst_gebruikt IS NULL", (int(time.time()),))
    conn.commit()


# Eén rij per inzending; answers is JSON {vraag-id: antwoord} (zie core/feedback.py).
_FEEDBACK_TABLE = """
    CREATE TABLE IF NOT EXISTS feedback (
        id           TEXT PRIMARY KEY,
        username     TEXT NOT NULL,
        workbook_id  TEXT NOT NULL,
        report_type  TEXT NOT NULL,
        report_title TEXT NOT NULL DEFAULT '',
        answers      TEXT NOT NULL,
        created_at   TEXT NOT NULL,
        instelling   TEXT NOT NULL DEFAULT ''
    )
"""


# Algemene feedback via de Feedback-link (#600): één rij per bericht; soort is '' als de gebruiker er geen koos.
_ALGEMENE_FEEDBACK_TABLE = """
    CREATE TABLE IF NOT EXISTS algemene_feedback (
        id         TEXT PRIMARY KEY,
        username   TEXT NOT NULL,
        soort      TEXT NOT NULL DEFAULT '',
        tekst      TEXT NOT NULL,
        pagina     TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
"""


# Hoe een data-key van een gesprek ontstond, zodat hij een herstart overleeft (#472).
# recipe is JSON: {laad: [tool, args]} of {afgeleid_van, tool, args, stap}; nooit een script.
_DATA_RECIPES_TABLE = """
    CREATE TABLE IF NOT EXISTS data_recipes (
        username   TEXT NOT NULL,
        conv_id    TEXT NOT NULL,
        data_key   TEXT NOT NULL,
        recipe     TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (username, conv_id, data_key)
    )
"""
_DATA_RECIPES_INDEX = "CREATE INDEX IF NOT EXISTS idx_recipes_key ON data_recipes(username, data_key, created_at DESC)"


# Wat de server zelf vastlegde bij een afgerond antwoord, zodat een heropend gesprek hetzelfde rapport geeft als het
# levende (ADR-009, #875). De sleutel is de sha256 van de tekst die message_end als `content` stuurde: de tekst die de
# client terugstuurt, vindt zo zijn rij, ook als de index verschoof. lineage, rekenbewijs en bronnen zijn JSON; bronnen
# per key de bronregels van de geladen tabellen, zoals onder een antwoord (labels en tekst, geen data, #987). Een rij
# van vóór #987 heeft '{}'.
# figuren is de JSON-lijst van de stappen achter de figuren van de beurt (tool, argumenten, titel, keys; geen figuur-JSON),
# zodat het rapport een gekozen figuur opnieuw kan maken (#993). Een rij van vóór #993 heeft '[]'. De kolom kaarten (de
# kaartregels per data_key) is weg sinds #1044: een kaart uit het gesprek staat als figuur in figuren.
_BEURTBEWIJS_TABLE = """
    CREATE TABLE IF NOT EXISTS beurtbewijs (
        username    TEXT NOT NULL,
        conv_id     TEXT NOT NULL,
        tekst_hash  TEXT NOT NULL,
        lineage     TEXT NOT NULL,
        rekenbewijs TEXT NOT NULL,
        bronnen     TEXT NOT NULL DEFAULT '{}',
        figuren     TEXT NOT NULL DEFAULT '[]',
        created_at  TEXT NOT NULL,
        PRIMARY KEY (username, conv_id, tekst_hash)
    )
"""


# Bij uitloggen ingetrokken tokens (#479): alleen sha256(token), nooit het token, tot zijn exp.
# Daarna faalt het token toch al op zijn vervaltijd en kan de rij weg.
_REVOKED_TOKENS_TABLE = """
    CREATE TABLE IF NOT EXISTS revoked_tokens (
        token_hash TEXT    PRIMARY KEY,
        expires_at INTEGER NOT NULL
    )
"""
_REVOKED_TOKENS_INDEX = "CREATE INDEX IF NOT EXISTS idx_revoked_expires ON revoked_tokens(expires_at)"

# Alle tokens van een account ingetrokken, bij "verwijder al mijn gegevens" (#786): elk token met een sessiestart
# op of vóór revoked_before geldt niet meer, ook een ververst token. De server houdt geen lijst van uitgegeven tokens
# bij, dus zo per account. Alleen sha256(gebruikersnaam), zodat na het verwijderen de naam nergens meer staat; tot
# expires_at, daarna is elk van die tokens toch verlopen.
_REVOKED_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS revoked_users (
        user_hash      TEXT    PRIMARY KEY,
        revoked_before INTEGER NOT NULL,
        expires_at     INTEGER NOT NULL
    )
"""

# De SRAM-gebruikersinfo per account (naam, e-mail, organisatie, instelling; routes/auth.py), zodat /api/auth/user ze na
# een herlaad van de pagina terugvindt, ook op een andere pod (#984). Stond in het geheugen van de pod. Begrensd zoals
# daar (#487, privacy M4): een rij vervalt na SESSION_MAX (`expires_at`, seconden sinds epoch) en boven het maximum gaat
# de langst niet gebruikte eruit (`gebruikt`, ms sinds epoch). De sleutel is een pseudoniem van de accountnaam
# (core/pseudoniem.py, `oidc_sleutel`); de gegevens zelf zijn persoonsgegevens: ze staan in de export van "mijn
# gegevens" en gaan weg bij uitloggen, "verwijder al mijn gegevens" (in de transactie daarvan, #1209) en de opschoning
# (`verlopen_staat`).
_OIDC_GEBRUIKERS_TABLE = """
    CREATE TABLE IF NOT EXISTS oidc_gebruikers (
        sleutel    TEXT   PRIMARY KEY,
        gegevens   TEXT   NOT NULL,
        expires_at BIGINT NOT NULL,
        gebruikt   BIGINT NOT NULL
    )
"""
_OIDC_GEBRUIKERS_INDEX = "CREATE INDEX IF NOT EXISTS idx_oidc_gebruikt ON oidc_gebruikers(gebruikt)"

# De instelling "Geavanceerd" per account (#1269): de gebruiker kiest haar zelf in Instellingen, op elk apparaat
# dezelfde. Nooit afgeleid uit rol, instelling of functie. `aan` is 0 of 1, `gewijzigd` ms sinds epoch. De sleutel is
# een pseudoniem van de accountnaam (`geavanceerd_sleutel`), zoals bij `oidc_gebruikers`; geen rij betekent uit. Een rij
# met 0 blijft staan: zo zet de pilotlijst (`GEAVANCEERD_PILOT`) bij een volgende login niets terug. De rij staat in de
# export van "mijn gegevens" en gaat weg bij "verwijder al mijn gegevens"; een eigen bewaartermijn heeft ze niet.
_GEAVANCEERD_TABLE = """
    CREATE TABLE IF NOT EXISTS geavanceerd (
        sleutel   TEXT    PRIMARY KEY,
        aan       INTEGER NOT NULL,
        gewijzigd BIGINT  NOT NULL
    )
"""


# Tellers van de limieten (core/rate_limit.py), gedeeld door alle pods (#984). Eén rij per meegetelde poging; `verloopt`
# (ms sinds epoch) is het moment waarop die poging uit het venster valt. De sleutel staat er alleen als HMAC met een
# servergeheim (core/pseudoniem.py, #1117): de gebruikersnaam of het adres uit de limiet staat zo nergens leesbaar of
# terug te rekenen, en "verwijder al mijn gegevens" hoeft er niets mee.
_RATE_LIMIT_TABLE = """
    CREATE TABLE IF NOT EXISTS rate_limit_hits (
        bucket   TEXT   NOT NULL,
        sleutel  TEXT   NOT NULL,
        verloopt BIGINT NOT NULL
    )
"""
_RATE_LIMIT_INDEX = "CREATE INDEX IF NOT EXISTS idx_rate_limit ON rate_limit_hits(bucket, sleutel, verloopt)"

# Tokengebruik per gebruiker per dag (#678, core/tokenbudget.py), in invoertoken-equivalenten. De sleutel is een HMAC
# van de gebruikersnaam met een servergeheim (core/pseudoniem.py, #1112); `dag` is jjjj-mm-dd (UTC). Rijen ouder dan TOKENGEBRUIK_DAGEN gaan weg
# bij het opruimen: genoeg voor deze en de vorige maand.
_TOKENGEBRUIK_TABLE = """
    CREATE TABLE IF NOT EXISTS tokengebruik (
        sleutel  TEXT   NOT NULL,
        dag      TEXT   NOT NULL,
        eenheden BIGINT NOT NULL,
        PRIMARY KEY (sleutel, dag)
    )
"""
TOKENGEBRUIK_DAGEN = 62


_CONVERSATIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS conversations (
        id        TEXT    NOT NULL,
        username  TEXT    NOT NULL,
        title     TEXT    NOT NULL,
        timestamp INTEGER NOT NULL,
        messages  TEXT    NOT NULL,
        PRIMARY KEY (id, username)
    )
"""
_CONVERSATIONS_INDEX = "CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(username, timestamp DESC)"

_WORKBOOKS_TABLE = """
    CREATE TABLE IF NOT EXISTS workbooks (
        id             TEXT NOT NULL,
        username       TEXT NOT NULL,
        title          TEXT NOT NULL,
        description    TEXT NOT NULL DEFAULT '',
        messages       TEXT,
        figures        TEXT,
        instelling     TEXT,
        html_content   TEXT,
        dashboard_spec TEXT,
        created_at     TEXT NOT NULL,
        laatst_gebruikt BIGINT,
        PRIMARY KEY (id, username)
    )
"""
_WORKBOOKS_INDEX = "CREATE INDEX IF NOT EXISTS idx_wb_user ON workbooks(username, created_at DESC)"

_SCHEMA_MIGRATIONS_TABLE = "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)"

# Het hele schema, voor Postgres en SQLite dezelfde DDL (#825); _migrate werkt een bestaande database daarna bij.
_SCHEMA = (
    _CONVERSATIONS_TABLE,
    _CONVERSATIONS_INDEX,
    _WORKBOOKS_TABLE,
    _WORKBOOKS_INDEX,
    _FEEDBACK_TABLE,
    _ALGEMENE_FEEDBACK_TABLE,
    _DATA_RECIPES_TABLE,
    _DATA_RECIPES_INDEX,
    _BEURTBEWIJS_TABLE,
    _REVOKED_TOKENS_TABLE,
    _REVOKED_TOKENS_INDEX,
    _REVOKED_USERS_TABLE,
    _OIDC_GEBRUIKERS_TABLE,
    _OIDC_GEBRUIKERS_INDEX,
    _GEAVANCEERD_TABLE,
    _RATE_LIMIT_TABLE,
    _RATE_LIMIT_INDEX,
    _TOKENGEBRUIK_TABLE,
    _SCHEMA_MIGRATIONS_TABLE,
)


# Het slot waaronder één pod tegelijk het schema aanmaakt en migreert (#984). Willekeurig, alleen vast.
_MIGRATIE_SLOT = 0x6F6E64657277696A
_MIGRATIE_WACHT_S = 120  # langer dan een migratie hoort te duren; daarna is er iets mis en moet de start falen
_MIGRATIE_POLL_S = 0.5


def _slotvraag(conn: Any, sql: str) -> Any:
    """Eén waarde uit een slot-query, met een gewone cursor (de eerste kolom, geen dict)."""
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (_MIGRATIE_SLOT,))
        return cursor.fetchone()[0]
    finally:
        cursor.close()


@contextmanager
def _migratielock(conn: Any) -> Generator[None]:
    """Op Postgres één pod tegelijk door het schema en de migraties (#984); op SQLite (één proces) niets.

    Twee pods die samen starten (uitrol, node-drain) deden `CREATE TABLE IF NOT EXISTS` en `ALTER TABLE` door elkaar:
    de ene kon op "tabel bestaat al" of een dubbele kolom stuiten en crashen. Een sessie-advisory-lock laat de tweede
    wachten; die vindt daarna alles klaar en doet niets meer. Sessie-niveau, want de migraties committen zelf
    tussendoor, wat een transactie-lock zou loslaten. Valt de verbinding weg, dan geeft Postgres het slot zelf vrij.
    """
    if not _USE_POSTGRES:
        yield
        return
    einde = time.monotonic() + _MIGRATIE_WACHT_S
    while not _slotvraag(conn, "SELECT pg_try_advisory_lock(%s)"):
        if time.monotonic() >= einde:
            raise DatabaseStartFout(
                f"Geen migratieslot binnen {_MIGRATIE_WACHT_S}s: draait een andere pod nog een migratie?"
            )
        time.sleep(_MIGRATIE_POLL_S)
    try:
        yield
    finally:
        # Na een fout staat de transactie afgebroken en weigert elk statement; het slot loslaten kan dan pas na een rollback.
        try:
            conn.rollback()
            _slotvraag(conn, "SELECT pg_advisory_unlock(%s)")
            conn.commit()
        except Exception as exc:
            # Een verbinding die het slot houdt, gaat terug de pool in en houdt de andere pods tegen: dicht, dan geeft
            # Postgres het slot zelf vrij.
            logger.warning("Migratieslot loslaten mislukt (%s): verbinding gesloten", type(exc).__name__)
            with contextlib.suppress(Exception):
                conn.close()


def init_db() -> None:
    with _connection() as conn, _migratielock(conn):
        if _USE_POSTGRES:
            cursor = conn.cursor()
            for ddl in _SCHEMA:
                cursor.execute(ddl)
            conn.commit()
            cursor.close()
        else:
            for ddl in _SCHEMA:
                conn.execute(ddl)

        _migrate(conn)
        purge_expired_revocations(conn)
        conn.commit()


def verlopen_staat(nu: datetime) -> dict[str, tuple[str, tuple]]:
    """Per tabel met korte staat wat op `nu` verlopen is, als WHERE met parameters (#1113).

    Ingetrokken sessies en accounts verlopen met hun token (verificatie weigert zo'n token zelf), SRAM-gebruikersinfo
    (`oidc_gebruikers`) na SESSION_MAX, een poging in `rate_limit_hits` als zij uit het venster van de limiet valt, en
    tokengebruik na `TOKENGEBRUIK_DAGEN`. Eén plek voor
    twee gebruikers: `purge_expired_revocations` bij de start en bij intrekken, en de nachtelijke opschoning
    (persistence/opschonen.py), die ook een pod bereikt die weken niet herstart.
    """
    seconden = int(nu.timestamp())
    grens = (nu.astimezone(UTC).date() - timedelta(days=TOKENGEBRUIK_DAGEN)).isoformat()
    return {
        "revoked_tokens": ("expires_at < ?", (seconden,)),
        "revoked_users": ("expires_at < ?", (seconden,)),
        "oidc_gebruikers": ("expires_at <= ?", (seconden,)),
        "rate_limit_hits": ("verloopt <= ?", (seconden * 1000,)),
        "tokengebruik": ("dag < ?", (grens,)),
    }


def purge_expired_revocations(conn: Any) -> None:
    """Drop the short-lived state that has expired: denylist rows, rate-limit attempts and old token usage."""
    for tabel, (waar, params) in verlopen_staat(datetime.now(UTC)).items():
        _execute(conn, f"DELETE FROM {tabel} WHERE {waar}", params)


def revoke_token_hash(token_hash: str, expires_at: int) -> None:
    """Put a token hash on the denylist until expires_at; revoking twice is a no-op."""
    with _connection() as conn:
        _execute(
            conn,
            "INSERT INTO revoked_tokens (token_hash, expires_at) VALUES (?, ?) ON CONFLICT (token_hash) DO NOTHING",
            (token_hash, expires_at),
        )
        purge_expired_revocations(conn)
        conn.commit()


def revoke_user_tokens(user_hash: str, revoked_before: int, expires_at: int) -> None:
    """Revoke every token of this account whose session started at or before revoked_before (#786).

    A later revocation replaces an earlier one: it covers at least as many tokens and lasts as long.
    """
    with _connection() as conn:
        _execute(
            conn,
            "INSERT INTO revoked_users (user_hash, revoked_before, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT (user_hash) DO UPDATE SET revoked_before = excluded.revoked_before, "
            "expires_at = excluded.expires_at",
            (user_hash, revoked_before, expires_at),
        )
        purge_expired_revocations(conn)
        conn.commit()


def is_token_revoked(token_hash: str, user_hash: str, start: int) -> bool:
    """Revoked on its own (logout) or with all tokens of its account (#786); one query for both."""
    with _connection() as conn:
        row = _execute(
            conn,
            "SELECT 1 FROM revoked_tokens WHERE token_hash = ? "
            "UNION ALL SELECT 1 FROM revoked_users WHERE user_hash = ? AND revoked_before >= ?",
            (token_hash, user_hash, start),
        ).fetchone()
    return row is not None


# Het domein van het pseudoniem in `oidc_gebruikers` (core/pseudoniem.py): een andere sleutel dan in `tokengebruik`.
OIDC_PSEUDONIEM_DOMEIN = "oidc_gebruiker"


def oidc_sleutel(gebruiker: str) -> str:
    """De sleutel van `gebruiker` in `oidc_gebruikers`: een pseudoniem van de accountnaam, niet de naam zelf (#984).

    Eén afleiding voor de login (routes/auth.py), de export en het verwijderen (#1209), zodat die drie dezelfde rij
    vinden; de persistence-laag hoeft daarvoor routes.auth niet te importeren.
    """
    return pseudoniem(OIDC_PSEUDONIEM_DOMEIN, gebruiker)


def oidc_gebruiker_bewaar(sleutel: str, gegevens: str, expires_at: int, nu: float, maximum: int) -> None:
    """Bewaar (of vervang) de SRAM-gebruikersinfo onder `sleutel` tot `expires_at` (#984).

    In dezelfde transactie gaan verlopen rijen weg en, boven `maximum`, de langst niet gebruikte (#487).
    """
    with _connection() as conn:
        _execute(conn, "DELETE FROM oidc_gebruikers WHERE expires_at <= ?", (int(nu),))
        _execute(
            conn,
            "INSERT INTO oidc_gebruikers (sleutel, gegevens, expires_at, gebruikt) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (sleutel) DO UPDATE SET gegevens = excluded.gegevens, expires_at = excluded.expires_at, "
            "gebruikt = excluded.gebruikt",
            (sleutel, gegevens, expires_at, int(nu * 1000)),
        )
        _execute(
            conn,
            "DELETE FROM oidc_gebruikers WHERE sleutel NOT IN "
            "(SELECT sleutel FROM oidc_gebruikers ORDER BY gebruikt DESC, sleutel DESC LIMIT ?)",
            (maximum,),
        )
        conn.commit()


def oidc_gebruiker_lees(sleutel: str, nu: float) -> str | None:
    """De bewaarde gegevens onder `sleutel`, of None als ze er niet zijn of verlopen (dan gaat de rij weg).

    Lezen houdt de rij jong: `gebruikt` gaat naar `nu`, zodat het maximum de langst niet gebruikte eruit zet (#487).
    """
    with _connection() as conn:
        rij = _execute(
            conn, "SELECT gegevens, expires_at FROM oidc_gebruikers WHERE sleutel = ?", (sleutel,)
        ).fetchone()
        if rij is None:
            return None
        if rij["expires_at"] <= nu:
            _execute(conn, "DELETE FROM oidc_gebruikers WHERE sleutel = ?", (sleutel,))
            conn.commit()
            return None
        _execute(conn, "UPDATE oidc_gebruikers SET gebruikt = ? WHERE sleutel = ?", (int(nu * 1000), sleutel))
        conn.commit()
    return rij["gegevens"]


def oidc_gebruiker_vergeet(sleutel: str) -> None:
    """De SRAM-gebruikersinfo onder `sleutel` weg, bij uitloggen. "Verwijder al mijn gegevens" wist haar in zijn eigen
    transactie (persistence/verwijderen.py, #1209)."""
    with _connection() as conn:
        _execute(conn, "DELETE FROM oidc_gebruikers WHERE sleutel = ?", (sleutel,))
        conn.commit()


# Het domein van het pseudoniem in `geavanceerd` (#1269): een andere sleutel dan in `oidc_gebruikers` en `tokengebruik`.
GEAVANCEERD_PSEUDONIEM_DOMEIN = "geavanceerd"


def geavanceerd_sleutel(gebruiker: str) -> str:
    """De sleutel van `gebruiker` in `geavanceerd`; één afleiding voor de route, de login, de export en het verwijderen."""
    return pseudoniem(GEAVANCEERD_PSEUDONIEM_DOMEIN, gebruiker)


def geavanceerd_lees(sleutel: str) -> bool | None:
    """De bewaarde keuze onder `sleutel`: True of False, of None als er nog geen is."""
    with _connection() as conn:
        rij = _execute(conn, "SELECT aan FROM geavanceerd WHERE sleutel = ?", (sleutel,)).fetchone()
    return None if rij is None else bool(rij["aan"])


def geavanceerd_zet(sleutel: str, aan: bool, nu: float) -> None:
    """Bewaar de keuze van de gebruiker zelf; een bestaande keuze wordt vervangen."""
    with _connection() as conn:
        _execute(
            conn,
            "INSERT INTO geavanceerd (sleutel, aan, gewijzigd) VALUES (?, ?, ?) "
            "ON CONFLICT (sleutel) DO UPDATE SET aan = excluded.aan, gewijzigd = excluded.gewijzigd",
            (sleutel, int(aan), int(nu * 1000)),
        )
        conn.commit()


def geavanceerd_zet_als_nieuw(sleutel: str, aan: bool, nu: float) -> bool:
    """Bewaar `aan` alleen als er nog geen keuze is (de pilotlijst bij de eerste login); True als er een rij bij kwam.

    Atomisch, ook met twee pods tegelijk: een keuze die de gebruiker al maakte, blijft staan.
    """
    with _connection() as conn:
        cursor = _execute(
            conn,
            "INSERT INTO geavanceerd (sleutel, aan, gewijzigd) VALUES (?, ?, ?) ON CONFLICT (sleutel) DO NOTHING",
            (sleutel, int(aan), int(nu * 1000)),
        )
        nieuw = cursor.rowcount == 1
        conn.commit()
    return nieuw


def deelt_staat() -> bool:
    """Waar de database de staat van meerdere pods deelt: Postgres. SQLite is één proces, daar telt het geheugen (#984)."""
    return _USE_POSTGRES


def tokengebruik_sleutel(gebruiker: str) -> str:
    """De sleutel van `gebruiker` in `tokengebruik`: dezelfde als bij het boeken (`core.tokenbudget._sleutel`), zodat
    export en verwijderen (#1074) precies de rijen van dit account vinden. Pas bij de aanroep geïmporteerd: tokenbudget
    haalt de agent binnen, en die de persistence-laag."""
    from core.tokenbudget import _sleutel

    return _sleutel(gebruiker)


def tokengebruik_boek(sleutel: str, dag: str, eenheden: int) -> None:
    """Tel `eenheden` op bij het gebruik van `sleutel` op `dag` (#678); atomisch, ook met twee pods tegelijk."""
    with _connection() as conn:
        _execute(
            conn,
            "INSERT INTO tokengebruik (sleutel, dag, eenheden) VALUES (?, ?, ?) "
            "ON CONFLICT (sleutel, dag) DO UPDATE SET eenheden = tokengebruik.eenheden + excluded.eenheden",
            (sleutel, dag, eenheden),
        )
        conn.commit()


def tokengebruik_stand(sleutel: str, dag: str, maand_vanaf: str) -> tuple[int, int]:
    """(gebruik op `dag`, gebruik van `maand_vanaf` tot en met `dag`) voor `sleutel` (#678)."""
    with _connection() as conn:
        rij = _execute(
            conn,
            "SELECT COALESCE(SUM(CASE WHEN dag = ? THEN eenheden ELSE 0 END), 0) AS vandaag, "
            "COALESCE(SUM(eenheden), 0) AS maand FROM tokengebruik WHERE sleutel = ? AND dag >= ? AND dag <= ?",
            (dag, sleutel, maand_vanaf, dag),
        ).fetchone()
    return int(rij["vandaag"]), int(rij["maand"])


def rate_limit_poging(bucket: str, sleutel: str, max_aantal: int, venster_ms: int, *, tel: bool = True) -> int | None:
    """Telt een poging mee als er ruimte is en geeft dan None; anders na hoeveel ms er weer ruimte is (#984).

    `sleutel` is al gehasht (core/rate_limit.py). Met `tel=False` kijkt het alleen. Het opruimen van verlopen pogingen,
    tellen en bijschrijven gaat in één transactie. Op Postgres houdt een advisory lock per bucket+sleutel twee pods die
    tegelijk dezelfde sleutel tellen uit elkaar; op SQLite neemt de DELETE de schrijfvergrendeling.
    """
    nu = int(time.time() * 1000)
    with _connection() as conn:
        if _USE_POSTGRES:
            _execute(conn, "SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", (f"{bucket}:{sleutel}",)).fetchone()
        _execute(
            conn,
            "DELETE FROM rate_limit_hits WHERE bucket = ? AND sleutel = ? AND verloopt <= ?",
            (bucket, sleutel, nu),
        )
        rij = _execute(
            conn,
            "SELECT COUNT(*) AS n, MIN(verloopt) AS eerste FROM rate_limit_hits WHERE bucket = ? AND sleutel = ?",
            (bucket, sleutel),
        ).fetchone()
        if rij["n"] >= max_aantal:
            conn.commit()
            return max(1, rij["eerste"] - nu)
        if tel:
            _execute(
                conn,
                "INSERT INTO rate_limit_hits (bucket, sleutel, verloopt) VALUES (?, ?, ?)",
                (bucket, sleutel, nu + venster_ms),
            )
        conn.commit()
    return None


def rate_limit_opruimen(bucket: str) -> None:
    """Alle verlopen pogingen van deze bucket weg, ook van sleutels die niet meer terugkomen (#984)."""
    with _connection() as conn:
        _execute(
            conn, "DELETE FROM rate_limit_hits WHERE bucket = ? AND verloopt <= ?", (bucket, int(time.time() * 1000))
        )
        conn.commit()


def list_conversations(
    username: str, before: tuple[int, str] | None = None, limit: int = _MAX_CONVERSATIONS
) -> list[dict]:
    """Newest first, one page at a time (#123): id, title and timestamp, without the messages (#509).

    The next page starts after `before`, the (timestamp, id) of the last
    conversation on the previous one; id breaks ties between equal timestamps.
    The sidebar needs no messages; those come per conversation from get_conversation.
    """
    ts, conv_id = before or _FIRST_PAGE
    with _connection() as conn:
        rows = _execute(
            conn,
            "SELECT id, title, timestamp FROM conversations "
            "WHERE username = ? AND (timestamp < ? OR (timestamp = ? AND id < ?)) "
            "ORDER BY timestamp DESC, id DESC LIMIT ?",
            (username, ts, ts, conv_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(username: str, conv_id: str) -> dict | None:
    """One own conversation with its messages parsed; None when this user has no such conversation."""
    with _connection() as conn:
        row = _execute(
            conn,
            "SELECT id, title, timestamp, messages FROM conversations WHERE id = ? AND username = ?",
            (conv_id, username),
        ).fetchone()
    if row is None:
        return None
    conversation = dict(row)
    conversation["messages"] = json.loads(conversation["messages"])
    return conversation


def _summary(row: dict) -> dict:
    """What the list carries of a conversation: never its messages (#509)."""
    return {"id": row["id"], "title": row["title"], "timestamp": row["timestamp"]}


def search_conversations(username: str, query: str, limit: int = _MAX_CONVERSATIONS) -> list[dict]:
    """Conversations whose title or message text contains `query`, newest first (#124).

    Matched in Python on the parsed messages, not with LIKE on the stored JSON:
    that JSON escapes non-ASCII ("é" is stored as "\\u00e9") and would
    match its own keys ("role", "content"). The hits carry no messages (#509).
    """
    needle = query.casefold()
    with _connection() as conn:
        rows = _execute(
            conn,
            "SELECT id, title, timestamp, messages FROM conversations WHERE username = ? ORDER BY timestamp DESC, id DESC",
            (username,),
        ).fetchall()
    hits = [_summary(row) for r in rows if _contains(row := dict(r), needle)]
    return hits[:limit]


def _contains(row: dict, needle: str) -> bool:
    if needle in (row.get("title") or "").casefold():
        return True
    try:
        messages = json.loads(row.get("messages") or "[]")
    except ValueError:
        return False
    return any(
        isinstance(m, dict) and isinstance(m.get("content"), str) and needle in m["content"].casefold()
        for m in messages
    )


def _normalize_ts(timestamp: float) -> int:
    """Milliseconden naar seconden, en nooit later dan nu.

    De tijd komt uit de browser en is de laatste activiteit van het gesprek: met een klok in de toekomst zou het
    gesprek buiten de bewaartermijn vallen (#485).
    """
    seconds = int(timestamp) // 1000 if timestamp > 1e12 else int(timestamp)
    return min(seconds, int(time.time()))


class GesprekEldersGewijzigd(Exception):
    """De opslag zou vragen weggooien die al bewaard zijn: een ander tabblad of apparaat schreef ertussen (#760)."""


def _vragen(messages: list) -> list:
    return [m.get("content") for m in messages if isinstance(m, dict) and m.get("role") == "user"]


def upsert_conversation(username: str, conv_id: str, title: str, timestamp: float, messages: list[dict]) -> None:
    """Bewaar een gesprek; de titel alleen bij het aanmaken.

    Elke opslag na een antwoord stuurt de automatische titel uit de eerste vraag mee. Een bestaand gesprek houdt
    zijn titel, zodat een hernoeming (rename_conversation) blijft staan, ook vanaf een ander apparaat (#757).

    De nieuwe versie moet beginnen met de vragen die al bewaard zijn, anders `GesprekEldersGewijzigd` (#760): twee
    tabbladen met hetzelfde gesprek overschreven elkaars beurten zonder melding. Alleen de vragen tellen; een antwoord
    mag veranderen (een afgebroken antwoord dat later volledig is, #548/#635). Het schrijven slaagt alleen op de
    versie die gelezen is, zodat een schrijver die er tussen lezen en schrijven doorheen komt ook niet verloren gaat.
    In Python en zonder databasespecifieke JSON-functies, zodat SQLite en PostgreSQL hetzelfde doen.
    """
    nieuw = json.dumps(messages)
    with _connection() as conn:
        rij = _execute(
            conn,
            "SELECT messages FROM conversations WHERE id = ? AND username = ?",
            (conv_id, username),
        ).fetchone()
        if rij is None:
            cursor = _execute(
                conn,
                "INSERT INTO conversations (id, username, title, timestamp, messages) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT (id, username) DO NOTHING",
                (conv_id, username, title, _normalize_ts(timestamp), nieuw),
            )
        else:
            bewaard = rij["messages"]
            vragen = _vragen(json.loads(bewaard))
            if _vragen(messages)[: len(vragen)] != vragen:
                raise GesprekEldersGewijzigd(conv_id)
            cursor = _execute(
                conn,
                "UPDATE conversations SET timestamp = ?, messages = ? WHERE id = ? AND username = ? AND messages = ?",
                (_normalize_ts(timestamp), nieuw, conv_id, username, bewaard),
            )
        if cursor.rowcount == 0:
            raise GesprekEldersGewijzigd(conv_id)
        conn.commit()


def rename_conversation(username: str, conv_id: str, title: str) -> bool:
    """Update only the title. Returns False when the user has no such conversation."""
    with _connection() as conn:
        cursor = _execute(
            conn,
            "UPDATE conversations SET title = ? WHERE id = ? AND username = ?",
            (title, conv_id, username),
        )
        conn.commit()
    return cursor.rowcount > 0


def delete_conversation(username: str, conv_id: str) -> None:
    with _connection() as conn:
        _execute(
            conn,
            "DELETE FROM conversations WHERE id = ? AND username = ?",
            (conv_id, username),
        )
        ruim_gesprek_op(conn, username, conv_id)
        conn.commit()


def ruim_gesprek_op(conn: Any, username: str, conv_id: str) -> dict[str, int]:
    """Wat bij een verwijderd gesprek hoort, in de transactie van `conn`: recepten en bewijsrijen weg (#875).

    Voor het verwijderen door de gebruiker en voor de opschoning na de bewaartermijn (persistence/opschonen.py).
    Geeft per tabel het aantal verwijderde rijen.
    """
    return {
        tabel: _execute(conn, f"DELETE FROM {tabel} WHERE username = ? AND conv_id = ?", (username, conv_id)).rowcount
        for tabel in ("data_recipes", "beurtbewijs")
    }


def save_recipes(username: str, conv_id: str, recipes: dict[str, dict]) -> None:
    """Bewaar per data-key van een gesprek zijn recept; een bestaand recept wordt bijgewerkt (#472)."""
    if not recipes:
        return
    now = datetime.now(UTC).isoformat(timespec="seconds")
    with _connection() as conn:
        for key, recipe in recipes.items():
            _execute(
                conn,
                "INSERT INTO data_recipes (username, conv_id, data_key, recipe, created_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (username, conv_id, data_key) DO UPDATE SET recipe=excluded.recipe",
                (username, conv_id, key, json.dumps(recipe, ensure_ascii=False, default=str), now),
            )
        conn.commit()


def recipes_for(username: str, conv_id: str) -> dict[str, dict]:
    """De recepten van een eigen gesprek, per data-key."""
    with _connection() as conn:
        rows = _execute(
            conn,
            "SELECT data_key, recipe FROM data_recipes WHERE username = ? AND conv_id = ?",
            (username, conv_id),
        ).fetchall()
    return {r["data_key"]: json.loads(r["recipe"]) for r in rows}


def beurtbewijs_voor(username: str, conv_id: str) -> dict[str, dict]:
    """De bewijsrijen van een eigen gesprek, per tekst-hash (ADR-009, #875); een onleesbare rij slaat ze over."""
    with _connection() as conn:
        rows = _execute(
            conn,
            "SELECT tekst_hash, lineage, rekenbewijs, bronnen, figuren, created_at FROM beurtbewijs "
            "WHERE username = ? AND conv_id = ?",
            (username, conv_id),
        ).fetchall()
    uit: dict[str, dict] = {}
    for r in rows:
        try:
            uit[r["tekst_hash"]] = {
                "lineage": json.loads(r["lineage"]),
                "rekenbewijs": json.loads(r["rekenbewijs"]),
                "bronnen": json.loads(r["bronnen"]),
                "figuren": json.loads(r["figuren"]),
                "created_at": r["created_at"],
            }
        except ValueError:
            continue
    return uit


def beurtbewijs_hashes(username: str, conv_id: str) -> list[str]:
    """Alleen de tekst-hashes van de bewijsrijen van een eigen gesprek, zonder hun inhoud te lezen."""
    with _connection() as conn:
        rows = _execute(
            conn,
            "SELECT tekst_hash FROM beurtbewijs WHERE username = ? AND conv_id = ?",
            (username, conv_id),
        ).fetchall()
    return [r["tekst_hash"] for r in rows]


def save_beurtbewijs(username: str, conv_id: str, rijen: dict[str, dict]) -> None:
    """Bewaar per tekst-hash zijn bewijsrij; een bestaande rij wordt bijgewerkt en houdt haar `created_at`."""
    if not rijen:
        return
    with _connection() as conn:
        for tekst_hash, rij in rijen.items():
            _execute(
                conn,
                "INSERT INTO beurtbewijs "
                "(username, conv_id, tekst_hash, lineage, rekenbewijs, bronnen, figuren, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (username, conv_id, tekst_hash) DO UPDATE SET "
                "lineage=excluded.lineage, rekenbewijs=excluded.rekenbewijs, "
                "bronnen=excluded.bronnen, figuren=excluded.figuren",
                (
                    username,
                    conv_id,
                    tekst_hash,
                    json.dumps(rij["lineage"], ensure_ascii=False, default=str),
                    json.dumps(rij["rekenbewijs"], ensure_ascii=False, default=str),
                    json.dumps(rij.get("bronnen") or {}, ensure_ascii=False, default=str),
                    json.dumps(rij.get("figuren") or [], ensure_ascii=False, default=str),
                    rij["created_at"],
                ),
            )
        conn.commit()


def recipe_for_key(username: str, key: str) -> dict | None:
    """Het nieuwste recept van deze gebruiker voor `key`, over al zijn gesprekken; nooit dat van een ander."""
    with _connection() as conn:
        row = _execute(
            conn,
            "SELECT recipe FROM data_recipes WHERE username = ? AND data_key = ? ORDER BY created_at DESC LIMIT 1",
            (username, key),
        ).fetchone()
    return json.loads(row["recipe"]) if row else None


# Een rapport is een werkboek met HTML en zonder dashboard-spec; zo leest de frontend het ook (getWorkbookType).
_WERKBOEK_TYPE = (
    "CASE WHEN dashboard_spec IS NULL AND COALESCE(html_content, '') <> '' THEN 'report' ELSE 'dashboard' END"
)


def list_workbooks(username: str) -> list[dict]:
    """De werkboeken van een gebruiker zonder hun inhoud, nieuwste eerst (#633).

    De lijst draagt alleen wat een kaart toont; de HTML, berichten, figuren en spec komen per werkboek
    uit `get_workbook`. Met alle rapport-HTML erin werd de lijst bij 85 rapporten 2,1 MB.
    """
    with _connection() as conn:
        rows = _execute(
            conn,
            f"SELECT id, title, description, instelling, created_at, {_WERKBOEK_TYPE} AS type FROM workbooks "
            "WHERE username = ? ORDER BY created_at DESC",
            (username,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_workbook(username: str, wb_id: str) -> dict | None:
    """Eén eigen werkboek met zijn inhoud, of None als het er niet (meer) is."""
    with _connection() as conn:
        row = _execute(
            conn,
            "SELECT id, title, description, messages, figures, instelling, "
            f"html_content, dashboard_spec, created_at, {_WERKBOEK_TYPE} AS type FROM workbooks "
            "WHERE id = ? AND username = ?",
            (wb_id, username),
        ).fetchone()
    return dict(row) if row else None


def upsert_workbook(
    username: str,
    wb_id: str,
    title: str,
    description: str,
    messages: list[dict] | None = None,
    figures: list | None = None,
    instelling: str | None = None,
    html_content: str | None = None,
    dashboard_spec: dict | None = None,
    created_at: str = "",
) -> None:
    with _connection() as conn:
        _execute(
            conn,
            "INSERT INTO workbooks (id, username, title, description, messages, figures, "
            "instelling, html_content, dashboard_spec, created_at, laatst_gebruikt) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (id, username) DO UPDATE SET title=excluded.title, "
            "description=excluded.description, messages=excluded.messages, "
            "figures=excluded.figures, instelling=excluded.instelling, "
            "html_content=excluded.html_content, dashboard_spec=excluded.dashboard_spec, "
            "created_at=excluded.created_at, laatst_gebruikt=excluded.laatst_gebruikt",
            (
                wb_id,
                username,
                title,
                description,
                json.dumps(messages) if messages is not None else None,
                json.dumps(figures) if figures is not None else None,
                instelling,
                html_content,
                json.dumps(dashboard_spec) if dashboard_spec is not None else None,
                created_at,
                int(time.time()),
            ),
        )
        conn.commit()


_WERKBOEKGROOTTE = (
    "LENGTH(COALESCE(messages, '')) + LENGTH(COALESCE(figures, '')) + LENGTH(COALESCE(html_content, '')) "
    "+ LENGTH(COALESCE(dashboard_spec, ''))"
)


def opslagstand(username: str, soort: str, item_id: str) -> dict[str, int | None]:
    """Wat `username` bewaart (#682, S24): aantal gesprekken en werkboeken, hun samen bewaarde grootte (tekens) en de
    grootte van het item `item_id` van `soort` ("gesprek" of "werkboek"), None als het nog niet bestaat."""
    tabel, grootte = ("conversations", "LENGTH(messages)") if soort == "gesprek" else ("workbooks", _WERKBOEKGROOTTE)
    with _connection() as conn:
        g = _execute(
            conn,
            "SELECT COUNT(*) AS n, COALESCE(SUM(LENGTH(messages)), 0) AS grootte FROM conversations WHERE username = ?",
            (username,),
        ).fetchone()
        w = _execute(
            conn,
            f"SELECT COUNT(*) AS n, COALESCE(SUM({_WERKBOEKGROOTTE}), 0) AS grootte FROM workbooks WHERE username = ?",
            (username,),
        ).fetchone()
        item = _execute(
            conn, f"SELECT {grootte} AS grootte FROM {tabel} WHERE id = ? AND username = ?", (item_id, username)
        ).fetchone()
    return {
        "gesprekken": int(g["n"]),
        "werkboeken": int(w["n"]),
        "grootte": int(g["grootte"]) + int(w["grootte"]),
        "item": None if item is None else int(item["grootte"] or 0),
    }


def werkboek_geopend(username: str, wb_id: str) -> None:
    """Een eigen werkboek is geopend: zijn bewaartermijn van 365 dagen begint opnieuw (#485)."""
    with _connection() as conn:
        _execute(
            conn,
            "UPDATE workbooks SET laatst_gebruikt = ? WHERE id = ? AND username = ?",
            (int(time.time()), wb_id, username),
        )
        conn.commit()


def workbook_belongs_to(username: str, wb_id: str) -> bool:
    with _connection() as conn:
        row = _execute(
            conn,
            "SELECT 1 FROM workbooks WHERE id = ? AND username = ?",
            (wb_id, username),
        ).fetchone()
    return row is not None


def delete_workbook(username: str, wb_id: str) -> None:
    with _connection() as conn:
        _execute(
            conn,
            "DELETE FROM workbooks WHERE id = ? AND username = ?",
            (wb_id, username),
        )
        conn.commit()


def add_feedback(
    username: str,
    workbook_id: str,
    report_type: str,
    report_title: str,
    answers: dict[str, str | list[str]],
    instelling: str = "",
) -> None:
    with _connection() as conn:
        _execute(
            conn,
            "INSERT INTO feedback (id, username, workbook_id, report_type, report_title, answers, created_at, instelling) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                username,
                workbook_id,
                report_type,
                report_title,
                json.dumps(answers),
                datetime.now(UTC).isoformat(timespec="seconds"),
                instelling,
            ),
        )
        conn.commit()


def list_feedback_workbooks(username: str) -> list[str]:
    with _connection() as conn:
        rows = _execute(
            conn,
            "SELECT DISTINCT workbook_id FROM feedback WHERE username = ? ORDER BY workbook_id",
            (username,),
        ).fetchall()
    return [r["workbook_id"] for r in rows]


def add_algemene_feedback(username: str, soort: str, tekst: str, pagina: str) -> None:
    with _connection() as conn:
        _execute(
            conn,
            "INSERT INTO algemene_feedback (id, username, soort, tekst, pagina, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), username, soort, tekst, pagina, datetime.now(UTC).isoformat(timespec="seconds")),
        )
        conn.commit()


def all_algemene_feedback() -> list[dict]:
    """Alle algemene feedback, nieuwste eerst: de lijst voor het team (#600)."""
    with _connection() as conn:
        rows = _execute(conn, "SELECT * FROM algemene_feedback ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]
