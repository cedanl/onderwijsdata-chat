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

    assert gezien == [(uri, extra)]
