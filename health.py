"""
Health check endpoints for Kubernetes liveness and readiness probes.
"""

import asyncio
import logging
import os
import time

from core.config import get_all_api_key_env_vars
from core.logging_util import foutkenmerk

logger = logging.getLogger(__name__)

# Track app startup time for liveness probe
_startup_time: float | None = None


def record_startup() -> None:
    """Record application startup time."""
    global _startup_time
    _startup_time = time.time()
    logger.info("Application startup recorded")


async def check_database_connection() -> bool:
    """Test database connection. Returns True if healthy.

    In a thread: the probe runs every few seconds, and a slow database must not stall the chat streams (#508).
    """
    try:
        from persistence import db

        await asyncio.to_thread(db.ping)
        return True
    except Exception as e:
        # Een driverfout kan host en databasenaam citeren: alleen type en kenmerk (#675).
        logger.warning("Database connection check failed: %s", foutkenmerk(e))
        return False


async def check_llm_configuration() -> bool:
    """Is er een sleutel voor een van de providers? Uit de ene lijst in core/config.py, dus ook Willma (#675):
    /ready is de readiness-probe, en een omgeving met alleen WILLMA_API_KEY zou anders nooit verkeer krijgen."""
    return any(os.getenv(naam) for naam in get_all_api_key_env_vars())


async def health_check() -> dict:
    """
    Liveness probe endpoint.
    Returns 200 if application is running.
    """
    return {
        "status": "ok",
        "timestamp": time.time(),
    }


async def readiness_check() -> dict:
    """
    Readiness probe endpoint.
    Returns 200 only if application is ready to serve traffic:
    - Database connection is working
    - LLM is configured
    """
    checks = {
        "database": await check_database_connection(),
        "llm": await check_llm_configuration(),
    }

    status = "ready" if all(checks.values()) else "not_ready"
    http_status = 200 if status == "ready" else 503

    return {
        "status": status,
        "checks": checks,
        "timestamp": time.time(),
    }, http_status


async def startup_check() -> dict:
    """
    Verification endpoint for startup success.
    Checks database and configuration without detailed diagnostics.
    """
    try:
        db_ok = await check_database_connection()
        llm_ok = await check_llm_configuration()

        if db_ok and llm_ok:
            return {"status": "startup_ok"}
        else:
            missing = []
            if not db_ok:
                missing.append("database")
            if not llm_ok:
                missing.append("llm")
            return {"status": "startup_incomplete", "missing": missing}
    except Exception as e:
        # Het eindpunt is zonder token bereikbaar: geen fouttekst in het antwoord (S4, #675).
        logger.error("Startup check failed: %s", foutkenmerk(e))
        return {"status": "startup_failed"}
