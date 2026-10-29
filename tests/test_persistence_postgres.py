import contextlib
import sys
import threading
import types

import pytest

import persistence.db as db


@pytest.fixture
def fake_psycopg2(monkeypatch):
    """Provide a stand-in `psycopg2` so the Postgres branch of `_execute`
    can be exercised without the real (optional) driver installed."""
    psycopg2 = types.ModuleType("psycopg2")
    extras = types.ModuleType("psycopg2.extras")
    extras.RealDictCursor = object
    psycopg2.extras = extras
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg2)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras)
    monkeypatch.setattr(db, "_USE_POSTGRES", True)
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setenv("POSTGRES_URI", "postgresql://test")
    yield psycopg2
    monkeypatch.setattr(db, "_USE_POSTGRES", False)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.calls = []

    def execute(self, sql, params=()):
        if self.conn.dood:
            self.conn.closed = 2
            raise RuntimeError("server closed the connection unexpectedly")
        if self.conn.faalt:
            raise RuntimeError("verbinding weg")
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return None


class FakeConn:
    """Wat de pool van een psycopg2-verbinding gebruikt: closed, rollback, commit, close, cursor."""

    def __init__(self):
        self.closed = 0
        self.rollbacks = 0
        self.commits = 0
        self.faalt = False  # elke query faalt, en de rollback erna ook: de verbinding is kapot
        self.dood = False  # de server is weg (herstart, failover): de query faalt en psycopg2 zet closed op 2

    def cursor(self, cursor_factory=None):
        self._cursor = FakeCursor(self)
        return self._cursor

    def rollback(self):
        if self.faalt:
            raise RuntimeError("verbinding weg")
        self.rollbacks += 1

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = 1


@pytest.fixture
def verbindingen(fake_psycopg2):
    """Elke verbinding die de driver opende, in volgorde."""
    gemaakt = []

    def connect(uri, **kwargs):
        conn = FakeConn()
        gemaakt.append(conn)
        return conn

    fake_psycopg2.connect = connect
    return gemaakt


def test_execute_rewrites_placeholders_for_postgres(fake_psycopg2):
    conn = FakeConn()
    cursor = db._execute(
        conn,
        "SELECT id FROM conversations WHERE username = ? ORDER BY timestamp DESC LIMIT ?",
        ("alice", 15),
    )
    assert isinstance(cursor, FakeCursor)
    sql, params = cursor.calls[0]
    assert "?" not in sql
    assert "%s" in sql
    assert params == ("alice", 15)


def test_execute_uses_realdict_cursor(fake_psycopg2):
    conn = FakeConn()
    db._execute(conn, "DELETE FROM workbooks WHERE id = ? AND username = ?", ("wb1", "alice"))
    # cursor_factory was passed through to conn.cursor
    assert conn._cursor is not None


# ── De pool (#508): één verbinding per aanroep openen kostte TCP, TLS en authenticatie per verzoek ──


def test_opeenvolgende_aanroepen_hergebruiken_een_verbinding(verbindingen):
    db.is_token_revoked("a")
    db.is_token_revoked("b")
    db.list_conversations("alice")
    assert len(verbindingen) == 1


def test_een_leesactie_laat_geen_transactie_open(verbindingen):
    """psycopg2 opent bij de eerste query een transactie; die gaat met een rollback dicht vóór hergebruik."""
    db.is_token_revoked("a")
    assert verbindingen[0].rollbacks == 1
    assert verbindingen[0].closed == 0


def test_een_mislukte_aanroep_geeft_de_verbinding_terug(verbindingen):
    """Een fout waarna de verbinding nog open is (een SQL-fout), gaat naar de aanroeper, zonder herhaling (#764)."""
    db.is_token_revoked("a")
    verbindingen[0].faalt = True
    with pytest.raises(RuntimeError):
        db.is_token_revoked("b")
    # Kapot: dicht en niet hergebruikt; de volgende aanroep krijgt een nieuwe.
    assert verbindingen[0].closed == 1
    db.is_token_revoked("c")
    assert len(verbindingen) == 2


def test_close_sluit_de_open_verbindingen(verbindingen):
    db.is_token_revoked("a")
    db.close()
    assert verbindingen[0].closed == 1
    db.is_token_revoked("b")
    assert len(verbindingen) == 2


def test_niet_meer_verbindingen_dan_de_poolgrootte():
    """Boven de grens wacht een aanroep op een vrije verbinding in plaats van er een bij te openen."""
    gemaakt = []

    def connect():
        gemaakt.append(FakeConn())
        return gemaakt[-1]

    pool = db._Pool(connect, size=1)
    eerste_binnen, laat_los, tweede_binnen = threading.Event(), threading.Event(), threading.Event()

    def houdt_vast():
        with pool.connection():
            eerste_binnen.set()
            laat_los.wait(timeout=5)

    def wacht():
        with pool.connection():
            tweede_binnen.set()

    eerste = threading.Thread(target=houdt_vast)
    eerste.start()
    assert eerste_binnen.wait(timeout=5)
    tweede = threading.Thread(target=wacht)
    tweede.start()
    assert not tweede_binnen.wait(timeout=0.2)
    laat_los.set()
    assert tweede_binnen.wait(timeout=5)
    eerste.join()
    tweede.join()
    assert len(gemaakt) == 1


