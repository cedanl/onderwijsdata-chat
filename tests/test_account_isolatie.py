"""Isolatie tussen accounts (#488, privacy H2): wat Anna opslaat, ziet, wijzigt of exporteert Bert niet.

De testomgeving had één gedeeld account, dus dit was nooit getoetst. Hier twee accounts in CHAT_USERS
en elke API die per gebruiker opslaat: gesprekken, werkboeken, rapportfeedback, antwoordfeedback en de
CSV-export. Een vreemde key of een vreemd gesprek krijgt dezelfde 404 als een onbestaand: de API
bevestigt niet dat het bestaat.
"""

import importlib

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from agent import recepten
from tools import store
from tools.store import KeyMeta


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CHAT_USERS", "anna:wachtwoord-a,bert:wachtwoord-b")
    monkeypatch.setenv("CHAT_SECRET", "test-secret-for-tests")
    from core import auth

    importlib.reload(auth)
    import server

    importlib.reload(server)
    store.clear()
    yield TestClient(server.app)
    store.clear()


def _als(client: TestClient, gebruiker: str) -> None:
    """Ingelogd zonder /api/auth/login: de login-limiter telt over de hele testrun mee."""
    from core import auth

    client.headers["Authorization"] = f"Bearer {auth.make_token(gebruiker)}"


_GESPREK = {
    "title": "Studenten HU 2024",
    "timestamp": 1_700_000_000,
    "messages": [
        {"role": "user", "content": "Hoeveel studenten heeft de HU?"},
        {"role": "assistant", "content": "De HU had 36.206 studenten.", "tools": []},
    ],
}
_WERKBOEK = {"title": "Rapport HU", "description": "", "createdAt": "2026-10-14T10:00:00Z"}


def test_gesprekken_zijn_alleen_voor_de_eigenaar(client):
    _als(client, "anna")
    assert client.put("/api/conversations/c1", json=_GESPREK).status_code == 200

    _als(client, "bert")
    assert client.get("/api/conversations").json() == []
    assert client.get("/api/conversations", params={"q": "HU"}).json() == []
    assert client.get("/api/conversations/c1").status_code == 404
    assert client.patch("/api/conversations/c1", json={"title": "van Bert"}).status_code == 404
    assert client.delete("/api/conversations/c1").status_code == 200  # raakt alleen een eigen gesprek

    _als(client, "anna")
    assert [c["id"] for c in client.get("/api/conversations").json()] == ["c1"]
    assert client.get("/api/conversations/c1").json()["title"] == "Studenten HU 2024"


def test_werkboeken_zijn_alleen_voor_de_eigenaar(client):
    _als(client, "anna")
    assert client.put("/api/workbooks/w1", json=_WERKBOEK).status_code == 200

    _als(client, "bert")
    assert client.get("/api/workbooks").json() == []
    assert client.get("/api/workbooks/w1").status_code == 404
    assert client.delete("/api/workbooks/w1").status_code == 200

    _als(client, "anna")
    assert [w["id"] for w in client.get("/api/workbooks").json()] == ["w1"]


def test_rapportfeedback_alleen_op_een_eigen_werkboek(client):
    feedback = {"workbook_id": "w1", "report_type": "report", "report_title": "Rapport HU", "answers": {"nuttig": "4"}}
    _als(client, "anna")
    assert client.put("/api/workbooks/w1", json=_WERKBOEK).status_code == 200

    _als(client, "bert")
    assert client.post("/api/feedback", json=feedback).status_code == 404
    assert client.get("/api/feedback/given").json() == []

    _als(client, "anna")
    assert client.post("/api/feedback", json=feedback).status_code == 200
    assert client.get("/api/feedback/given").json() == ["w1"]

    _als(client, "bert")
    assert client.get("/api/feedback/given").json() == []


def test_antwoordfeedback_alleen_op_een_eigen_gesprek(client):
    oordeel = {"conversation_id": "c1", "message_index": 1, "oordeel": "down", "toelichting": "klopt niet"}
    _als(client, "anna")
    assert client.put("/api/conversations/c1", json=_GESPREK).status_code == 200
    assert client.post("/api/answer-feedback", json=oordeel).status_code == 200

    _als(client, "bert")
    assert client.get("/api/answer-feedback", params={"conversation_id": "c1"}).json() == {}
    assert client.post("/api/answer-feedback", json=oordeel).status_code == 404

    _als(client, "anna")
    assert client.get("/api/answer-feedback", params={"conversation_id": "c1"}).json() == {"1": "down"}


def test_csv_export_alleen_met_een_eigen_recept(client):
    key = "duo:p01hoinges:0"
    store.put(
        key,
        pd.DataFrame({"STUDIEJAAR": [2024], "AANTAL": [36206]}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=0),
    )
    recepten.onthoud("anna", key, {"laad": ["get_duo_data", {"dataset_id": "p01hoinges", "resource": 0}]})

    _als(client, "bert")
    assert client.get("/api/data/csv", params={"key": key}).status_code == 404

    _als(client, "anna")
    export = client.get("/api/data/csv", params={"key": key})
    assert export.status_code == 200
    assert "STUDIEJAAR;AANTAL" in export.text
