import importlib
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    # Reload auth first (reads env at module level), then server (imports from auth)
    import core.auth as auth
    importlib.reload(auth)
    import server
    importlib.reload(server)
    return TestClient(server.app)


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_returns_status_ok(client):
    resp = client.get("/health")
    data = resp.json()
    assert data["status"] == "ok"


def test_version_returns_200(client):
    resp = client.get("/version")
    assert resp.status_code == 200


def test_version_returns_version_string(client):
    resp = client.get("/version")
    data = resp.json()
    assert "version" in data
    assert isinstance(data["version"], str)
    assert len(data["version"].split(".")) >= 2
