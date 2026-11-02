from fastapi import APIRouter

from core.auth import SESSION_MAX, SESSION_TTL
from core.config import DASHBOARDS_ENABLED, FEEDBACK_ENABLED, MAX_CHAT_TURNS, MAX_HISTORY, MAX_MESSAGE_CHARS
from persistence.opschonen import OngeldigeTermijn, termijnen
from tools.catalog import dataset_counts

router = APIRouter(tags=["config"])


def _bewaartermijnen() -> dict[str, int | None]:
    """De termijnen die de opschoning toepast (#485), voor de privacy- en feedbackteksten (#835). Weigert de
    opschoning een termijn, dan verwijdert zij niets en komt er hier geen getal mee; de frontend toont dan zijn
    standaardtekst."""
    try:
        t = termijnen()
    except OngeldigeTermijn:
        return {"bewaartermijn_gesprekken_dagen": None, "bewaartermijn_rapporten_dagen": None}
    return {"bewaartermijn_gesprekken_dagen": t.gesprekken, "bewaartermijn_rapporten_dagen": t.rapporten}


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
        **_bewaartermijnen(),
        # De sessieduur (#479) in uren, zoals SESSION_TTL_HOURS en SESSION_MAX_HOURS hem instellen.
        "sessie_uren": SESSION_TTL / 3600,
        "sessie_max_uren": SESSION_MAX / 3600,
    }


@router.get("/api/catalog/counts")
async def get_catalog_counts() -> dict[str, int]:
    """Dataset counts per source for the data sources overview (public)."""
    return dataset_counts()
