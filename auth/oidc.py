"""
SRAM OIDC authentication (CEDA convention — see skill `sram-oidc`).

Auth is opt-in: it activates only when OIDC_PROVIDER is set. When it's not,
`is_oidc_configured()` returns False and the app stays on CHAT_USERS auth
(or fully open, if neither is set) — see core/auth.py.

Flow: authorization-code OIDC against the SRAM proxy's discovery document.
On success we mint the same signed token core/auth.py already uses for
CHAT_USERS logins (core.auth.make_token), so the rest of the app — the
get_current_user dependency, the frontend's Bearer-token handling — is
completely unaware whether a token came from a password login or SRAM.
"""

import logging
import time
from typing import Optional

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from config import Config

logger = logging.getLogger(__name__)

OAUTH_SCOPES = "openid email profile"
_DISCOVERY_CACHE_TTL = 3600  # discovery documents don't change; cache for an hour

_discovery_cache: Optional[dict] = None
_discovery_cache_at: float = 0.0


def is_oidc_configured() -> bool:
    """Check if SRAM OIDC is configured (CEDA convention: gated on OIDC_PROVIDER)."""
    return bool(
        Config.OIDC_PROVIDER
        and Config.OIDC_DISCOVERY_URL
        and Config.OIDC_CLIENT_ID
        and Config.OIDC_CLIENT_SECRET
        and Config.SERVER_URL
    )


def _redirect_uri() -> str:
    return Config.SERVER_URL.rstrip("/") + "/" + Config.SERVER_REDIRECT.lstrip("/")


async def _get_discovery_config() -> dict:
    global _discovery_cache, _discovery_cache_at
    now = time.time()
    if _discovery_cache and (now - _discovery_cache_at) < _DISCOVERY_CACHE_TTL:
        return _discovery_cache
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(Config.OIDC_DISCOVERY_URL)
        response.raise_for_status()
        _discovery_cache = response.json()
        _discovery_cache_at = now
        return _discovery_cache


async def build_authorization_url(state: str) -> str:
    """Build the SRAM authorization redirect URL for the given CSRF state."""
    oidc_config = await _get_discovery_config()
    client = AsyncOAuth2Client(
        Config.OIDC_CLIENT_ID,
        Config.OIDC_CLIENT_SECRET,
        redirect_uri=_redirect_uri(),
        scope=OAUTH_SCOPES,
    )
    auth_url, _ = client.create_authorization_url(
        oidc_config["authorization_endpoint"], state=state
    )
    return auth_url


async def exchange_code_for_user(code: str) -> dict:
    """Exchange an authorization code for the SRAM user's profile (email, name, sub)."""
    oidc_config = await _get_discovery_config()
    client = AsyncOAuth2Client(
        Config.OIDC_CLIENT_ID,
        Config.OIDC_CLIENT_SECRET,
        redirect_uri=_redirect_uri(),
    )
    token = await client.fetch_token(oidc_config["token_endpoint"], code=code)
    userinfo_response = await client.get(
        oidc_config["userinfo_endpoint"],
        headers={"Authorization": f"Bearer {token['access_token']}"},
    )
    userinfo_response.raise_for_status()
    return userinfo_response.json()
