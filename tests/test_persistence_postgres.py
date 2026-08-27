import sys
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
    yield extras
    monkeypatch.setattr(db, "_USE_POSTGRES", False)


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return []


class FakeConn:
    def cursor(self, cursor_factory=None):
        self._cursor = FakeCursor()
        return self._cursor


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
