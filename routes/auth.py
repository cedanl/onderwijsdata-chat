import asyncio
import json
import logging
import secrets
import time
import urllib.parse
from collections import OrderedDict
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from auth.oidc import (
    LoginGeheimen,
    OidcValidatieFout,
    build_authorization_url,
    exchange_code_for_user,
    is_oidc_configured,
    nieuwe_login_geheimen,
)
from core.auth import (
    AUTH_ENABLED,
    SESSION_MAX,
    USERS,
    bearer_token,
    check_credentials,
    get_current_user,
    get_optional_user,
    make_token,
    revoke_token,
    session_start,
    verify_token,
)
from core.errors import log_interne_fout
from core.logging_util import foutkenmerk
from core.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_login_limiter = RateLimiter(max_attempts=5, window_seconds=60, naam="login")
_LIMITER_NAAM_MAX = 64
# De eenmalige waarden van één SRAM-login, elk in een eigen cookie (#1024). Inloggen zet ze, de callback wist ze
# altijd: bij succes en bij elke fout.
_OIDC_COOKIES = {"state": "oidc_state", "nonce": "oidc_nonce", "code_verifier": "oidc_verifier"}
_OIDC_COOKIE_MAX_AGE = 600


def _extract_org_from_entitlement(entitlements):
    """Extract organization name from eduperson_entitlement values.
    Format: urn:mace:surf.nl:sram:group:<orgname>:<coname>:<groupname>"""
    if not entitlements:
        return None
    if isinstance(entitlements, str):
        entitlements = [entitlements]
    for ent in entitlements:
        if "sram:group:" in ent:
            parts = ent.split(":")
            if len(parts) >= 6:
                return parts[5]  # orgname
    return None


def _extract_institution_from_affiliation(affiliations):
    """Extract institution from voperson_external_affiliation.
    Format: employee@surf.nl -> surf.nl"""
    if not affiliations:
        return None
    if isinstance(affiliations, str):
        affiliations = [affiliations]
    for aff in affiliations:
        if "@" in aff:
            return aff.split("@")[1]
    return None


def _extract_domain_from_email(email):
    """Extract the domain from an email address: j.vermeer@hu.nl -> hu.nl."""
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[1].strip().lower() or None


@router.get("/status")
async def auth_status() -> dict:
    return {"required": AUTH_ENABLED, "oidc_enabled": is_oidc_configured()}


@router.get("/session", status_code=204, responses={401: {"description": "Token ontbreekt of geldt niet meer"}})
def session_check(username: Annotated[str | None, Depends(get_optional_user)]) -> Response:
    """Geldt het token in Authorization nog? 204 ja, 401 nee; in beide modi, zonder body (#499).

    De frontend vraagt het na een geweigerde chat-socket; /user bestaat alleen met OIDC. Dezelfde controle
    als /user (handtekening, vervaltijd, denylist), dus een databasestoring geeft 500, geen 401. Ook de 401
    blijft leeg. Een gewone functie: de denylist lezen hoort in de threadpool (#508). no-store: een bewaarde
    204 verbergt geen verlopen sessie.
    """
    return Response(status_code=204 if username else 401, headers={"Cache-Control": "no-store"})


# De SRAM-gebruikersinfo (naam, e-mail, organisatie, instelling) per gebruiker, zodat ze een herlaad van
# de pagina overleeft. Begrensd (#487, privacy M4): een rij vervalt na SESSION_MAX (langer kan geen sessie
# leven) en boven _OIDC_CACHE_MAX gebruikers gaat de langst niet gebruikte eruit. Eerder groeide dit tot een
# herstart.
_OIDC_CACHE_MAX = 1000
_oidc_user_cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()  # username -> (vervalt op, user_info)


def _ruim_oidc_cache_op() -> None:
    nu = time.monotonic()
    for naam in [naam for naam, (vervalt, _) in _oidc_user_cache.items() if vervalt <= nu]:
        del _oidc_user_cache[naam]
    while len(_oidc_user_cache) > _OIDC_CACHE_MAX:
        _oidc_user_cache.popitem(last=False)


def _store_oidc_user(username: str, user_data: dict) -> None:
    """Store SRAM user info server-side so it survives page reloads; bounded in size and time (#487)."""
    _oidc_user_cache.pop(username, None)
    _oidc_user_cache[username] = (time.monotonic() + SESSION_MAX, user_data)
    _ruim_oidc_cache_op()


