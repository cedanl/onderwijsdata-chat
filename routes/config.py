import os
from fastapi import APIRouter

router = APIRouter(tags=["config"])


@router.get("/api/config")
async def get_config():
    """Return frontend configuration (public endpoint, no auth required)."""
    return {
        "dashboards_enabled": os.getenv("ENABLE_DASHBOARDS", "true").lower() != "false",
    }
