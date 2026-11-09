"""De tabel beurtbewijs: per gebruiker, per gesprek en per tekst-hash, en weg met het gesprek (ADR-009, #875)."""

import importlib
import sqlite3
import sys
import types
from contextlib import contextmanager

import pytest

_LINEAGE = {"cbs:85423NED": {"name": "get_cbs_data", "arguments": {"dataset_id": "85423NED"}}}
_REKEN = [{"tool": "compute_kpi", "argumenten": {"data_key": "cbs:85423NED"}, "resultaat": '{"waarde": 12.5}'}]
_KAARTEN = {"cbs:85423NED": {"data_key": "cbs:85423NED", "location_col": "PROVINCIE", "value_col": "AANTAL"}}
_CONTROLE = ["2025 staat niet in de opgehaalde data."]
_NU = "2026-11-03T10:00:00+00:00"


def _rij(**anders):
    return {
        "lineage": _LINEAGE,
        "rekenbewijs": _REKEN,
        "kaarten": _KAARTEN,
        "controle": _CONTROLE,
        "created_at": _NU,
        **anders,
    }


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    return db


def test_een_rij_komt_terug_zoals_ze_bewaard_is(db):
    db.save_beurtbewijs("alice", "c1", {"h1": _rij()})

    assert db.beurtbewijs_voor("alice", "c1") == {"h1": _rij()}


def test_rijen_zijn_van_een_gebruiker_en_een_gesprek(db):
    db.save_beurtbewijs("alice", "c1", {"h1": _rij()})
    db.save_beurtbewijs("alice", "c2", {"h2": _rij()})
    db.save_beurtbewijs("bob", "c1", {"h3": _rij()})

    assert set(db.beurtbewijs_voor("alice", "c1")) == {"h1"}
    assert set(db.beurtbewijs_voor("bob", "c1")) == {"h3"}
    assert db.beurtbewijs_voor("carol", "c1") == {}
    assert db.beurtbewijs_hashes("alice", "c2") == ["h2"]


def test_opnieuw_bewaren_werkt_de_inhoud_bij_en_houdt_de_tijd_van_het_antwoord(db):
    db.save_beurtbewijs("alice", "c1", {"h1": _rij()})
    db.save_beurtbewijs(
        "alice", "c1", {"h1": _rij(rekenbewijs=[], controle=[], created_at="2030-01-01T00:00:00+00:00")}
    )

    assert db.beurtbewijs_voor("alice", "c1") == {"h1": _rij(rekenbewijs=[], controle=[])}


def test_zonder_rijen_schrijft_niets(db):
    db.save_beurtbewijs("alice", "c1", {})

    assert db.beurtbewijs_voor("alice", "c1") == {}


def test_een_onleesbare_rij_wordt_overgeslagen(db):
    db.save_beurtbewijs("alice", "c1", {"goed": _rij(), "stuk": _rij()})
    conn = db._connect()
    conn.execute("UPDATE beurtbewijs SET lineage = 'geen json' WHERE tekst_hash = 'stuk'")
    conn.commit()
    conn.close()

    assert set(db.beurtbewijs_voor("alice", "c1")) == {"goed"}


def test_een_gesprek_verwijderen_verwijdert_zijn_rijen(db):
    db.upsert_conversation("alice", "c1", "Titel", 1000, [])
    db.save_beurtbewijs("alice", "c1", {"h1": _rij()})
    db.save_beurtbewijs("alice", "c2", {"h2": _rij()})
    db.save_beurtbewijs("bob", "c1", {"h3": _rij()})

    db.delete_conversation("alice", "c1")

    assert db.beurtbewijs_voor("alice", "c1") == {}
    assert set(db.beurtbewijs_voor("alice", "c2")) == {"h2"}
    assert set(db.beurtbewijs_voor("bob", "c1")) == {"h3"}


def test_ruim_gesprek_op_telt_per_tabel(db):
    db.save_recipes("alice", "c1", {"k": {"laad": ["x", {}]}})
    db.save_beurtbewijs("alice", "c1", {"h1": _rij(), "h2": _rij()})

    with db._connection() as conn:
        aantallen = db.ruim_gesprek_op(conn, "alice", "c1")
        conn.commit()

    assert aantallen == {"data_recipes": 1, "beurtbewijs": 2}


def test_init_db_is_herhaalbaar(db):
    db.save_beurtbewijs("alice", "c1", {"h1": _rij()})
    db.init_db()
    db.init_db()

    assert set(db.beurtbewijs_voor("alice", "c1")) == {"h1"}