# #683: de URI uit het secret noemt geen sslmode, en psycopg2 viel dan stil terug op `prefer`.
@pytest.mark.parametrize(
    ("uri", "extra"),
    [
        ("postgresql://app@db:5432/app", {"sslmode": "require"}),
        ("postgresql://app@db:5432/app?sslmode=verify-full", {}),
        ("postgresql://app@localhost/app?sslmode=disable", {}),
    ],
)
def test_de_verbinding_vraagt_tls_tenzij_de_uri_zelf_een_sslmode_noemt(fake_psycopg2, monkeypatch, uri, extra):
    gezien = []
    fake_psycopg2.connect = lambda dsn, **kwargs: gezien.append((dsn, kwargs)) or types.SimpleNamespace()
    monkeypatch.setenv("POSTGRES_URI", uri)

    db._connect()

    ((dsn, kwargs),) = gezien
    assert dsn == uri
    assert {k: v for k, v in kwargs.items() if k == "sslmode"} == extra


# ── #764: na een herstart of failover van PostgreSQL lagen er dode verbindingen in de pool ──


def _vrije_verbindingen(n):
    """Zet n verbindingen in de pool: n aanroepen tegelijk, dan geven ze ze terug."""
    with contextlib.ExitStack() as stapel:
        for _ in range(n):
            stapel.enter_context(db._connection())


def test_een_dode_vrije_verbinding_wordt_vervangen_voordat_de_aanroeper_iets_merkt(verbindingen):
    _vrije_verbindingen(3)
    for conn in verbindingen:
        conn.dood = True

    assert db.is_token_revoked("a") is False
    assert len(verbindingen) == 4
    # Drie aanroepen tegelijk krijgen elk een vrije verbinding: de vervanger en twee dode, die op hun beurt vervangen worden.
    with contextlib.ExitStack() as stapel:
        geleend = [stapel.enter_context(db._connection()) for _ in range(3)]
        for conn in geleend:
            assert db._execute(conn, "SELECT 1 FROM revoked_tokens WHERE token_hash = ?", ("b",)).fetchone() is None

    assert len(verbindingen) == 6
    assert all(conn.closed for conn in verbindingen[:3])
    assert not any(conn.closed for conn in verbindingen[3:])


def test_een_verse_verbinding_die_faalt_wordt_niet_herhaald(verbindingen, fake_psycopg2):
    """Is ook een nieuwe verbinding meteen dood, dan is de database echt weg: dat hoort de aanroeper."""

    def connect(uri, **kwargs):
        conn = FakeConn()
        conn.dood = True
        verbindingen.append(conn)
        return conn

    fake_psycopg2.connect = connect
    with pytest.raises(RuntimeError, match="server closed"):
        db.is_token_revoked("a")
    assert len(verbindingen) == 1


def test_alleen_het_eerste_statement_wordt_herhaald(verbindingen):
    """Na een geslaagd statement kan er al iets in de transactie staan: dan geen nieuwe poging."""
    _vrije_verbindingen(1)
    with pytest.raises(RuntimeError, match="server closed"), db._connection() as conn:
        db._execute(conn, "SELECT 1")
        conn.conn.dood = True
        db._execute(conn, "UPDATE conversations SET title = ?", ("x",))
    assert len(verbindingen) == 1


def test_commit_gaat_naar_de_vervangende_verbinding(verbindingen):
    _vrije_verbindingen(1)
    verbindingen[0].dood = True
    with db._connection() as conn:
        db._execute(conn, "INSERT INTO revoked_tokens VALUES (?)", ("a",))
        conn.commit()
    assert verbindingen[0].commits == 0
    assert verbindingen[1].commits == 1


def test_een_nieuwe_verbinding_krijgt_een_connect_timeout_en_keepalives(fake_psycopg2, monkeypatch):
    gezien = []
    fake_psycopg2.connect = lambda dsn, **kwargs: gezien.append(kwargs) or types.SimpleNamespace()

    db._connect()
    monkeypatch.setenv("POSTGRES_URI", "postgresql://app@db/app?connect_timeout=20")
    db._connect()

    assert gezien[0]["connect_timeout"] == 5
    assert gezien[0]["keepalives"] == 1
    assert gezien[0]["keepalives_idle"] == 30
    # Wat de URI zelf zet, blijft van de URI.
    assert "connect_timeout" not in gezien[1]
    assert gezien[1]["keepalives"] == 1
