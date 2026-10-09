"""Recepten per data-key in de database: per gebruiker, per gesprek, en weg met het gesprek (#472)."""

import importlib
import sqlite3
import sys
import types

import pytest

_CBS = {"laad": ["get_cbs_data", {"dataset_id": "85423NED", "filters": None}]}
_SELECTIE = {"afgeleid_van": "cbs:85423NED", "tool": "query_data", "args": {"filters": {"a": 1}}, "stap": "a = 1"}


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    return db


def test_een_recept_terugvinden_per_gebruiker_en_key(db):
    db.save_recipes("alice", "c1", {"cbs:85423NED": _CBS})

    assert db.recipe_for_key("alice", "cbs:85423NED") == _CBS
    assert db.recipe_for_key("bob", "cbs:85423NED") is None
    assert db.recipe_for_key("alice", "cbs:anders") is None


def test_de_recepten_van_een_gesprek(db):
    db.save_recipes("alice", "c1", {"cbs:85423NED": _CBS, "cbs:85423NED:ab": _SELECTIE})
    db.save_recipes("alice", "c2", {"rio:x": {"laad": ["get_rio_data", {"resource": "x"}]}})
    db.save_recipes("bob", "c1", {"rio:y": {"laad": ["get_rio_data", {"resource": "y"}]}})

    assert db.recipes_for("alice", "c1") == {"cbs:85423NED": _CBS, "cbs:85423NED:ab": _SELECTIE}


def test_opnieuw_opslaan_werkt_het_recept_bij(db):
    db.save_recipes("alice", "c1", {"k": {"laad": ["get_rio_data", {"resource": "oud"}]}})
    db.save_recipes("alice", "c1", {"k": _CBS})

    assert db.recipes_for("alice", "c1") == {"k": _CBS}


def test_nieuwste_recept_wint_over_gesprekken(db, monkeypatch):
    db.save_recipes("alice", "oud", {"k": {"laad": ["get_rio_data", {"resource": "oud"}]}})
    conn = db._connect()
    conn.execute("UPDATE data_recipes SET created_at = '2000-01-01T00:00:00+00:00'")
    conn.commit()
    conn.close()
    db.save_recipes("alice", "nieuw", {"k": _CBS})

    assert db.recipe_for_key("alice", "k") == _CBS


def test_een_gesprek_verwijderen_verwijdert_zijn_recepten(db):
    db.upsert_conversation("alice", "c1", "Titel", 1000, [])
    db.save_recipes("alice", "c1", {"cbs:85423NED": _CBS})
    db.save_recipes("alice", "c2", {"rio:x": _CBS})
    db.save_recipes("bob", "c1", {"cbs:85423NED": _CBS})

    db.delete_conversation("alice", "c1")

    assert db.recipes_for("alice", "c1") == {}
    assert db.recipes_for("alice", "c2") == {"rio:x": _CBS}
    assert db.recipes_for("bob", "c1") == {"cbs:85423NED": _CBS}


def test_init_db_is_herhaalbaar(db):
    db.save_recipes("alice", "c1", {"k": _CBS})
    db.init_db()
    db.init_db()
    assert db.recipe_for_key("alice", "k") == _CBS


def test_een_bestaande_database_zonder_de_tabel_krijgt_hem(tmp_path, monkeypatch):
    pad = tmp_path / "oud.db"
    oud = sqlite3.connect(pad)
    oud.executescript("""
        CREATE TABLE conversations (
            id TEXT NOT NULL, username TEXT NOT NULL, title TEXT NOT NULL,
            timestamp INTEGER NOT NULL, messages TEXT NOT NULL, PRIMARY KEY (id, username)
        );
        CREATE TABLE workbooks (
            id TEXT NOT NULL, username TEXT NOT NULL, title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', messages TEXT, figures TEXT, instelling TEXT,
            html_content TEXT, dashboard_spec TEXT, created_at TEXT NOT NULL, PRIMARY KEY (id, username)
        );
        CREATE TABLE schema_migrations (name TEXT PRIMARY KEY);
        INSERT INTO schema_migrations VALUES ('160_dedupe_legacy_conversations');
        INSERT INTO conversations VALUES ('c1', 'alice', 'Oud gesprek', 1700000000, '[]');
    """)
    oud.close()
    monkeypatch.setenv("DATABASE_PATH", str(pad))
    from persistence import db

    importlib.reload(db)
    db.init_db()

    assert [c["id"] for c in db.list_conversations("alice")] == ["c1"]
    db.save_recipes("alice", "c1", {"k": _CBS})
    assert db.recipe_for_key("alice", "k") == _CBS


class _Cursor:
    def __init__(self, log):
        self.log = log

    def execute(self, sql, params=()):
        self.log.append(sql)

    def fetchone(self):
        return (1,)

    def close(self):
        pass


class _Conn:
    def __init__(self):
        self.log: list[str] = []

    def cursor(self, cursor_factory=None):
        return _Cursor(self.log)

    def commit(self):
        pass

    def close(self):
        pass


def test_postgres_maakt_de_tabel_ook_aan(monkeypatch):
    """De Postgres-tak van init_db kent de tabel ook, met CREATE TABLE IF NOT EXISTS."""
    import persistence.db as db

    extras = types.ModuleType("psycopg2.extras")
    vars(extras).update(RealDictCursor=object)
    psycopg2 = types.ModuleType("psycopg2")
    vars(psycopg2).update(extras=extras)
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg2)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras)
    monkeypatch.setattr(db, "_USE_POSTGRES", True)
    conn = _Conn()
    monkeypatch.setattr(db, "_connect", lambda: conn)

    db.init_db()

    statements = [" ".join(s.split()) for s in conn.log]
    assert any(s.startswith("CREATE TABLE IF NOT EXISTS data_recipes") for s in statements)
    assert any(s.startswith("CREATE INDEX IF NOT EXISTS idx_recipes_key") for s in statements)
