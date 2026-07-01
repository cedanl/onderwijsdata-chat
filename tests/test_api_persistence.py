import importlib
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    import core.auth as auth
    importlib.reload(auth)
    from persistence import db
    importlib.reload(db)
    db.init_db()
    import server
    importlib.reload(server)
    return TestClient(server.app)


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CHAT_USERS", "testuser:testpass")
    monkeypatch.setenv("CHAT_SECRET", "test-secret-for-tests")
    import core.auth as auth
    importlib.reload(auth)
    from persistence import db
    importlib.reload(db)
    db.init_db()
    import server
    importlib.reload(server)
    c = TestClient(server.app)
    resp = c.post("/api/auth/login", json={"username": "testuser", "password": "testpass"})
    token = resp.json()["token"]
    c.headers["Authorization"] = f"Bearer {token}"
    return c


# ── Conversations (no auth) ──────────────────────────────────────────────────

def test_get_conversations_empty(client):
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_put_and_get_conversation(client):
    body = {"title": "Test", "timestamp": 1000, "messages": [{"role": "user", "content": "hi"}]}
    resp = client.put("/api/conversations/c1", json=body)
    assert resp.status_code == 200

    resp = client.get("/api/conversations")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "c1"
    assert data[0]["title"] == "Test"


def test_delete_conversation(client):
    client.put("/api/conversations/c1", json={"title": "X", "timestamp": 1, "messages": []})
    resp = client.delete("/api/conversations/c1")
    assert resp.status_code == 200
    assert client.get("/api/conversations").json() == []


# ── Workbooks (no auth) ──────────────────────────────────────────────────────

def test_get_workbooks_empty(client):
    resp = client.get("/api/workbooks")
    assert resp.status_code == 200
    assert resp.json() == []


def test_put_and_get_workbook(client):
    body = {
        "title": "Dashboard",
        "description": "test",
        "messages": [{"role": "user", "content": "data"}],
        "figures": [],
        "instelling": "HU",
        "htmlContent": "<html></html>",
        "createdAt": "2024-01-01T00:00:00Z",
    }
    resp = client.put("/api/workbooks/wb1", json=body)
    assert resp.status_code == 200

    resp = client.get("/api/workbooks")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "wb1"
    assert data[0]["title"] == "Dashboard"


def test_delete_workbook(client):
    client.put("/api/workbooks/wb1", json={
        "title": "X", "description": "", "createdAt": "2024-01-01T00:00:00Z",
    })
    resp = client.delete("/api/workbooks/wb1")
    assert resp.status_code == 200
    assert client.get("/api/workbooks").json() == []


# ── Auth enforcement ──────────────────────────────────────────────────────────

def test_auth_enabled_no_token_returns_401(authed_client):
    c = TestClient(authed_client.app)
    resp = c.get("/api/conversations")
    assert resp.status_code == 401


def test_auth_enabled_with_token_works(authed_client):
    authed_client.put("/api/conversations/c1", json={"title": "T", "timestamp": 1, "messages": []})
    resp = authed_client.get("/api/conversations")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
