import contextlib
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


def _tls_verplicht(uri: str) -> dict:
    """`sslmode=require` als de URI zelf geen sslmode noemt (#683).

    De URI uit het secret noemt er geen, en de default van psycopg2 (`prefer`) valt stil terug op een
    onversleutelde verbinding. Test en playground praten al TLS 1.3 (gemeten met `pg_stat_ssl`), dus
    `require` breekt daar niets; een URI met een eigen sslmode (lokaal `sslmode=disable`) houdt die.
    """
    return {} if "sslmode=" in uri else {"sslmode": "require"}


def _connect() -> Any:
    if _USE_POSTGRES:
        try:
            import psycopg2
            import psycopg2.extras

            uri = os.getenv("POSTGRES_URI") or ""
            conn = psycopg2.connect(uri, **_tls_verplicht(uri))
            conn.autocommit = False
            return conn
        except ImportError:
            raise RuntimeError("psycopg2 required for PostgreSQL but not installed") from None
    else:
        conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


class _Pool:
    """Hergebruikt Postgres-verbindingen over aanroepen heen (#508).

    Elke aanroep opende een eigen verbinding (TCP, TLS, authenticatie). Een verbinding gaat na
    gebruik met een rollback terug, zodat een leesactie geen transactie open laat staan; na een
    commit is die rollback niets. Een verbinding die niet meer werkt (server herstart, netwerk weg)
    gaat dicht in plaats van terug. Meer dan `size` aanroepen tegelijk wachten op een vrije.
    """

    def __init__(self, connect: Callable[[], Any], size: int) -> None:
        self._connect = connect
        self._idle: list[Any] = []
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(size)

    @contextmanager
    def connection(self) -> Generator[Any]:
        with self._slots:
            conn = self._take()
            try:
                yield conn
            finally:
                self._give_back(conn)

    def _take(self) -> Any:
        with self._lock:
            if self._idle:
                return self._idle.pop()
        return self._connect()

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
        conn.close()


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

    _voeg_feedback_instelling_toe(conn)
    _begin_bewaartermijn_werkboeken(conn)
    _run_once(conn, "160_dedupe_legacy_conversations", _dedupe_conversations)
    _run_once(conn, MIGRATIE_FEEDBACK_ZONDER_GESPREK, _ontkoppel_feedback_zonder_gesprek)


def _voeg_feedback_instelling_toe(conn: Any) -> None:
    """Feedback van vóór de kolom `instelling` krijgt een lege waarde; idempotent, dus veilig bij elke start."""
    if _USE_POSTGRES:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE feedback ADD COLUMN IF NOT EXISTS instelling TEXT NOT NULL DEFAULT ''")
        conn.commit()
        cursor.close()
    elif "instelling" not in {row[1] for row in conn.execute("PRAGMA table_info(feedback)")}:
        conn.execute("ALTER TABLE feedback ADD COLUMN instelling TEXT NOT NULL DEFAULT ''")
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


# Eén oordeel per antwoord; een nieuw oordeel vervangt het oude (#248). trace is
# JSON uit het opgeslagen gesprek (core/answer_feedback.py), zodat de melding
# reproduceerbaar blijft als het gesprek later verandert of verdwijnt; verdwijnt het,
# dan gaan gebruikersnaam en gesprek-id eruit (#476, zie delete_conversation).
_ANSWER_FEEDBACK_TABLE = """
    CREATE TABLE IF NOT EXISTS answer_feedback (
        username        TEXT    NOT NULL,
        conversation_id TEXT    NOT NULL,
        message_index   INTEGER NOT NULL,
        oordeel         TEXT    NOT NULL,
        toelichting     TEXT    NOT NULL DEFAULT '',
        trace           TEXT    NOT NULL,
        created_at      TEXT    NOT NULL,
        PRIMARY KEY (username, conversation_id, message_index)
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


# Bij uitloggen ingetrokken tokens (#479): alleen sha256(token), nooit het token, tot zijn exp.
# Daarna faalt het token toch al op zijn vervaltijd en kan de rij weg.
_REVOKED_TOKENS_TABLE = """
    CREATE TABLE IF NOT EXISTS revoked_tokens (
        token_hash TEXT    PRIMARY KEY,
        expires_at INTEGER NOT NULL
    )
