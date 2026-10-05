"""Feedback per antwoord, met de tool-trace als reproduceerbaar bugrapport (#248).

De trace komt uit het opgeslagen gesprek van de gebruiker zelf, niet uit het
verzoek: zo hoort een 👎 altijd bij een echt antwoord, en kan niemand feedback
bij andermans gesprek opslaan.
"""

import importlib
import json

import pytest
from fastapi.testclient import TestClient

from core.answer_feedback import als_markdown, antwoord_trace

GESPREK = [
    {"id": 1, "role": "user", "content": "Hoeveel studenten heeft de HU?"},
    {
        "id": 2,
        "role": "assistant",
        "content": "De HU had 38.000 studenten.",
        "done": True,
        "controle": ["2025 staat niet in de data"],
        "tools": [
            {"name": "get_duo_data", "label": "Data opgehaald", "done": True, "snippet": "df = laad()"},
            {"name": "query_data", "label": "Data gefilterd", "done": True, "status": "empty", "snippet": None},
        ],
    },
    {"id": 1, "role": "user", "content": "En de HAN?"},
    {"id": 2, "role": "assistant", "content": "Er ging iets mis.", "isError": True, "done": True},
]


# ── De trace ─────────────────────────────────────────────────────────────────


def test_trace_bevat_vraag_antwoord_stappen_en_controle():
    trace = antwoord_trace(GESPREK, 1)
    assert trace == {
        "vraag": "Hoeveel studenten heeft de HU?",
        "antwoord": "De HU had 38.000 studenten.",
        "controle": ["2025 staat niet in de data"],
        "stappen": [
            {"name": "get_duo_data", "label": "Data opgehaald", "status": None, "snippet": "df = laad()"},
            {"name": "query_data", "label": "Data gefilterd", "status": "empty", "snippet": None},
        ],
    }


def test_alleen_een_afgerond_antwoord_heeft_een_trace():
    assert antwoord_trace(GESPREK, 0) is None  # een vraag
    assert antwoord_trace(GESPREK, 3) is None  # een foutmelding
    assert antwoord_trace(GESPREK, 9) is None
    assert antwoord_trace(GESPREK, -1) is None


def test_overzicht_voor_het_team_is_reproduceerbaar():
    rij = {
        "username": "anna",
        "conversation_id": "c1",
        "message_index": 1,
        "oordeel": "down",
        "toelichting": "HU had er 40.000",
        "trace": json.dumps(antwoord_trace(GESPREK, 1)),
        "created_at": "2026-10-05T20:00:00+00:00",
    }
    tekst = als_markdown([rij])
    assert tekst.startswith("## 👎 2026-10-05T20:00:00+00:00 · anna · gesprek c1")
    assert "> HU had er 40.000" in tekst
    assert "**Vraag:** Hoeveel studenten heeft de HU?" in tekst
    assert "2. Data gefilterd (empty)" in tekst
    assert "```python\ndf = laad()\n```" in tekst


def test_leeg_overzicht():
    assert als_markdown([]) == "Nog geen feedback.\n"


# ── Endpoint ─────────────────────────────────────────────────────────────────


def _client(tmp_path, monkeypatch, users="anna:pw1,bob:pw2", enabled="true"):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CHAT_USERS", users)
    monkeypatch.setenv("CHAT_SECRET", "test-secret-for-tests")
    monkeypatch.setenv("ENABLE_FEEDBACK", enabled)
    from core import auth, config

    importlib.reload(config)
    importlib.reload(auth)
    from persistence import db

    importlib.reload(db)
    db.init_db()
    import routes.answer_feedback
    import server

    importlib.reload(routes.answer_feedback)
    importlib.reload(server)
    # Elke test logt in; de loginlimiet (5 per minuut per IP) hoort niet bij wat hier getest wordt.
    import routes.auth
    from core.rate_limit import RateLimiter

    monkeypatch.setattr(routes.auth, "_login_limiter", RateLimiter(max_attempts=1000, window_seconds=60))
    return TestClient(server.app), db


def _als(client, user, pw):
    token = client.post("/api/auth/login", json={"username": user, "password": pw}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
def app(tmp_path, monkeypatch):
    client, db = _client(tmp_path, monkeypatch)
    db.upsert_conversation("anna", "c1", "HU", 1_700_000_000, GESPREK)
    return client, db


def test_duim_omlaag_slaat_trace_en_toelichting_op(app):
    client, db = app
    _als(client, "anna", "pw1")
    resp = client.post(
        "/api/answer-feedback",
        json={"conversation_id": "c1", "message_index": 1, "oordeel": "down", "toelichting": "HU had er 40.000"},
    )
    assert resp.status_code == 200
    [rij] = db.all_answer_feedback()
    assert rij["username"] == "anna"
    assert rij["conversation_id"] == "c1"
    assert rij["message_index"] == 1
    assert rij["oordeel"] == "down"
    assert rij["toelichting"] == "HU had er 40.000"
    assert json.loads(rij["trace"])["stappen"][0]["snippet"] == "df = laad()"


def test_een_nieuw_oordeel_vervangt_het_oude(app):
    client, db = app
    _als(client, "anna", "pw1")
    for oordeel in ("down", "up"):
        client.post("/api/answer-feedback", json={"conversation_id": "c1", "message_index": 1, "oordeel": oordeel})
    assert [r["oordeel"] for r in db.all_answer_feedback()] == ["up"]


def test_oordelen_per_gesprek_ophalen_ook_na_heropenen(app):
    client, _ = app
    _als(client, "anna", "pw1")
    client.post("/api/answer-feedback", json={"conversation_id": "c1", "message_index": 1, "oordeel": "up"})
    assert client.get("/api/answer-feedback", params={"conversation_id": "c1"}).json() == {"1": "up"}


def test_feedback_bij_andermans_gesprek_kan_niet(app):
    client, db = app
    _als(client, "bob", "pw2")
    resp = client.post("/api/answer-feedback", json={"conversation_id": "c1", "message_index": 1, "oordeel": "down"})
    assert resp.status_code == 404
    assert db.all_answer_feedback() == []
    assert client.get("/api/answer-feedback", params={"conversation_id": "c1"}).json() == {}


def test_feedback_op_iets_anders_dan_een_antwoord_kan_niet(app):
    client, _ = app
    _als(client, "anna", "pw1")
    for index in (0, 3, 9):
        resp = client.post(
            "/api/answer-feedback", json={"conversation_id": "c1", "message_index": index, "oordeel": "up"}
        )
        assert resp.status_code == 404


def test_alleen_duim_omhoog_of_omlaag(app):
    client, _ = app
    _als(client, "anna", "pw1")
    resp = client.post("/api/answer-feedback", json={"conversation_id": "c1", "message_index": 1, "oordeel": "meh"})
    assert resp.status_code == 422


def test_toelichting_is_begrensd(app):
    client, _ = app
    _als(client, "anna", "pw1")
    resp = client.post(
        "/api/answer-feedback",
        json={"conversation_id": "c1", "message_index": 1, "oordeel": "down", "toelichting": "x" * 2001},
    )
    assert resp.status_code == 422


def test_uitgeschakeld_zonder_endpoint(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch, enabled="false")
    _als(client, "anna", "pw1")
    assert client.get("/api/answer-feedback", params={"conversation_id": "c1"}).status_code == 404
