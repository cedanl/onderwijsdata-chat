import base64
import hashlib
import hmac
import math
import os
import time
from typing import Annotated

from fastapi import Header, HTTPException

from persistence import db

_TOKEN_SECRET_RAW = os.getenv("CHAT_SECRET", "")


def _uren_uit_env(naam: str, standaard: int) -> int:
    """Een duur in uren uit de env, in seconden; een ongeldige waarde laat de start falen."""
    raw = os.getenv(naam, "").strip()
    if not raw:
        return standaard * 3600
    try:
        uren = float(raw)
    except ValueError:
        uren = math.nan
    if not math.isfinite(uren) or int(uren * 3600) < 1:
        raise ValueError(f"{naam} moet een positief aantal uren zijn (bijvoorbeeld 8), niet {raw!r}.")
    return int(uren * 3600)


# Een token is SESSION_TTL geldig; verversen kan tot SESSION_MAX na het inloggen (#479).
SESSION_TTL = _uren_uit_env("SESSION_TTL_HOURS", 8)
SESSION_MAX = _uren_uit_env("SESSION_MAX_HOURS", 24)
# Tokens van vóór #479 ("<user>|<exp>") hadden geen sessiestart; ze golden 24 uur.
_OUDE_TTL = 24 * 3600


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


def make_token(username: str, start: int | None = None) -> str:
    """Payload "<user>|<start>|<exp>": exp blijft het laatste veld (frontend/src/auth.js leest het).

    start is het moment van inloggen; een ververst token houdt het, zodat exp nooit voorbij
    start + SESSION_MAX komt.
    """
    now = int(time.time())
    start = now if start is None else start
    exp = min(now + SESSION_TTL, start + SESSION_MAX)
    payload = base64.urlsafe_b64encode(f"{username}|{start}|{exp}".encode()).decode().rstrip("=")
    return f"{payload}.{_token_sign(payload)}"


def _parse_claims(decoded: str) -> tuple[str, int, int] | None:
    user, *getallen = decoded.rsplit("|", 2)
    if len(getallen) == 2 and all(_is_geheel(g) for g in getallen):
        return user, int(getallen[0]), int(getallen[1])
    user, sep, exp = decoded.rpartition("|")
    if not sep or not _is_geheel(exp):
        return None
    return user, int(exp) - _OUDE_TTL, int(exp)


def _is_geheel(tekst: str) -> bool:
    try:
        int(tekst)
    except ValueError:
        return False
    return True


def _decode(token: str) -> tuple[str, int, int] | None:
    """(user, start, exp) uit een token met een geldige handtekening, nieuw of oud formaat; anders None."""
    payload, sep, sig = token.rpartition(".")
    if not sep or not hmac.compare_digest(_token_sign(payload).encode(), sig.encode()):
        return None
    try:
        decoded = base64.urlsafe_b64decode(payload + "==").decode()
    except ValueError:
        return None
    return _parse_claims(decoded)


def _geldige_claims(token: str) -> tuple[str, int, int] | None:
    claims = _decode(token)
    if claims is None or claims[2] < time.time():
        return None
    return claims


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str) -> str | None:
    """De gebruiker bij een ondertekend, niet verlopen en niet ingetrokken token, anders None.

    Een databasefout bij de denylist gaat als uitzondering door (500), niet als None (401):
    een storing is geen "sessie voorbij".
    """
    claims = _geldige_claims(token)
    if claims is None or db.is_token_revoked(_token_hash(token)):
        return None
    return claims[0]


def session_start(token: str) -> int | None:
    """Het inlogmoment van een ondertekend, niet verlopen token, of None."""
    claims = _geldige_claims(token)
    return claims[1] if claims else None


def revoke_token(token: str) -> None:
    """Uitloggen: zet een geldig token tot zijn exp op de denylist.

    Zonder login, of bij een ongeldig, verlopen of al ingetrokken token gebeurt er niets.
    """
    if not AUTH_ENABLED:
        return
    claims = _geldige_claims(token)
    token_hash = _token_hash(token)
    if claims and not db.is_token_revoked(token_hash):
        db.revoke_token_hash(token_hash, claims[2])


USERS = parse_users(os.getenv("CHAT_USERS", ""))
OIDC_ENABLED = bool(os.getenv("OIDC_PROVIDER"))
AUTH_ENABLED = bool(USERS) or OIDC_ENABLED

if AUTH_ENABLED and not _TOKEN_SECRET_RAW:
    raise ValueError(
        "CHAT_SECRET moet ingesteld zijn wanneer CHAT_USERS of OIDC_PROVIDER is geconfigureerd. "
        'Genereer een willekeurige waarde: python -c "import secrets; print(secrets.token_hex(32))"'
    )

_TOKEN_SECRET = _TOKEN_SECRET_RAW.encode() or b"dev-only-no-secret-set"

FALLBACK_USER = "gast"


# Het token komt alleen via een header: een query-string belandt in proxy- en serverlogs (#103).
def _resolve_user(authorization: str | None) -> str | None:
    if not AUTH_ENABLED:
        return FALLBACK_USER
    return verify_token(bearer_token(authorization))


def bearer_token(authorization: str | None) -> str:
    """Het token uit een "Bearer <token>"-header, of "" zonder."""
    return authorization.removeprefix("Bearer ") if authorization and authorization.startswith("Bearer ") else ""


# Een browser kan bij een WebSocket geen header meegeven, wel subprotocollen: ["bearer", token].
WS_SUBPROTOCOL = "bearer"


def token_uit_protocol(header: str | None) -> str | None:
    """Het token uit Sec-WebSocket-Protocol "bearer, <token>", of None."""
    delen = [d.strip() for d in (header or "").split(",")]
    if len(delen) == 2 and delen[0] == WS_SUBPROTOCOL and delen[1]:
        return delen[1]
    return None


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> str:
    """FastAPI dependency. Raises 401 when token ontbreekt of ongeldig is."""
    username = _resolve_user(authorization)
    if not username:
        raise HTTPException(status_code=401, detail="Niet geautoriseerd")
    return username


def get_optional_user(authorization: Annotated[str | None, Header()] = None) -> str | None:
    """FastAPI dependency — retourneert gebruikersnaam of None (geen 401)."""
    return _resolve_user(authorization)
