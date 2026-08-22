import logging
import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from auth.oidc import build_authorization_url, exchange_code_for_user, is_oidc_configured
from core.auth import AUTH_ENABLED, USERS, check_credentials, make_token
from core.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_login_limiter = RateLimiter(max_attempts=5, window_seconds=60)
_OIDC_STATE_COOKIE = "oidc_state"


@router.get("/status")
async def auth_status() -> dict:
    return {"required": AUTH_ENABLED, "oidc_enabled": is_oidc_configured()}


@router.post("/login")
async def login(body: dict, request: Request) -> dict:
    client_ip = request.client.host if request.client else "unknown"
    if not _login_limiter.is_allowed(client_ip):
        retry = _login_limiter.retry_after(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Te veel inlogpogingen. Probeer het over {retry} seconden opnieuw.",
            headers={"Retry-After": str(retry)},
        )
    username = body.get("username", "").strip()
    password = body.get("password", "")
    if AUTH_ENABLED and not check_credentials(username, password, USERS):
        raise HTTPException(status_code=401, detail="Ongeldige inloggegevens")
    token = make_token(username or "gast")
    return {"token": token, "user": username or "gast"}


@router.get("/oidc/login")
async def oidc_login() -> RedirectResponse:
    if not is_oidc_configured():
        raise HTTPException(status_code=404, detail="OIDC is niet geconfigureerd")
    state = secrets.token_urlsafe(32)
    auth_url = await build_authorization_url(state)
    response = RedirectResponse(auth_url, status_code=307)
    response.set_cookie(
        _OIDC_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.get("/oidc/callback")
async def oidc_callback(request: Request) -> RedirectResponse:
    if not is_oidc_configured():
        raise HTTPException(status_code=404, detail="OIDC is niet geconfigureerd")

    error = request.query_params.get("error")
    if error:
        logger.warning("OIDC callback returned an error: %s", error)
        return RedirectResponse("/?oidc_error=1", status_code=302)

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    cookie_state = request.cookies.get(_OIDC_STATE_COOKIE)
    if not code or not state or not cookie_state or not secrets.compare_digest(state, cookie_state):
        raise HTTPException(status_code=400, detail="Ongeldige of verlopen OIDC-state")

    try:
        userinfo = await exchange_code_for_user(code)
    except Exception:
        logger.exception("OIDC code exchange failed")
        return RedirectResponse("/?oidc_error=1", status_code=302)

    username = userinfo.get("email") or userinfo.get("sub")
    if not username:
        return RedirectResponse("/?oidc_error=1", status_code=302)

    token = make_token(username)
    response = RedirectResponse(f"/?token={token}", status_code=302)
    response.delete_cookie(_OIDC_STATE_COOKIE)
    return response
