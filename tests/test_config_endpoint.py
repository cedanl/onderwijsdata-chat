"""GET /api/config publishes the message limit to the composer (#501)."""

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
