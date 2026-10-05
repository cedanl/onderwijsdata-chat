"""Het auth-token staat nooit in een URL: proxy- en serverlogs bewaren query-strings (#103)."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from core.auth import token_uit_protocol


def test_token_uit_het_subprotocol():
    assert token_uit_protocol("bearer, abc.def") == "abc.def"


@pytest.mark.parametrize("header", [None, "", "bearer", "chat, abc.def"])
def test_geen_token_zonder_bearer_subprotocol(header):
    assert token_uit_protocol(header) is None


@pytest.fixture
def ws_client(monkeypatch):
    import routes.chat
    import server

    monkeypatch.setattr(routes.chat, "AUTH_ENABLED", True)
    monkeypatch.setattr(routes.chat, "verify_token", lambda t: "alice" if t == "goed.token" else None)
    return TestClient(server.app)


def test_websocket_accepteert_token_in_het_subprotocol(ws_client):
    with ws_client.websocket_connect("/api/chat", subprotocols=["bearer", "goed.token"]) as ws:
        assert ws.accepted_subprotocol == "bearer"


def test_websocket_negeert_token_in_de_url(ws_client):
    with pytest.raises(WebSocketDisconnect) as exc, ws_client.websocket_connect("/api/chat?token=goed.token") as ws:
        ws.receive_text()
    assert exc.value.code == 4001


def test_rest_negeert_token_in_de_url(monkeypatch, tmp_path):
    import importlib

    import server
    from core import auth
    from persistence import db

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    importlib.reload(db)
    db.init_db()
    monkeypatch.setattr(auth, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth, "verify_token", lambda t: "alice" if t == "goed.token" else None)
    client = TestClient(server.app)
    assert client.get("/api/conversations", params={"token": "goed.token"}).status_code == 401
    assert client.get("/api/conversations", headers={"Authorization": "Bearer goed.token"}).status_code == 200
