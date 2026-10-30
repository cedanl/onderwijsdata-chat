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
