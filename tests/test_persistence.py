import json

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    import importlib

    from persistence import db
    importlib.reload(db)
    db.init_db()
    return db


def test_init_db_creates_tables(db):
    import os
    import sqlite3
    conn = sqlite3.connect(os.environ["DATABASE_PATH"])
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    conn.close()
    assert "conversations" in tables
    assert "workbooks" in tables


def test_upsert_and_list_conversation(db):
    msgs = [{"role": "user", "content": "hoi"}]
    db.upsert_conversation("alice", "c1", "Eerste gesprek", 1000, msgs)
    result = db.list_conversations("alice")
    assert len(result) == 1
    assert result[0]["id"] == "c1"
    assert result[0]["title"] == "Eerste gesprek"
    assert result[0]["timestamp"] == 1000
    assert json.loads(result[0]["messages"]) == msgs


def test_upsert_conversation_is_idempotent(db):
    msgs = [{"role": "user", "content": "v1"}]
    db.upsert_conversation("alice", "c1", "Titel", 1000, msgs)

    msgs2 = [{"role": "user", "content": "v2"}]
    db.upsert_conversation("alice", "c1", "Titel update", 2000, msgs2)

    result = db.list_conversations("alice")
    assert len(result) == 1
    assert result[0]["title"] == "Titel update"
    assert json.loads(result[0]["messages"]) == msgs2


def test_conversations_scoped_to_user(db):
    db.upsert_conversation("alice", "c1", "Alice chat", 1000, [])
    db.upsert_conversation("bob", "c2", "Bob chat", 2000, [])

    assert len(db.list_conversations("alice")) == 1
    assert len(db.list_conversations("bob")) == 1
    assert db.list_conversations("alice")[0]["title"] == "Alice chat"


def test_list_conversations_max_15(db):
    for i in range(20):
        db.upsert_conversation("alice", f"c{i}", f"Chat {i}", i * 1000, [])
    result = db.list_conversations("alice")
    assert len(result) == 15


def test_list_conversations_ordered_newest_first(db):
    db.upsert_conversation("alice", "old", "Oud", 1000, [])
    db.upsert_conversation("alice", "new", "Nieuw", 9000, [])
    result = db.list_conversations("alice")
    assert result[0]["id"] == "new"
    assert result[1]["id"] == "old"


def test_delete_conversation(db):
    db.upsert_conversation("alice", "c1", "Chat", 1000, [])
    db.delete_conversation("alice", "c1")
    assert len(db.list_conversations("alice")) == 0


def test_delete_conversation_scoped_to_user(db):
    db.upsert_conversation("alice", "c1", "Alice", 1000, [])
    db.upsert_conversation("bob", "c1", "Bob", 1000, [])
    db.delete_conversation("alice", "c1")
    assert len(db.list_conversations("alice")) == 0
    assert len(db.list_conversations("bob")) == 1


def test_upsert_and_list_workbook(db):
    db.upsert_workbook(
        "alice", "wb1", "Dashboard 1", "beschrijving",
        messages=[{"role": "user", "content": "test"}],
        figures=[{"type": "bar"}],
        instelling="HU",
        html_content="<html></html>",
        created_at="2024-01-01T00:00:00.000Z",
    )
    result = db.list_workbooks("alice")
    assert len(result) == 1
    assert result[0]["id"] == "wb1"
    assert result[0]["title"] == "Dashboard 1"
    assert result[0]["instelling"] == "HU"
    assert json.loads(result[0]["messages"]) == [{"role": "user", "content": "test"}]


def test_workbooks_scoped_to_user(db):
    db.upsert_workbook("alice", "wb1", "Alice WB", "", created_at="2024-01-01T00:00:00Z")
    db.upsert_workbook("bob", "wb2", "Bob WB", "", created_at="2024-01-01T00:00:00Z")
    assert len(db.list_workbooks("alice")) == 1
    assert len(db.list_workbooks("bob")) == 1


