from fastapi import APIRouter

from core.config import DASHBOARDS_ENABLED
from tools.catalog import dataset_counts

router = APIRouter(tags=["config"])


@router.get("/api/config")
async def get_config():
    """Return frontend configuration (public endpoint, no auth required)."""
    return {
        "dashboards_enabled": DASHBOARDS_ENABLED,
    }


@router.get("/api/catalog/counts")
async def get_catalog_counts() -> dict[str, int]:
    """Dataset counts per source for the data sources overview (public)."""
    return dataset_counts()