def _get_oidc_user(username: str) -> dict | None:
    """Retrieve cached SRAM user info; None when unknown or expired. Reading keeps the row young."""
    item = _oidc_user_cache.get(username)
    if item is None:
        return None
    vervalt, user_data = item
    if vervalt <= time.monotonic():
        del _oidc_user_cache[username]
        return None
    _oidc_user_cache.move_to_end(username)
    return user_data


def vergeet_oidc_gebruiker(username: str) -> None:
    """Na "verwijder al mijn gegevens" (#646) staan naam, e-mail en organisatie niet meer in het geheugen."""
    _oidc_user_cache.pop(username, None)


# Only add user info + refresh endpoints if OIDC is configured; zonder OIDC (wachtwoordlogin of geen login)
# bestaan ze niet.
if is_oidc_configured():

    @router.get("/user")
    async def get_current_user_info(username: str = Depends(get_current_user)) -> dict:
        """
        Get current user's info. Server-side source of truth.
        Only available with OIDC; zonder OIDC houdt de frontend de gebruiker in localStorage.
        The token comes in the Authorization header, never in the URL (#103).
        """

        # For basic auth users, minimal info
        user_info = {"username": username, "name": username}

        # For SRAM users, add rich data if available
        if oidc_data := _get_oidc_user(username):
            user_info.update(oidc_data)

        return user_info

    @router.post("/refresh")
    def refresh_token(body: dict) -> dict:
        """
        Refresh auth token before expiration.
        Only available with OIDC.
        The new token keeps the session start: after SESSION_MAX_HOURS the user logs in again (#479).
        A plain function: verify_token reads the denylist, and that belongs in the threadpool (#508).
        """
        old_token = body.get("token", "").strip()
        if not old_token:
            raise HTTPException(status_code=400, detail="Token ontbreekt")

        username = verify_token(old_token)
        start = session_start(old_token)
        if not username or start is None or time.time() >= start + SESSION_MAX:
            raise HTTPException(status_code=401, detail="Ongeldig of verlopen token")

        new_token = make_token(username, start)
        user_info = {"username": username, "name": username}
        if oidc_data := _get_oidc_user(username):
            user_info.update(oidc_data)

        return {"token": new_token, "user": user_info}


@router.post("/logout", status_code=204)
def logout(authorization: Annotated[str | None, Header()] = None) -> None:
    """Trekt het token server-side in (#479).

    204 ook zonder, met een ongeldig of met een al ingetrokken token: uitloggen mag de
    client nooit in een 401-lus brengen. Zonder login raakt het de database niet.
    Een databasestoring geeft wel 500: het token is dan mogelijk niet ingetrokken.
    """
    revoke_token(bearer_token(authorization))


def _limiter_key(username: str, client_ip: str) -> str:
    """Sleutel van de login-limiter. De gebruikersnaam komt ongeauthenticeerd binnen en
    is dus onbegrensd lang: afkappen houdt de sleutel (en het geheugen) klein."""
    return f"{username.lower()[:_LIMITER_NAAM_MAX] or 'gast'}|{client_ip}"


@router.post("/login")
async def login(body: dict, request: Request) -> dict:
    username = body.get("username", "").strip()
    password = body.get("password", "")
    client_ip = request.client.host if request.client else "unknown"
    # Achter de ingress ziet uvicorn vaak voor iedereen hetzelfde adres (#504, S5):
    # tellen op IP alleen zette dan alle wachtwoordgebruikers in één bucket, en één
    # aanvaller kon de login voor iedereen blokkeren. De gebruikersnaam erbij beperkt
    # een vol budget tot die ene combinatie.
    limiter_key = _limiter_key(username, client_ip)
    if (retry := await asyncio.to_thread(_login_limiter.probeer, limiter_key)) is not None:
        raise HTTPException(
            status_code=429,
            detail=f"Te veel inlogpogingen. Probeer het over {retry} seconden opnieuw.",
            headers={"Retry-After": str(retry)},
        )
    if AUTH_ENABLED and not check_credentials(username, password, USERS):
        raise HTTPException(status_code=401, detail="Ongeldige inloggegevens")
    token = make_token(username or "gast")
    return {"token": token, "user": username or "gast"}


def _zet_oidc_cookies(response: Response, geheimen: LoginGeheimen) -> None:
    for veld, cookie in _OIDC_COOKIES.items():
        response.set_cookie(
            cookie,
            getattr(geheimen, veld),
            max_age=_OIDC_COOKIE_MAX_AGE,
            httponly=True,
            secure=True,
            samesite="lax",
        )


def _wis_oidc_cookies(response: Response) -> None:
    for cookie in _OIDC_COOKIES.values():
        response.delete_cookie(cookie, httponly=True, secure=True, samesite="lax")


