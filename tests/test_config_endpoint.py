"""GET /api/config publishes the message limit (#501) and the context limits (#789) to the frontend."""

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import config
from routes import config as config_route


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(config_route.router)
    return TestClient(app)


def test_config_publishes_max_message_chars(client):
    body = client.get("/api/config").json()
    assert body["max_message_chars"] == config.MAX_MESSAGE_CHARS


def test_config_follows_an_overridden_max_message_chars(client, monkeypatch):
    monkeypatch.setattr(config_route, "MAX_MESSAGE_CHARS", 1234)
    assert client.get("/api/config").json()["max_message_chars"] == 1234


def test_config_publishes_the_context_limits(client):
    body = client.get("/api/config").json()
    assert body["max_chat_turns"] == config.MAX_CHAT_TURNS
    assert body["max_history"] == config.MAX_HISTORY


def test_config_follows_overridden_context_limits(client, monkeypatch):
    monkeypatch.setattr(config_route, "MAX_CHAT_TURNS", 7)
    monkeypatch.setattr(config_route, "MAX_HISTORY", 14)
    body = client.get("/api/config").json()
    assert (body["max_chat_turns"], body["max_history"]) == (7, 14)


@pytest.mark.parametrize(("max_history", "max_chat_turns"), [("40", 20), ("41", 20), ("10", 5), ("1", 1), ("0", 1)])
def test_a_chat_turn_is_two_messages(monkeypatch, max_history, max_chat_turns):
    """#789: MAX_CHAT_TURNS volgt MAX_HISTORY (een vraag en zijn antwoord), minimaal één vraag."""
    monkeypatch.setenv("MAX_HISTORY", max_history)
    try:
        importlib.reload(config)
        assert max_chat_turns == config.MAX_CHAT_TURNS
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_config_publishes_retention_and_session_terms(client):
    """#835: de frontend noemt de bewaartermijnen en de sessieduur die de backend toepast, niet vaste getallen."""
    body = client.get("/api/config").json()
    assert body["bewaartermijn_gesprekken_dagen"] == int(config.BEWAARTERMIJN_GESPREKKEN_DAGEN)
    assert body["bewaartermijn_rapporten_dagen"] == int(config.BEWAARTERMIJN_RAPPORTEN_DAGEN)
    assert body["sessie_uren"] == 8
    assert body["sessie_max_uren"] == 24


def test_config_follows_overridden_terms(client, monkeypatch):
    monkeypatch.setattr(config, "BEWAARTERMIJN_GESPREKKEN_DAGEN", "30")
    monkeypatch.setattr(config, "BEWAARTERMIJN_RAPPORTEN_DAGEN", "180")
    monkeypatch.setattr(config_route, "SESSION_TTL", 2 * 3600)
    monkeypatch.setattr(config_route, "SESSION_MAX", 12 * 3600)
    body = client.get("/api/config").json()
    assert (body["bewaartermijn_gesprekken_dagen"], body["bewaartermijn_rapporten_dagen"]) == (30, 180)
    assert (body["sessie_uren"], body["sessie_max_uren"]) == (2, 12)


def test_config_gives_no_retention_term_the_cleanup_rejects(client, monkeypatch):
    """Een termijn die persistence/opschonen.py weigert (die verwijdert dan niets), komt niet als getal mee."""
    monkeypatch.setattr(config, "BEWAARTERMIJN_GESPREKKEN_DAGEN", "3")
    body = client.get("/api/config").json()
    assert body["bewaartermijn_gesprekken_dagen"] is None
    assert body["bewaartermijn_rapporten_dagen"] is None
