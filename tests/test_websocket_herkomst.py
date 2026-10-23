"""De chat-WebSocket alleen vanaf de eigen origin (#682).

CORS geldt niet voor WebSockets: de browser stuurt Origin mee, maar de server moet hem zelf controleren. Het
token is het eerste slot; zonder login (lokaal, demo) is dit het enige, en anders kon elke site die de
gebruiker open had een chatverbinding naar de app openen.
"""

import importlib

import pytest
from starlette.websockets import WebSocketDisconnect

from core.herkomst import origin_toegestaan

HOST = "onderwijsdata-chat.test.sdp.surf.nl"


@pytest.mark.parametrize(
    "origin, verwacht",
    [
        (None, True),  # geen browser
        (f"https://{HOST}", True),
        ("https://elders.example", False),
        ("null", False),  # een frame met een opake origin, zoals het rapportframe
        (f"https://{HOST}.elders.example", False),
        ("http://localhost:5173", False),
    ],
)
def test_alleen_de_eigen_origin(origin, verwacht):
    assert origin_toegestaan(origin, HOST, [], lokaal=False) is verwacht


def test_een_ingestelde_cors_origin_mag_ook():
    assert origin_toegestaan("https://andere.surf.nl", HOST, ["https://andere.surf.nl"], lokaal=False)


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_lokaal_mag_de_vite_devserver(origin):
    """Vite proxiet met changeOrigin: Host wordt localhost:8000, Origin blijft de devserver."""
    assert origin_toegestaan(origin, "localhost:8000", [], lokaal=True)
    assert not origin_toegestaan("https://elders.example", "localhost:8000", [], lokaal=True)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    from core import auth

    importlib.reload(auth)
    from persistence import db

    importlib.reload(db)
    db.init_db()
    import server

    importlib.reload(server)
    from fastapi.testclient import TestClient

    return TestClient(server.app)


def test_de_chat_weigert_een_verbinding_van_een_andere_site(client):
    with (
        pytest.raises(WebSocketDisconnect) as dicht,
        client.websocket_connect("/api/chat", headers={"Origin": "https://elders.example"}) as ws,
    ):
        ws.receive_text()
    assert dicht.value.code == 4003


def test_de_chat_neemt_een_verbinding_van_de_eigen_origin_aan(client):
    with client.websocket_connect("/api/chat", headers={"Origin": "http://testserver"}) as ws:
        ws.send_text('{"action": "ping"}')
        assert any('"pong"' in ws.receive_text() for _ in range(3))
