"""Test that WebSocket chat sessions persist conversations to the database."""
import contextlib
import importlib
import json

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

        # Het antwoord zelf is hier niet interessant: de sessie wordt pas bij
        # disconnect weggeschreven.
        with contextlib.suppress(Exception):
            websocket.receive_text(timeout=2)

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
        with contextlib.suppress(Exception):
            websocket.receive_text(timeout=1)

    # Check that history was persisted
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    conversations = resp.json()
    assert len(conversations) > 0, "History should be persisted when loading"
    assert conversations[0]["title"] == "Hallo"


def test_conversation_title_strips_markup_and_whitespace():
    from routes.chat import _conversation_title
    messages = [{"role": "user", "content": "<b>Hoeveel</b>\n  studenten?"}]
    assert _conversation_title(messages) == "Hoeveel studenten?"


def test_conversation_title_falls_back_without_user_text():
    from routes.chat import _conversation_title
    assert _conversation_title([{"role": "user", "content": "<img src=x>"}]) == "Untitled"


def _receive_until(websocket, event_type, limit=10):
    for _ in range(limit):
        event = json.loads(websocket.receive_text())
        if event["type"] == event_type:
            return event
    raise AssertionError(f"geen {event_type} ontvangen")


def test_reset_starts_a_fresh_conversation(client):
    """'Nieuw gesprek' must not carry the previous conversation into the next one (#70)."""
    old = [
        {"role": "user", "content": "Hoeveel studenten heeft de RUG?"},
        {"role": "assistant", "content": "Ongeveer 34.000."},
    ]
    new = [{"role": "user", "content": "Welke afkorting noemde ik eerder?"}]

    with client.websocket_connect("/api/chat") as websocket:
        websocket.send_text(json.dumps({"action": "history", "messages": old}))
        websocket.send_text(json.dumps({"action": "reset"}))
        done = _receive_until(websocket, "reset_done")
        assert done["conv_id"]
        # Anything said after the reset lands in a new record, not in the old one.
        websocket.send_text(json.dumps({"action": "history", "messages": new}))
        with contextlib.suppress(Exception):
            websocket.receive_text(timeout=1)

    conversations = {c["title"]: c for c in client.get("/api/conversations").json()}
    assert set(conversations) == {"Hoeveel studenten heeft de RUG?", "Welke afkorting noemde ik eerder?"}
    assert "RUG" not in conversations["Welke afkorting noemde ik eerder?"]["messages"]


def test_reset_session_clears_turns_but_keeps_settings():
    from routes.chat import _new_session, _reset_session
    session = _new_session(username="alice")
    old_id = session["conv_id"]
    session["messages"] = [{"role": "user", "content": "oud"}]
    session["turns"] = [{"question": "oud"}]
    session["_clarified"] = True
    session["chat_settings"] = {"model": "anthropic/claude-opus", "instelling": "RUG"}

    _reset_session(session)

    assert session["messages"] == [] and session["turns"] == []
    assert "_clarified" not in session
    assert session["conv_id"] != old_id
    assert session["username"] == "alice"
    assert session["chat_settings"] == {"model": "anthropic/claude-opus", "instelling": "RUG"}
