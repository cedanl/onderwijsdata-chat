"""
Health check endpoints for Kubernetes liveness and readiness probes.
"""

import asyncio
import logging
import time

from core.config import MODEL, llm_sleutel_aanwezig
from core.logging_util import foutkenmerk

logger = logging.getLogger(__name__)


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
    """Kan de app het geconfigureerde model aanroepen? Dezelfde check als de chat (`llm_sleutel_aanwezig`, #815):
    met Ollama zonder sleutel, anders met een van de providersleutels, dus ook alleen WILLMA_API_KEY (#675)."""
    return llm_sleutel_aanwezig(MODEL)


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
