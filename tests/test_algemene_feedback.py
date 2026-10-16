"""Algemene feedback via de Feedback-link (#600): een idee, probleem of compliment los van een antwoord of rapport."""

import importlib
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from core.algemene_feedback import als_markdown


def _stored() -> list[dict]:
    conn = sqlite3.connect(os.environ["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM algemene_feedback").fetchall()]
    conn.close()
    return rows


def _client(tmp_path, monkeypatch, enabled: str = "true") -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ENABLE_FEEDBACK", enabled)
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    from core import auth, config

    importlib.reload(auth)
    importlib.reload(config)
    from persistence import db

    importlib.reload(db)
    db.init_db()
    from routes import config as config_route
    from routes import feedback as feedback_route

    importlib.reload(config_route)
    importlib.reload(feedback_route)
    import routes

    importlib.reload(routes)
    import server

    importlib.reload(server)
    return TestClient(server.app)


@pytest.fixture
def client(tmp_path, monkeypatch):
    return _client(tmp_path, monkeypatch)


def test_een_bericht_wordt_bewaard_met_soort_en_pagina(client):
    resp = client.post(
        "/api/feedback/algemeen", json={"tekst": "  Graag ook vo-cijfers  ", "soort": "idee", "pagina": "/rapporten"}
    )

    assert resp.status_code == 200
    [rij] = _stored()
    assert (rij["username"], rij["soort"], rij["tekst"], rij["pagina"]) == (
        "gast",
        "idee",
        "Graag ook vo-cijfers",
        "/rapporten",
    )
    assert rij["created_at"]


def test_soort_is_optioneel(client):
    assert client.post("/api/feedback/algemeen", json={"tekst": "Fijne tool", "pagina": "/"}).status_code == 200
    assert _stored()[0]["soort"] == ""


@pytest.mark.parametrize(
    "body",
    [
        {"tekst": "", "pagina": "/chat"},
        {"tekst": "   ", "pagina": "/chat"},
        {"tekst": "x" * 2001, "pagina": "/chat"},
        {"tekst": "ok", "soort": "klacht", "pagina": "/chat"},
        {"tekst": "ok", "pagina": "https://elders.example/pad"},
        {"tekst": "ok", "pagina": "/chat?id=geheim"},
        {"tekst": "ok", "pagina": "/" + "a" * 60},
    ],
)
def test_ongeldige_inzending_wordt_geweigerd(client, body):
    assert client.post("/api/feedback/algemeen", json=body).status_code == 422
    assert _stored() == []


def test_staat_uit_met_de_feedbackschakelaar(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, enabled="false")
    assert client.post("/api/feedback/algemeen", json={"tekst": "Hallo", "pagina": "/"}).status_code == 404


def test_is_begrensd_per_gebruiker(client):
    for _ in range(10):
        assert client.post("/api/feedback/algemeen", json={"tekst": "nog een idee", "pagina": "/"}).status_code == 200
    resp = client.post("/api/feedback/algemeen", json={"tekst": "nog een idee", "pagina": "/"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_overzicht_voor_het_team_nieuwste_eerst():
    rijen = [
        {
            "created_at": "2026-10-16T12:00:00+00:00",
            "username": "demo",
            "soort": "probleem",
            "pagina": "/chat",
            "tekst": "De grafiek laadt niet",
        },
        {"created_at": "2026-10-15T09:00:00+00:00", "username": "gast", "soort": "", "pagina": "/", "tekst": "Mooi"},
    ]
    tekst = als_markdown(rijen)
    assert tekst.index("De grafiek laadt niet") < tekst.index("Mooi")
    assert "probleem" in tekst and "/chat" in tekst and "demo" in tekst


def test_overzicht_zonder_berichten():
    assert als_markdown([]) == "Nog geen algemene feedback.\n"


def test_alle_berichten_voor_het_overzicht(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    db.add_algemene_feedback("alice", "idee", "eerste", "/")
    db.add_algemene_feedback("bob", "", "tweede", "/chat")
    rijen = {r["username"]: r for r in db.all_algemene_feedback()}
    assert (rijen["alice"]["soort"], rijen["alice"]["tekst"], rijen["alice"]["pagina"]) == ("idee", "eerste", "/")
    assert (rijen["bob"]["soort"], rijen["bob"]["tekst"], rijen["bob"]["pagina"]) == ("", "tweede", "/chat")
