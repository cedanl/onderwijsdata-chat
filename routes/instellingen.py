import asyncio

from fastapi import APIRouter, Query

from core.config import MODEL, get_available_models
from data.dashboard import load_dashboard as load_dashboard_data
from data.instellingen import get_all as get_all_instellingen
from tools.catalog import _cbs as _cbs_catalog, _rio_duo as _rio_duo_catalog

router = APIRouter(tags=["instellingen"])


# ─── Starters ────────────────────────────────────────────────────────────────

_TAG_STARTERS: dict[str, tuple[str, ...]] = {
    "Verken Arbeidsmarkt": ("arbeidsmarkt",),
    "Verken Kansengelijkheid": ("kansengelijkheid", "herkomst", "diversiteit"),
    "Verken Regio": ("regio", "gemeente"),
    "Verken Voortijdig Schoolverlaten": ("vsv",),
}

TAG_STARTERS = _TAG_STARTERS


def tag_voorbeeldvragen(tags: tuple[str, ...], n: int = 4) -> list[str]:
    seen: set[str] = set()
    questions: list[str] = []
    for entry in list(_cbs_catalog()) + list(_rio_duo_catalog()):
        if any(t in entry.get("tags", []) for t in tags):
            for q in entry.get("voorbeeldvragen", []):
                if q not in seen:
                    seen.add(q)
                    questions.append(q)
        if len(questions) >= n * 4:
            break
    step = max(1, len(questions) // n)
    return [questions[i * step] for i in range(n) if i * step < len(questions)]


# ─── Settings ────────────────────────────────────────────────────────────────

@router.get("/api/settings/config")
async def get_settings_config() -> dict:
    available = get_available_models()
    return {
        "models": [
            {"id": mid, "name": name, "description": desc, "icon": icon}
            for mid, name, desc, icon in (available or [])
        ],
        "default_model": MODEL,
    }


# ─── Instellingen & Dashboard ───────────────────────────────────────────────

@router.get("/api/instellingen")
async def get_instellingen(type: str | None = Query(default=None)) -> list[dict]:
    loop = asyncio.get_running_loop()
    alle = await loop.run_in_executor(None, get_all_instellingen)
    if type:
        types = {t.strip().lower() for t in type.split(",")}
        return [i for i in alle if i["type"] in types]
    return alle


@router.get("/api/dashboard/instroom")
async def dashboard_instroom(instelling: str = Query(...)) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, load_dashboard_data, instelling)