def _oidc_fout(detail: str) -> JSONResponse:
    """400 van de callback, als response en niet als HTTPException: zo kan de callback de cookies nog wissen."""
    return JSONResponse({"detail": detail}, status_code=400)


@router.get("/oidc/login")
async def oidc_login() -> RedirectResponse:
    if not is_oidc_configured():
        raise HTTPException(status_code=404, detail="OIDC is niet geconfigureerd")
    geheimen = nieuwe_login_geheimen()
    try:
        auth_url = await build_authorization_url(geheimen)
    except OidcValidatieFout as e:
        # Een discovery zonder issuer of jwks_uri: zonder die twee valt het id_token niet te controleren (#1024).
        logger.error("OIDC-login niet gestart: %s", e)
        return RedirectResponse("/?oidc_error=1", status_code=302)
    response = RedirectResponse(auth_url, status_code=307)
    _zet_oidc_cookies(response, geheimen)
    return response


@router.get("/oidc/callback")
async def oidc_callback(request: Request) -> Response:
    if not is_oidc_configured():
        raise HTTPException(status_code=404, detail="OIDC is niet geconfigureerd")
    # Elk pad wist de drie login-cookies, ook een onverwachte fout na de code-uitwisseling (#1042): anders blijven ze
    # tot 10 minuten staan. De gebruiker krijgt een fout-ID, het type en een kenmerk staan in het log (core.errors).
    try:
        response = await _verwerk_oidc_callback(request)
    except Exception as e:
        fout_id = log_interne_fout(e, "OIDC-callback")
        response = JSONResponse({"detail": f"Inloggen mislukte door een interne fout (fout-ID {fout_id})."}, 500)
    _wis_oidc_cookies(response)
    return response


def _cookie_geheimen(request: Request) -> LoginGeheimen | None:
    """De waarden die oidc_login in cookies zette; None als er een ontbreekt."""
    state, nonce, code_verifier = (request.cookies.get(_OIDC_COOKIES[veld]) for veld in LoginGeheimen._fields)
    if state and nonce and code_verifier:
        return LoginGeheimen(state, nonce, code_verifier)
    return None


async def _verwerk_oidc_callback(request: Request) -> Response:
    error = request.query_params.get("error")
    if error:
        logger.warning("OIDC callback returned an error: %s", error)
        return RedirectResponse("/?oidc_error=1", status_code=302)

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    geheimen = _cookie_geheimen(request)
    if not code or not state or geheimen is None or not secrets.compare_digest(state.encode(), geheimen.state.encode()):
        return _oidc_fout("Ongeldige of verlopen OIDC-state")

    try:
        userinfo = await exchange_code_for_user(code, geheimen.code_verifier, geheimen.nonce)
    except OidcValidatieFout as e:
        # Eigen tekst zonder token of claimwaarde (auth/oidc.py); geen sessie (#1024).
        logger.warning("OIDC-login afgewezen: %s", e)
        return _oidc_fout("Ongeldige OIDC-login")
    except Exception as e:
        # De fout van de provider kan de token-URL of het antwoord citeren: op ERROR type en kenmerk (#819).
        logger.error("OIDC code exchange failed: %s", foutkenmerk(e))
        logger.debug("OIDC code exchange failed", exc_info=True)
        return RedirectResponse("/?oidc_error=1", status_code=302)

    username = userinfo.get("email") or userinfo.get("sub")
    if not username:
        return RedirectResponse("/?oidc_error=1", status_code=302)

    # Extract additional user info from SRAM OIDC
    name = userinfo.get("name")
    given_name = userinfo.get("given_name")
    family_name = userinfo.get("family_name")
    email = userinfo.get("email")
    entitlements = userinfo.get("eduperson_entitlement")
    external_affiliation = userinfo.get("voperson_external_affiliation")

    org = _extract_org_from_entitlement(entitlements)
    institution = _extract_institution_from_affiliation(external_affiliation)
    email_domein = _extract_domain_from_email(email)

    token = make_token(username)
    user_data = {
        "username": username,
        "name": name,
        "given_name": given_name,
        "family_name": family_name,
        "email": email,
        "org": org,
        "institution": institution,
        "email_domein": email_domein,
    }
    # Store user data server-side for /api/user endpoint (survives page reloads)
    _store_oidc_user(username, user_data)

    # Also send in URL for frontend initialization (temporary, deprecated in favor of /api/user)
    user_data_encoded = urllib.parse.quote(json.dumps(user_data))
    # In het fragment, niet in de query: een browser stuurt '#…' nooit naar een server of proxy (#103).
    return RedirectResponse(f"/#token={token}&user_data={user_data_encoded}", status_code=302)