def test_een_bestaande_database_zonder_de_tabel_krijgt_hem(tmp_path, monkeypatch):
    pad = tmp_path / "oud.db"
    oud = sqlite3.connect(pad)
    oud.executescript("""
        CREATE TABLE conversations (
            id TEXT NOT NULL, username TEXT NOT NULL, title TEXT NOT NULL,
            timestamp INTEGER NOT NULL, messages TEXT NOT NULL, PRIMARY KEY (id, username)
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

    assert db.beurtbewijs_voor("alice", "c1") == {}
    db.save_beurtbewijs("alice", "c1", {"h1": _rij()})
    assert set(db.beurtbewijs_voor("alice", "c1")) == {"h1"}


def test_een_bestaande_tabel_zonder_controle_krijgt_de_kolom(tmp_path, monkeypatch):
    """Rijen van vóór #876 hebben geen controle-uitkomst: ze krijgen een lege lijst, de rest blijft."""
    pad = tmp_path / "oud.db"
    oud = sqlite3.connect(pad)
    oud.executescript("""
        CREATE TABLE beurtbewijs (
            username TEXT NOT NULL, conv_id TEXT NOT NULL, tekst_hash TEXT NOT NULL, lineage TEXT NOT NULL,
            rekenbewijs TEXT NOT NULL, kaarten TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY (username, conv_id, tekst_hash)
        );
        INSERT INTO beurtbewijs VALUES ('alice', 'c1', 'h1', '{}', '[]', '{}', '2026-11-03T10:00:00+00:00');
    """)
    oud.close()
    monkeypatch.setenv("DATABASE_PATH", str(pad))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    db.init_db()

    assert db.beurtbewijs_voor("alice", "c1")["h1"]["controle"] == []


class _Cursor:
    def __init__(self, log):
        self.log = log

    def execute(self, sql, params=()):
        self.log.append((sql, params))

    def fetchone(self):
        return (1,)

    def close(self):
        pass


class _Conn:
    def __init__(self):
        self.log: list[tuple] = []

    def cursor(self, cursor_factory=None):
        return _Cursor(self.log)

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def postgres(monkeypatch):
    """Een stand-in voor de (optionele) driver: elke verbinding is dezelfde _Conn."""
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
    # Een pool van een eerdere test houdt diens verbinding vast.
    monkeypatch.setattr(db, "_pool", None)
    return conn


def test_postgres_maakt_de_tabel_met_dezelfde_ddl_aan(postgres):
    """De Postgres-tak van init_db voert dezelfde DDL uit als SQLite (#825), met CREATE TABLE IF NOT EXISTS."""
    import persistence.db as db

    db.init_db()

    statements = [" ".join(sql.split()) for sql, _ in postgres.log]
    assert " ".join(db._BEURTBEWIJS_TABLE.split()) in statements
    assert db._BEURTBEWIJS_TABLE in db._SCHEMA
    assert db._BEURTBEWIJS_TABLE.lstrip().startswith("CREATE TABLE IF NOT EXISTS beurtbewijs")
    assert "PRIMARY KEY (username, conv_id, tekst_hash)" in " ".join(db._BEURTBEWIJS_TABLE.split())


def test_postgres_voegt_de_kolom_controle_toe(postgres):
    """Een bestaande tabel van vóór #876 krijgt de kolom; idempotent, dus veilig bij elke start."""
    import persistence.db as db

    db.init_db()

    statements = [" ".join(sql.split()) for sql, _ in postgres.log]
    assert "ALTER TABLE beurtbewijs ADD COLUMN IF NOT EXISTS controle TEXT NOT NULL DEFAULT '[]'" in statements
    assert "controle TEXT NOT NULL DEFAULT '[]'" in " ".join(db._BEURTBEWIJS_TABLE.split())


def test_postgres_schrijft_met_parameters_en_een_upsert(postgres, monkeypatch):
    """De upsert gebruikt ON CONFLICT, dat SQLite en PostgreSQL allebei kennen, en %s-parameters op PostgreSQL."""
    import persistence.db as db

    @contextmanager
    def verbinding():
        yield postgres

    monkeypatch.setattr(db, "_connection", verbinding)

    db.save_beurtbewijs("alice", "c1", {"h1": _rij()})

    sql, params = postgres.log[0]
    assert sql.startswith("INSERT INTO beurtbewijs") and "ON CONFLICT (username, conv_id, tekst_hash)" in sql
    assert "?" not in sql and sql.count("%s") == 8
    assert params[:3] == ("alice", "c1", "h1")
