import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    # Reload auth first (reads env at module level), then server (imports from auth)
    from core import auth

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


def test_version_noemt_de_commit_uit_het_image(client, monkeypatch):
    # #231: zonder commit was niet vast te stellen welke code een omgeving draait.
    from config import Config

    monkeypatch.setattr(Config, "GIT_COMMIT", "021632f")
    assert client.get("/version").json()["commit"] == "021632f"


def test_version_zonder_build_arg_zegt_onbekend(client, monkeypatch):
    from config import Config

    monkeypatch.setattr(Config, "GIT_COMMIT", None)
    assert client.get("/version").json()["commit"] == "onbekend"