def test_delete_workbook(db):
    db.upsert_workbook("alice", "wb1", "WB", "", created_at="2024-01-01T00:00:00Z")
    db.delete_workbook("alice", "wb1")
    assert len(db.list_workbooks("alice")) == 0


def test_delete_workbook_scoped_to_user(db):
    db.upsert_workbook("alice", "wb1", "A", "", created_at="2024-01-01T00:00:00Z")
    db.upsert_workbook("bob", "wb1", "B", "", created_at="2024-01-01T00:00:00Z")
    db.delete_workbook("alice", "wb1")
    assert len(db.list_workbooks("alice")) == 0
    assert len(db.list_workbooks("bob")) == 1


def test_upsert_workbook_is_idempotent(db):
    db.upsert_workbook("alice", "wb1", "V1", "old", created_at="2024-01-01T00:00:00Z")
    db.upsert_workbook("alice", "wb1", "V2", "new", created_at="2024-01-02T00:00:00Z")
    result = db.list_workbooks("alice")
    assert len(result) == 1
    assert result[0]["title"] == "V2"


def test_workbook_with_dashboard_spec(db):
    spec = {
        "title": "Test Dashboard",
        "kpis": [{"label": "Studenten", "value": "1.000"}],
        "figures_json": ["{}"],
        "sources": ["DUO"],
        "recipe": [{"name": "get_duo_data", "arguments": "{}"}],
    }
    db.upsert_workbook(
        "alice", "wb-spec", "Spec Dashboard", "met spec",
        dashboard_spec=spec,
        created_at="2024-01-01T00:00:00Z",
    )
    result = db.list_workbooks("alice")
    assert len(result) == 1
    loaded = json.loads(result[0]["dashboard_spec"])
    assert loaded["title"] == "Test Dashboard"
    assert len(loaded["kpis"]) == 1


def test_workbook_without_dashboard_spec_returns_none(db):
    db.upsert_workbook("alice", "wb-old", "Old", "", created_at="2024-01-01T00:00:00Z")
    result = db.list_workbooks("alice")
    assert result[0]["dashboard_spec"] is None


# --- Timestamp-normalisatie ---


def test_upsert_normalizes_millisecond_timestamp(db):
    ms_ts = 1700000000000
    db.upsert_conversation("alice", "c-ms", "MS test", ms_ts, [])
    result = db.list_conversations("alice")
    assert result[0]["timestamp"] == 1700000000


def test_upsert_keeps_seconds_timestamp(db):
    sec_ts = 1700000000
    db.upsert_conversation("alice", "c-sec", "Sec test", sec_ts, [])
    result = db.list_conversations("alice")
    assert result[0]["timestamp"] == 1700000000


def test_migrate_converts_existing_ms_timestamps(db):
    import os
    import sqlite3
    conn = sqlite3.connect(os.environ["DATABASE_PATH"])
    conn.execute(
        "INSERT INTO conversations (id, username, title, timestamp, messages) "
        "VALUES (?, ?, ?, ?, ?)",
        ("c-old", "alice", "Oud", 1700000000000, "[]"),
    )
    conn.commit()
    conn.close()

    import importlib
    importlib.reload(db._module if hasattr(db, '_module') else __import__('persistence.db', fromlist=['db']))
    from persistence import db as fresh_db
    importlib.reload(fresh_db)
    fresh_db.init_db()

    result = fresh_db.list_conversations("alice")
    old = next(r for r in result if r["id"] == "c-old")
    assert old["timestamp"] == 1700000000


