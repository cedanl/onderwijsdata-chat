import importlib
import os

import pytest


def test_token_sign_uses_configured_secret(monkeypatch):
    monkeypatch.setenv("CHAT_SECRET", "test-secret-value")
    import core.auth as auth
    importlib.reload(auth)
    sig1 = auth._token_sign("payload1")
    sig2 = auth._token_sign("payload1")
    assert sig1 == sig2

    monkeypatch.setenv("CHAT_SECRET", "different-secret")
    importlib.reload(auth)
    sig3 = auth._token_sign("payload1")
    assert sig3 != sig1


def test_fallback_secret_blocked_when_auth_enabled(monkeypatch):
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    monkeypatch.setenv("CHAT_USERS", "admin:pass")
    import core.auth as auth
    with pytest.raises(ValueError, match="CHAT_SECRET"):
        importlib.reload(auth)


def test_fallback_secret_allowed_when_auth_disabled(monkeypatch):
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    monkeypatch.delenv("CHAT_USERS", raising=False)
    import core.auth as auth
    importlib.reload(auth)
    assert auth._TOKEN_SECRET is not None