"""
_REVOKED_TOKENS_INDEX = "CREATE INDEX IF NOT EXISTS idx_revoked_expires ON revoked_tokens(expires_at)"


def init_db() -> None:
    with _connection() as conn:
        cursor = conn.cursor()

        if _USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id        TEXT    NOT NULL,
                    username  TEXT    NOT NULL,
                    title     TEXT    NOT NULL,
                    timestamp INTEGER NOT NULL,
                    messages  TEXT    NOT NULL,
                    PRIMARY KEY (id, username)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(username, timestamp DESC)")
            cursor.execute("""
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
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wb_user ON workbooks(username, created_at DESC)")
            cursor.execute(_FEEDBACK_TABLE)
            cursor.execute(_ANSWER_FEEDBACK_TABLE)
            cursor.execute(_ALGEMENE_FEEDBACK_TABLE)
            cursor.execute(_DATA_RECIPES_TABLE)
            cursor.execute(_DATA_RECIPES_INDEX)
            cursor.execute(_REVOKED_TOKENS_TABLE)
            cursor.execute(_REVOKED_TOKENS_INDEX)
            cursor.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)")
            conn.commit()
            cursor.close()
        else:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id        TEXT    NOT NULL,
                    username  TEXT    NOT NULL,
                    title     TEXT    NOT NULL,
                    timestamp INTEGER NOT NULL,
                    messages  TEXT    NOT NULL,
                    PRIMARY KEY (id, username)
                );
                CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(username, timestamp DESC);

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
                );
                CREATE INDEX IF NOT EXISTS idx_wb_user ON workbooks(username, created_at DESC);

                CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY);
            """)
            conn.execute(_FEEDBACK_TABLE)
            conn.execute(_ANSWER_FEEDBACK_TABLE)
            conn.execute(_ALGEMENE_FEEDBACK_TABLE)
            conn.execute(_DATA_RECIPES_TABLE)
            conn.execute(_DATA_RECIPES_INDEX)
            conn.execute(_REVOKED_TOKENS_TABLE)
            conn.execute(_REVOKED_TOKENS_INDEX)

        _migrate(conn)
        purge_expired_revocations(conn)
        conn.commit()


def purge_expired_revocations(conn: Any) -> None:
    """Drop denylist rows whose token has expired: verification rejects such a token on its own."""
    _execute(conn, "DELETE FROM revoked_tokens WHERE expires_at < ?", (int(time.time()),))


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


def is_token_revoked(token_hash: str) -> bool:
    with _connection() as conn:
        row = _execute(conn, "SELECT 1 FROM revoked_tokens WHERE token_hash = ?", (token_hash,)).fetchone()
    return row is not None


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


def upsert_conversation(username: str, conv_id: str, title: str, timestamp: int, messages: list[dict]) -> None:
    """Bewaar een gesprek; de titel alleen bij het aanmaken.

    Elke opslag na een antwoord stuurt de automatische titel uit de eerste vraag mee. Een bestaand gesprek houdt
    zijn titel, zodat een hernoeming (rename_conversation) blijft staan, ook vanaf een ander apparaat (#757).
    """
    with _connection() as conn:
        _execute(
            conn,
            "INSERT INTO conversations (id, username, title, timestamp, messages) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (id, username) DO UPDATE SET "
            "timestamp=excluded.timestamp, messages=excluded.messages",
            (conv_id, username, title, _normalize_ts(timestamp), json.dumps(messages)),
        )
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


# Feedback op een antwoord van een verwijderd gesprek blijft voor het team (oordeel, toelichting,
# trace), maar hangt niet meer aan de gebruiker of zijn gesprek (#476, privacy M2). Een willekeurig
# gesprek-id per verwijderd gesprek houdt de meldingen daarvan bij elkaar zonder dat ze te herleiden zijn.
VERWIJDERDE_GEBRUIKER = "verwijderd"


def delete_conversation(username: str, conv_id: str) -> None:
    with _connection() as conn:
        _execute(
            conn,
            "DELETE FROM conversations WHERE id = ? AND username = ?",
            (conv_id, username),
        )
        ruim_gesprek_op(conn, username, conv_id)
        conn.commit()


def ruim_gesprek_op(conn: Any, username: str, conv_id: str) -> int:
    """Wat bij een verwijderd gesprek hoort, in de transactie van `conn`: recepten weg, feedback losgekoppeld (#476).

    Voor het verwijderen door de gebruiker en voor de opschoning na de bewaartermijn (persistence/opschonen.py).
    Geeft het aantal verwijderde recepten.
    """
    recepten = _execute(conn, "DELETE FROM data_recipes WHERE username = ? AND conv_id = ?", (username, conv_id))
    _ontkoppel_feedback(conn, username, conv_id)
    return recepten.rowcount


def _ontkoppel_feedback(conn: Any, username: str, conv_id: str) -> None:
    _execute(
        conn,
        "UPDATE answer_feedback SET username = ?, conversation_id = ? WHERE username = ? AND conversation_id = ?",
        (VERWIJDERDE_GEBRUIKER, str(uuid.uuid4()), username, conv_id),
    )


MIGRATIE_FEEDBACK_ZONDER_GESPREK = "476_ontkoppel_feedback_zonder_gesprek"


def _ontkoppel_feedback_zonder_gesprek(conn: Any) -> None:
    """Feedback van gesprekken die vóór #476 zijn verwijderd: dezelfde ontkoppeling als delete_conversation.

    Feedback kan alleen bij een bestaand gesprek (routes/answer_feedback.py), dus een rij zonder
    gesprek hoort bij een verwijderd gesprek.
    """
    paren = _execute(
        conn,
        "SELECT DISTINCT username, conversation_id FROM answer_feedback a WHERE username <> ? AND NOT EXISTS "
        "(SELECT 1 FROM conversations c WHERE c.id = a.conversation_id AND c.username = a.username)",
        (VERWIJDERDE_GEBRUIKER,),
    ).fetchall()
    for paar in paren:
        _ontkoppel_feedback(conn, paar["username"], paar["conversation_id"])
    logger.info("feedback van %d verwijderde gesprekken ontkoppeld", len(paren))


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


def conversation_messages(username: str, conv_id: str) -> list[dict] | None:
    """De berichten van een eigen gesprek; None als deze gebruiker het niet heeft."""
    conversation = get_conversation(username, conv_id)
    return None if conversation is None else conversation["messages"]


def upsert_answer_feedback(
    username: str, conv_id: str, message_index: int, oordeel: str, toelichting: str, trace: dict
) -> None:
    with _connection() as conn:
        _execute(
            conn,
            "INSERT INTO answer_feedback "
            "(username, conversation_id, message_index, oordeel, toelichting, trace, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (username, conversation_id, message_index) DO UPDATE SET "
            "oordeel=excluded.oordeel, toelichting=excluded.toelichting, trace=excluded.trace, "
            "created_at=excluded.created_at",
            (
                username,
                conv_id,
                message_index,
                oordeel,
                toelichting,
                json.dumps(trace, ensure_ascii=False),
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        conn.commit()


def answer_feedback_for(username: str, conv_id: str) -> dict[int, str]:
    """Het oordeel per antwoord in een eigen gesprek, om de knoppen na heropenen te tonen."""
    with _connection() as conn:
        rows = _execute(
            conn,
            "SELECT message_index, oordeel FROM answer_feedback WHERE username = ? AND conversation_id = ?",
            (username, conv_id),
        ).fetchall()
    return {r["message_index"]: r["oordeel"] for r in rows}


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


def all_answer_feedback() -> list[dict]:
    """Alle meldingen, nieuwste eerst: de lijst voor het team."""
    with _connection() as conn:
        rows = _execute(conn, "SELECT * FROM answer_feedback ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]
