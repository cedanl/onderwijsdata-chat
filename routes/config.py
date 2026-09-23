import os

from fastapi import APIRouter

from tools.catalog import dataset_counts

router = APIRouter(tags=["config"])


@router.get("/api/config")
async def get_config():
    """Return frontend configuration (public endpoint, no auth required)."""
    return {
        "dashboards_enabled": os.getenv("ENABLE_DASHBOARDS", "true").lower() != "false",
    }


@router.get("/api/catalog/counts")
async def get_catalog_counts() -> dict[str, int]:
    """Dataset counts per source for the data sources overview (public)."""
    return dataset_counts()