def _reload_and_init(tmp_path, monkeypatch):
    """Reload the db module with a fresh DATABASE_PATH and run init_db()."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    import importlib

    from persistence import db as fresh
    importlib.reload(fresh)
    fresh.init_db()
    return fresh


def _raw_insert(conn, conv_id, username, title, timestamp, messages):
    conn.execute(
        "INSERT INTO conversations (id, username, title, timestamp, messages) "
        "VALUES (?, ?, ?, ?, ?)",
        (conv_id, username, title, timestamp, json.dumps(messages)),
    )


def test_migrate_dedupes_legacy_conversation_duplicates(db, tmp_path, monkeypatch):
    conn = db._connect()
    msgs_short = [{"role": "user", "content": "Hoeveel studenten?"}, {"role": "assistant", "content": "Kort."}]
    msgs_full = [
        {"role": "user", "content": "Hoeveel studenten?"},
        {"role": "assistant", "content": "Volledig antwoord."},
        {"role": "user", "content": "En in deeltijd?"},
        {"role": "assistant", "content": "Nog vollediger."},
    ]
    _raw_insert(conn, "dup-1", "alice", "Mijn vraag", 1700000000, msgs_full)
    _raw_insert(conn, "dup-2", "alice", "Mijn vraag", 1690000000, msgs_short)
    _raw_insert(conn, "dup-3", "alice", "mijn vraag", 1680000000, msgs_full)
    _raw_insert(conn, "unique", "bob", "Mijn vraag", 1700000001, msgs_full)
    conn.commit()
    conn.close()

    fresh = _reload_and_init(tmp_path, monkeypatch)

    alice = fresh.list_conversations("alice")
    assert [r["id"] for r in alice] == ["dup-1"], alice
    bob = fresh.list_conversations("bob")
    assert [r["id"] for r in bob] == ["unique"]


def test_migrate_keeps_richest_row_on_tiebreaker(db, tmp_path, monkeypatch):
    conn = db._connect()
    msgs = [
        {"role": "user", "content": "Wie doet mbo?"},
        {"role": "assistant", "content": "Antwoord."},
    ]
    _raw_insert(conn, "a-1", "alice", "MBO", 1700000000, msgs)
    _raw_insert(conn, "a-2", "alice", "MBO", 1690000000, msgs)
    conn.commit()
    conn.close()

    fresh = _reload_and_init(tmp_path, monkeypatch)

    alice = fresh.list_conversations("alice")
    assert [r["id"] for r in alice] == ["a-1"]


def test_migrate_dedupe_is_idempotent(db, tmp_path, monkeypatch):
    conn = db._connect()
    msgs = [{"role": "user", "content": "Hoeveel huur?"}, {"role": "assistant", "content": "Antwoord."}]
    _raw_insert(conn, "b-1", "alice", "Huur", 1700000000, msgs)
    _raw_insert(conn, "b-2", "alice", "Huur", 1690000000, msgs)
    conn.commit()
    conn.close()

    _reload_and_init(tmp_path, monkeypatch)
    fresh = _reload_and_init(tmp_path, monkeypatch)

    alice = fresh.list_conversations("alice")
    assert [r["id"] for r in alice] == ["b-1"]


def test_migrate_dedupe_ignores_different_first_questions(db, tmp_path, monkeypatch):
    conn = db._connect()
    msgs_a = [{"role": "user", "content": "Vraag A"}, {"role": "assistant", "content": "A"}]
    msgs_b = [{"role": "user", "content": "Vraag B"}, {"role": "assistant", "content": "B"}]
    _raw_insert(conn, "d-1", "alice", "Zelfde titel", 1700000000, msgs_a)
    _raw_insert(conn, "d-2", "alice", "Zelfde titel", 1690000000, msgs_b)
    conn.commit()
    conn.close()

    fresh = _reload_and_init(tmp_path, monkeypatch)

    alice = fresh.list_conversations("alice")
    assert sorted(r["id"] for r in alice) == ["d-1", "d-2"]


def test_rename_conversation_scoped_to_user(db):
    db.upsert_conversation("alice", "c1", "Van Alice", 1, [])
    assert db.rename_conversation("bob", "c1", "Gekaapt") is False
    assert db.list_conversations("alice")[0]["title"] == "Van Alice"
    assert db.rename_conversation("alice", "c1", "Nieuw") is True
    assert db.list_conversations("alice")[0]["title"] == "Nieuw"
