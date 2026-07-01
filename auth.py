import base64
import hashlib
import hmac
import os
import time
from typing import Annotated

from fastapi import Header, HTTPException, Query

_TOKEN_SECRET_RAW = os.getenv("CHAT_SECRET", "")
_TOKEN_TTL = 24 * 3600


def parse_users(users_env: str) -> dict[str, str]:
    if not users_env.strip():
        return {}
    result = {}
    for entry in users_env.split(","):
        entry = entry.strip()
        if ":" in entry:
            user, _, password = entry.partition(":")
            result[user.strip()] = password.strip()
    return result


def check_credentials(username: str, password: str, users: dict[str, str]) -> bool:
    stored = users.get(username)
    if stored is None:
        return False
    return hmac.compare_digest(stored, password)


def _token_sign(data: str) -> str:
    return hmac.new(_TOKEN_SECRET, data.encode(), hashlib.sha256).hexdigest()


def make_token(username: str) -> str:
    exp = int(time.time()) + _TOKEN_TTL
    payload = base64.urlsafe_b64encode(f"{username}|{exp}".encode()).decode().rstrip("=")
    return f"{payload}.{_token_sign(payload)}"


def verify_token(token: str) -> str | None:
    try:
        payload, sig = token.rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_token_sign(payload), sig):
        return None
    try:
        decoded = base64.urlsafe_b64decode(payload + "==").decode()
        username, exp_str = decoded.rsplit("|", 1)
        if int(exp_str) < time.time():
            return None
        return username
    except Exception:
        return None


USERS = parse_users(os.getenv("CHAT_USERS", ""))
AUTH_ENABLED = bool(USERS)

if AUTH_ENABLED and not _TOKEN_SECRET_RAW:
    raise ValueError(
        "CHAT_SECRET moet ingesteld zijn wanneer CHAT_USERS is geconfigureerd. "
        "Genereer een willekeurige waarde: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

_TOKEN_SECRET = _TOKEN_SECRET_RAW.encode() or b"dev-only-no-secret-set"

FALLBACK_USER = "gast"


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    token: Annotated[str | None, Query()] = None,
) -> str:
    """FastAPI dependency. Use with Depends(get_current_user).
    Reads token from Authorization header or query param."""
    if not AUTH_ENABLED:
        return FALLBACK_USER
    raw = None
    if authorization and authorization.startswith("Bearer "):
        raw = authorization[7:]
    elif token:
        raw = token
    username = verify_token(raw or "")
    if not username:
        raise HTTPException(status_code=401, detail="Niet geautoriseerd")
    return username
