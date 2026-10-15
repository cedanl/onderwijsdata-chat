"""Van de sessie naar de database: de recepten achter de tabellen van een opgeslagen gesprek (#472)."""

import importlib

import pytest
from fastapi.testclient import TestClient

from agent import recepten

_CBS = {"laad": ["get_cbs_data", {"dataset_id": "85423NED", "filters": None}]}
_SELECTIE = {"afgeleid_van": "cbs:85423NED", "tool": "query_data", "args": {"filters": {"a": 1}}, "stap": "a = 1"}


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    return db


def test_bewaren_neemt_de_tabellen_van_het_gesprek_en_hun_bron(db):
    recepten.onthoud("alice", "cbs:85423NED", _CBS)
    recepten.onthoud("alice", "cbs:85423NED:ab", _SELECTIE)
    recepten.onthoud("alice", "rio:ander_gesprek", {"laad": ["get_rio_data", {"resource": "x"}]})

    berichten = [
        {"role": "user", "content": "Hoeveel?"},
        {"role": "assistant", "content": "Zoveel.", "tools": [{"name": "query_data", "exportKey": "cbs:85423NED:ab"}]},
    ]
    recepten.bewaar("alice", "c1", berichten)

    assert db.recipes_for("alice", "c1") == {"cbs:85423NED:ab": _SELECTIE, "cbs:85423NED": _CBS}


def test_bewaren_neemt_ook_de_data_van_een_stap_zonder_exporteerbare_tabel(db):
    """#551: een gesprek met alleen een lader en een KPI had geen exportKey en dus geen recept."""
    recepten.onthoud("alice", "cbs:85423NED", _CBS)
    berichten = [
        {"role": "assistant", "content": "Zoveel.", "tools": [{"name": "get_cbs_data", "dataKey": "cbs:85423NED"}]},
        {"role": "assistant", "content": "Nog eens.", "tools": [{"name": "compute_kpi", "dataKey": None}]},
    ]
    recepten.bewaar("alice", "c1", berichten)

    assert db.recipes_for("alice", "c1") == {"cbs:85423NED": _CBS}


def test_datakeys_elk_een_keer_uit_exportkey_en_datakey():
    berichten = [
        {"role": "assistant", "tools": [{"exportKey": "a", "dataKey": "a"}, {"dataKey": "b"}, {"exportKey": "a"}, 3]},
        "geen dict",
    ]
    assert recepten._datakeys(berichten) == ["a", "b"]


def test_bewaren_slaat_geen_recept_van_een_ander_op(db):
    recepten.onthoud("bob", "cbs:85423NED", _CBS)
    recepten.bewaar("alice", "c1", [{"role": "assistant", "tools": [{"exportKey": "cbs:85423NED"}]}])
    assert db.recipes_for("alice", "c1") == {}


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    from core import auth

    importlib.reload(auth)
    import server

    importlib.reload(server)
    return TestClient(server.app)


def test_de_api_bewaart_bij_opslaan_en_vergeet_bij_verwijderen(client, db):
    recepten.onthoud("gast", "cbs:85423NED", _CBS)
    berichten = [{"role": "assistant", "content": "x", "tools": [{"exportKey": "cbs:85423NED"}]}]
    client.put("/api/conversations/c1", json={"title": "T", "timestamp": 1000, "messages": berichten})
    assert db.recipes_for("gast", "c1") == {"cbs:85423NED": _CBS}

    client.delete("/api/conversations/c1")

    assert db.recipes_for("gast", "c1") == {}
    assert recepten.voor("gast", "cbs:85423NED") is None
