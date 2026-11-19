"""
SRAM OIDC authentication (CEDA convention — see skill `sram-oidc`).

Auth is opt-in: it activates only when OIDC_PROVIDER is set. When it's not,
`is_oidc_configured()` returns False and the app stays on CHAT_USERS auth
(or fully open, if neither is set) — see core/auth.py.

Flow: authorization-code OIDC against the SRAM proxy's discovery document,
with PKCE (S256) and a nonce (RFC 9700, #1024). The callback validates the
id_token (signature against the discovery JWKS, iss, aud, exp, nonce) and
only accepts a userinfo response whose `sub` matches it (OIDC Core 5.3.2).
On success we mint the same signed token core/auth.py already uses for
CHAT_USERS logins (core.auth.make_token), so the rest of the app — the
get_current_user dependency, the frontend's Bearer-token handling — is
completely unaware whether a token came from a password login or SRAM.
"""

import logging
import secrets
import time
from typing import NamedTuple

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from joserfc import jwt
from joserfc.errors import InvalidKeyIdError, JoseError
from joserfc.jwk import KeySet

from config import Config

logger = logging.getLogger(__name__)

OAUTH_SCOPES = "openid email profile eduperson_entitlement voperson_external_affiliation"
_DISCOVERY_CACHE_TTL = 3600  # discovery documents don't change; cache for an hour
_HTTP_TIMEOUT = 10
_ID_TOKEN_LEEWAY = 60  # seconds of clock skew accepted on exp
# Discovery fields the flow cannot do without; without one of them there is no login (fail closed).
_DISCOVERY_REQUIRED = ("issuer", "authorization_endpoint", "token_endpoint", "userinfo_endpoint", "jwks_uri")
# Only asymmetric signatures: never `none`, never an HMAC keyed with the client secret.
_ASYMMETRIC_ALGS = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512")

_discovery_cache: dict | None = None
_discovery_cache_at: float = 0.0
_jwks_cache: tuple[str, float, KeySet] | None = None  # (jwks_uri, fetched at, keys)
_pkce_warned = False


class OidcValidatieFout(Exception):
    """The provider's configuration or answer fails validation: no login, the callback answers 400 (#1024).

    The message is our own fixed text (at most an error code and a claim name), never a token or claim value.
    """


class LoginGeheimen(NamedTuple):
    """The three single-use values of one login: CSRF state, OIDC nonce and PKCE code verifier."""

    state: str
    nonce: str
    code_verifier: str


def nieuwe_login_geheimen() -> LoginGeheimen:
    """Fresh random values per login; the verifier is 86 characters (RFC 7636 asks for 43-128)."""
    return LoginGeheimen(
        state=secrets.token_urlsafe(32),
        nonce=secrets.token_urlsafe(32),
        code_verifier=secrets.token_urlsafe(64),
    )


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


def _oauth_client() -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        Config.OIDC_CLIENT_ID,
        Config.OIDC_CLIENT_SECRET,
        redirect_uri=_redirect_uri(),
        scope=OAUTH_SCOPES,
        code_challenge_method="S256",
        timeout=_HTTP_TIMEOUT,
    )


async def _fetch_json(url: str):
    """GET a JSON document from the provider (discovery, JWKS) with a timeout."""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


def _check_discovery(config) -> None:
    """Fail closed on a discovery document the flow cannot validate against; warn once without S256."""
    global _pkce_warned
    if not isinstance(config, dict):
        raise OidcValidatieFout("discovery is geen JSON-object")
    if missing := [veld for veld in _DISCOVERY_REQUIRED if not config.get(veld)]:
        raise OidcValidatieFout(f"discovery mist {', '.join(missing)}")
    methods = config.get("code_challenge_methods_supported")
    if methods is not None and "S256" not in methods and not _pkce_warned:
        # We send S256 anyway: a provider without PKCE ignores the parameters.
        logger.warning("OIDC discovery noemt S256 niet in code_challenge_methods_supported")
        _pkce_warned = True


async def _get_discovery_config() -> dict:
    global _discovery_cache, _discovery_cache_at
    now = time.time()
    if _discovery_cache and (now - _discovery_cache_at) < _DISCOVERY_CACHE_TTL:
        return _discovery_cache
    if not Config.OIDC_DISCOVERY_URL:
        raise OidcValidatieFout("geen discovery-URL")
    config = await _fetch_json(Config.OIDC_DISCOVERY_URL)
    _check_discovery(config)
    _discovery_cache = config
    _discovery_cache_at = now
    return config


