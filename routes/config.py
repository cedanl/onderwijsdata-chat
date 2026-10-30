from fastapi import APIRouter

from core.config import DASHBOARDS_ENABLED, FEEDBACK_ENABLED, MAX_CHAT_TURNS, MAX_HISTORY, MAX_MESSAGE_CHARS
from tools.catalog import dataset_counts

router = APIRouter(tags=["config"])


@router.get("/api/config")
async def get_config():
    """Return frontend configuration (public endpoint, no auth required)."""
    return {
        "dashboards_enabled": DASHBOARDS_ENABLED,
        "feedback_enabled": FEEDBACK_ENABLED,
        "max_message_chars": MAX_MESSAGE_CHARS,
        # De contextlimieten (#789): de frontend houdt zijn constanten alleen als terugval.
        "max_chat_turns": MAX_CHAT_TURNS,
        "max_history": MAX_HISTORY,
    }


@router.get("/api/catalog/counts")
async def get_catalog_counts() -> dict[str, int]:
    """Dataset counts per source for the data sources overview (public)."""
    return dataset_counts()
