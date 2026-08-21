import asyncio
import logging
import os
import signal
import sys
import tomllib
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

# Setup structured logging (JSON for production, text for development)
from logging_config import setup_logging
from config import Config, ConfigError

json_format = Config.is_production()
setup_logging(level=Config.LOG_LEVEL, json_format=json_format)
logger = logging.getLogger(__name__)

# Validate configuration early
try:
    Config.validate()
except ConfigError as e:
    logger.error(f"Configuration validation failed: {e}")
    sys.exit(1)

from persistence import db as persistence_db
from routes import (
    auth_router,
    chat_router,
    instellingen_router,
    persistence_router,
)
from auth.oidc import is_oidc_configured
import health

app = FastAPI(
    title="Onderwijsdata Chat",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# Initialize database
try:
    persistence_db.init_db()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    sys.exit(1)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.get_parsed_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.plot.ly; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' wss: ws:; "
        "font-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers["Server"] = ""
    return response


# ─── Health checks ───────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health_endpoint() -> dict:
    """Liveness probe: application is running."""
    return await health.health_check()


@app.get("/ready", tags=["health"])
async def ready_endpoint() -> tuple[dict, int]:
    """Readiness probe: application is ready to serve traffic."""
    result, status_code = await health.readiness_check()
    return result, status_code


@app.get("/startup", tags=["health"])
async def startup_endpoint() -> dict:
    """Startup verification: checks if initialization completed successfully."""
    return await health.startup_check()


_PYPROJECT = Path(__file__).parent / "pyproject.toml"

@app.get("/version", tags=["info"])
async def version() -> dict:
    """Get application version."""
    def _read() -> str:
        with open(_PYPROJECT, "rb") as f:
            return tomllib.load(f)["project"]["version"]
    return {"version": await asyncio.to_thread(_read)}


@app.get("/info", tags=["info"])
async def info() -> dict:
    """Get application info and configuration."""
    return {
        "name": "Onderwijsdata Chat",
        "oidc_enabled": is_oidc_configured(),
        "database_type": "PostgreSQL" if Config.POSTGRES_URI else "SQLite",
        "environment": "production" if Config.is_production() else "development",
    }


# ─── Startup and Shutdown ────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """Initialize application and record startup time."""
    health.record_startup()
    logger.info("Application startup completed", extra={
        "oidc_enabled": is_oidc_configured(),
        "database": "PostgreSQL" if Config.POSTGRES_URI else "SQLite",
    })


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Graceful shutdown: close connections and cleanup."""
    logger.info("Application shutdown initiated")
    try:
        # Cleanup database connections
        if hasattr(persistence_db, 'close'):
            persistence_db.close()
    except Exception as e:
        logger.warning(f"Error during shutdown cleanup: {e}")
    logger.info("Application shutdown completed")


# Handle SIGTERM for container termination
def _handle_sigterm(signum, frame):
    """Handle SIGTERM signal for graceful shutdown."""
    logger.info("SIGTERM received, initiating graceful shutdown")
    sys.exit(0)


signal.signal(signal.SIGTERM, _handle_sigterm)


# ─── Routers ─────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(persistence_router)
app.include_router(instellingen_router)
app.include_router(chat_router)

# ─── Serve React frontend ───────────────────────────────────────────────────

_FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> Response:
        return Response(content=(_FRONTEND_DIST / "index.html").read_text(), media_type="text/html")
