from fastapi import APIRouter, HTTPException, Request

from core.auth import AUTH_ENABLED, USERS, check_credentials, make_token
from core.rate_limit import RateLimiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

_login_limiter = RateLimiter(max_attempts=5, window_seconds=60)


@router.get("/status")
async def auth_status() -> dict:
    return {"required": AUTH_ENABLED}


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