async def _get_jwks(jwks_uri: str, refresh: bool = False) -> KeySet:
    """The provider's public keys, cached like the discovery document; `refresh` skips the cache."""
    global _jwks_cache
    now = time.time()
    if not refresh and _jwks_cache and _jwks_cache[0] == jwks_uri and (now - _jwks_cache[1]) < _DISCOVERY_CACHE_TTL:
        return _jwks_cache[2]
    document = await _fetch_json(jwks_uri)
    try:
        keys = KeySet.import_key_set(document)
    except (JoseError, KeyError, TypeError, ValueError) as e:
        raise OidcValidatieFout(f"JWKS onleesbaar: {type(e).__name__}") from e
    _jwks_cache = (jwks_uri, now, keys)
    return keys


def _allowed_algorithms(config: dict) -> list[str]:
    offered = config.get("id_token_signing_alg_values_supported") or ["RS256"]
    algorithms = [alg for alg in _ASYMMETRIC_ALGS if alg in offered]
    if not algorithms:
        raise OidcValidatieFout("geen asymmetrisch ondertekeningsalgoritme voor het id_token")
    return algorithms


async def _decode_id_token(id_token: str, jwks_uri: str, algorithms: list[str]) -> dict:
    """Verify the signature; an unknown `kid` re-fetches the JWKS once (key rotation at the provider)."""
    try:
        try:
            return jwt.decode(id_token, await _get_jwks(jwks_uri), algorithms=algorithms).claims
        except InvalidKeyIdError:
            return jwt.decode(id_token, await _get_jwks(jwks_uri, refresh=True), algorithms=algorithms).claims
    except JoseError as e:
        raise OidcValidatieFout(f"id_token afgekeurd: {e.error}") from e


def _check_claims(claims: dict, issuer: str, nonce: str) -> None:
    client_id = Config.OIDC_CLIENT_ID
    if not client_id:
        raise OidcValidatieFout("geen client-ID")
    registry = jwt.JWTClaimsRegistry(
        leeway=_ID_TOKEN_LEEWAY,
        iss={"essential": True, "value": issuer},
        aud={"essential": True, "value": client_id},
        exp={"essential": True},
        sub={"essential": True},
        nonce={"essential": True},
    )
    try:
        registry.validate(claims)
    except JoseError as e:
        raise OidcValidatieFout(f"id_token afgekeurd: {e.error} {getattr(e, 'claim', '')}".rstrip()) from e
    if not secrets.compare_digest(str(claims["nonce"]).encode(), nonce.encode()):
        raise OidcValidatieFout("id_token afgekeurd: nonce wijkt af")
    if claims.get("azp") not in (None, client_id):
        raise OidcValidatieFout("id_token afgekeurd: azp wijkt af")


async def _valideer_id_token(id_token, config: dict, nonce: str) -> dict:
    """The claims of a valid id_token: signature from the JWKS, iss, aud, exp and nonce checked."""
    if not id_token or not isinstance(id_token, str):
        raise OidcValidatieFout("geen id_token in het antwoord van de provider")
    claims = await _decode_id_token(id_token, config["jwks_uri"], _allowed_algorithms(config))
    _check_claims(claims, config["issuer"], nonce)
    return claims


async def build_authorization_url(geheimen: LoginGeheimen) -> str:
    """Build the SRAM authorization redirect URL with state, nonce and PKCE challenge (S256)."""
    oidc_config = await _get_discovery_config()
    async with _oauth_client() as client:
        auth_url, _ = client.create_authorization_url(
            oidc_config["authorization_endpoint"],
            state=geheimen.state,
            nonce=geheimen.nonce,
            code_verifier=geheimen.code_verifier,
        )
    return auth_url


async def exchange_code_for_user(code: str, code_verifier: str, nonce: str) -> dict:
    """Exchange an authorization code for the SRAM user's profile (email, name, sub).

    Raises OidcValidatieFout when the id_token is missing or invalid, or when userinfo names another `sub`;
    any other exception is a provider or transport error.
    """
    oidc_config = await _get_discovery_config()
    async with _oauth_client() as client:
        token = await client.fetch_token(oidc_config["token_endpoint"], code=code, code_verifier=code_verifier)
        claims = await _valideer_id_token(token.get("id_token"), oidc_config, nonce)
        userinfo_response = await client.get(
            oidc_config["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
    userinfo_response.raise_for_status()
    userinfo = userinfo_response.json()
    if not isinstance(userinfo, dict) or userinfo.get("sub") != claims["sub"]:
        raise OidcValidatieFout("sub van userinfo wijkt af van het id_token")
    return userinfo
