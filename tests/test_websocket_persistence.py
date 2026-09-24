"""The WebSocket session: what it keeps between messages, and what it leaves to the frontend."""
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


def test_websocket_leaves_saving_to_the_frontend(client):
    """The frontend saves each conversation under one id, with figures (#69, #120).

    A second writer here created a text-only copy under its own id, so every
    conversation showed up twice and reopened without its figures.
    """
    history = [{"role": "user", "content": "Hallo"}, {"role": "assistant", "content": "Hoi!"}]
    with client.websocket_connect("/api/chat") as websocket:
        websocket.send_text(json.dumps({"action": "history", "messages": history}))
        websocket.send_text(json.dumps({"action": "reset"}))
        websocket.receive_text()
        websocket.send_text(json.dumps({"action": "message", "content": "Wat is 2+2?"}))
        with contextlib.suppress(Exception):
            websocket.receive_text(timeout=2)

    assert client.get("/api/conversations").json() == []


def test_opening_a_conversation_starts_a_fresh_session():
    from routes.chat import _new_session, _open_conversation
    session = _new_session(username="alice")
    session["turns"] = [{"question": "vorig gesprek"}]
    session["data_keys"] = ["rio:erkenningen"]
    session["chat_settings"] = {"instelling": "RUG"}

    _open_conversation(session, [
        {"role": "user", "content": "Hoeveel studenten heeft de HU?"},
        {"role": "assistant", "content": "26.370", "figures": ["{}"]},
    ])

    assert session["turns"] == [] and session["data_keys"] == []
    assert session["messages"] == [
        {"role": "user", "content": "Hoeveel studenten heeft de HU?"},
        {"role": "assistant", "content": "26.370"},
    ]
    assert session["chat_settings"] == {"instelling": "RUG"}


def test_reset_session_clears_turns_but_keeps_settings():
    from routes.chat import _new_session, _reset_session
    session = _new_session(username="alice")
    session["messages"] = [{"role": "user", "content": "oud"}]
    session["turns"] = [{"question": "oud"}]
    session["data_keys"] = ["cbs:85423NED"]
    session["_clarified"] = True
    session["chat_settings"] = {"model": "anthropic/claude-opus", "instelling": "RUG"}

    _reset_session(session)

    assert session["messages"] == [] and session["turns"] == [] and session["data_keys"] == []
    assert "_clarified" not in session
    assert session["username"] == "alice"
    assert session["chat_settings"] == {"model": "anthropic/claude-opus", "instelling": "RUG"}
