"""
Health check endpoints for Kubernetes liveness and readiness probes.
"""

import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Track app startup time for liveness probe
_startup_time: Optional[float] = None


def record_startup() -> None:
    """Record application startup time."""
    global _startup_time
    _startup_time = time.time()
    logger.info("Application startup recorded")


async def check_database_connection() -> bool:
    """Test database connection. Returns True if healthy."""
    try:
        from persistence import db
        conn = db._connect()
        # Simple query to verify connection
        cursor = conn.cursor() if hasattr(conn, 'cursor') else conn
        if hasattr(cursor, 'execute'):
            cursor.execute("SELECT 1")
            cursor.fetchone()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"Database connection check failed: {e}")
        return False


async def check_llm_configuration() -> bool:
    """Verify LLM configuration is available."""
    from config import Config
    return any([
        Config.ANTHROPIC_API_KEY,
        Config.AZURE_AI_API_KEY,
        Config.OPENAI_API_KEY,
        Config.GOOGLE_API_KEY,
    ])


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
        logger.error(f"Startup check failed: {e}")
        return {"status": "startup_failed", "error": str(e)}
