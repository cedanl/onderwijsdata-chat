"""Test that WebSocket chat sessions persist conversations to the database."""
import json
import importlib
import pytest


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


def test_websocket_persists_conversation(client):
    """Verify that messages sent via WebSocket are persisted to the database."""
    with client.websocket_connect("/api/chat") as websocket:
        websocket.send_text(json.dumps({
            "action": "message",
            "content": "What is 2+2?"
        }))

        # Receive response (might not get full response in test, but session saves on disconnect)
        try:
            response = websocket.receive_text(timeout=2)
            print(f"Received: {response}")
        except:
            pass

    # After WebSocket disconnect, check if conversation was persisted
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    conversations = resp.json()

    # Should have at least one conversation saved
    assert len(conversations) > 0, "Conversation should be persisted to database after WebSocket disconnect"

    # First conversation should have our message
    conv = conversations[0]
    assert "2+2" in conv["title"], "Title should contain first user message"


def test_websocket_persists_with_history_action(client):
    """Verify that loading history persists the conversation."""
    messages = [
        {"role": "user", "content": "Hallo"},
        {"role": "assistant", "content": "Hoi!"}
    ]

    with client.websocket_connect("/api/chat") as websocket:
        websocket.send_text(json.dumps({
            "action": "history",
            "messages": messages
        }))
        try:
            websocket.receive_text(timeout=1)
        except:
            pass

    # Check that history was persisted
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    conversations = resp.json()
    assert len(conversations) > 0, "History should be persisted when loading"
    assert conversations[0]["title"] == "Hallo"
