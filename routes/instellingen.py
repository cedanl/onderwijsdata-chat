import asyncio
import logging
from collections.abc import Callable

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from core.auth import get_current_user
from core.config import (
    DASHBOARD_QUEUE_TIMEOUT_S,
    DASHBOARD_TIMEOUT_S,
    DASHBOARDS_ENABLED,
    MAX_DASHBOARD_LOADS,
    MODEL,
    get_available_models_for_user,
)
from core.gelijktijdig import Druk, Runplaatsen
from data.dashboard import (
    BronNietBeschikbaar,
    load_dashboard_arbeidsmarktmatch,
    load_dashboard_nationaal,
    load_dashboard_regio,
    load_dashboard_rendement,
)
from data.dashboard_financien import load_dashboard_financien
from data.dashboard_opleidingen import load_dashboard_opleidingen
from data.dashboard_personeel import load_dashboard_personeel
from data.instellingen import get_all as get_all_instellingen
from tools import beschikbaarheid
from tools.catalog import _cbs as _cbs_catalog
from tools.catalog import _rio_duo as _rio_duo_catalog
from tools.scopeprofiel import is_vo_context

logger = logging.getLogger(__name__)

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
    """Startervragen per tag. Vo-context voor vervolgonderwijs (#557, #877) blijft erbuiten: een startervraag heeft
    geen vraag van de gebruiker achter zich, dus de zoekpoort kan een pure vo-vraag daar niet tegenhouden."""
    seen: set[str] = set()
    questions: list[str] = []
    for entry in list(_cbs_catalog()) + list(_rio_duo_catalog()):
        if is_vo_context(entry):
            continue
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


# Met login aan alleen voor een ingelogde gebruiker, zoals de andere /api-routes: de modellijst helpt anders bij
# fingerprinting (#607). De loginpagina vraagt haar niet op; ChatPage pas na het inloggen.
@router.get("/api/settings/config")
async def get_settings_config(username: str = Depends(get_current_user)) -> dict:
    available = get_available_models_for_user(username)
    return {
        "models": [
            {"id": mid, "name": name, "description": desc, "icon": icon, "provider": provider}
            for mid, name, desc, icon, provider in (available or [])
        ],
        "default_model": MODEL,
    }


# ─── Instellingen & Dashboard ───────────────────────────────────────────────


@router.get("/api/instellingen")
async def get_instellingen(type: str | None = Query(default=None)) -> list[dict]:
    loop = asyncio.get_running_loop()
    alle = await loop.run_in_executor(None, get_all_instellingen)
    if type:
        types = {t.strip().lower() for t in type.split(",") if t.strip()}
        if types:
            return [i for i in alle if i["type"] in types]
    return alle


# Met login aan alleen voor een ingelogde gebruiker, en alleen als dashboards aan staan (#636): elke aanroep
# laadt en rekent DUO-, UWV- en ROA-data. Zonder login (lokaal) voor `gast`, zoals voorheen.
_INGELOGD = [Depends(get_current_user)]


# Hoeveel dashboardladingen tegelijk (#901), met dezelfde wachtrij als de runs van de chat (#688).
_dashboardplaatsen = Runplaatsen(max_tegelijk=MAX_DASHBOARD_LOADS, wacht_s=DASHBOARD_QUEUE_TIMEOUT_S)
# Een lading die de tijdsgrens haalde, loopt door in haar thread en houdt haar plaats tot ze klaar is: anders telde de
# limiet een thread die nog laadt niet meer mee. De verwijzing houdt de taak in leven.
_uitlopend: set[asyncio.Task] = set()


def _over_de_tijdsgrens() -> str:
    return f"Het dashboard kwam niet binnen {DASHBOARD_TIMEOUT_S:.0f} seconden af. Probeer het opnieuw."


async def _in_een_plaats(loader: Callable[[str], dict], instelling: str) -> dict:
    async with _dashboardplaatsen.plaats():
        return await asyncio.get_running_loop().run_in_executor(None, loader, instelling)


def _laat_uitlopen(taak: asyncio.Task) -> None:
    _uitlopend.add(taak)

    def klaar(t: asyncio.Task) -> None:
        _uitlopend.discard(t)
        if not t.cancelled() and t.exception() is not None:
            logger.debug("DASHBOARD uitgelopen lading mislukt", exc_info=t.exception())

    taak.add_done_callback(klaar)


# Een eindpunt op een bron met een omgevingsregel (tools/beschikbaarheid.py) bestaat niet waar die bron uit staat.
BRON_UIT = "Dit dashboard-eindpunt staat in deze omgeving niet aan: de bron erachter geeft hier geen antwoord."


async def _laad_dashboard(
    loader: Callable[[str], dict], instelling: str, bron_aan: Callable[[], bool] | None = None
) -> dict | JSONResponse:
    """De lading in een plaats en binnen de tijdsgrens (#901); de frontend leest `error` en biedt een nieuwe poging.
    `bron_aan`: de regel van de bron (tools/beschikbaarheid.py); staat ze uit, dan 404 en wordt er niets geladen."""
    if not DASHBOARDS_ENABLED:
        return JSONResponse({"error": "Dashboards zijn niet beschikbaar"}, status_code=403)
    if bron_aan is not None and not bron_aan():
        return JSONResponse({"error": BRON_UIT}, status_code=404)
    taak = asyncio.ensure_future(_in_een_plaats(loader, instelling))
    grens = asyncio.timeout(DASHBOARD_TIMEOUT_S)
    try:
        async with grens:
            return await asyncio.shield(taak)
    except asyncio.CancelledError:
        _laat_uitlopen(taak)  # de client is weg; de lading vult de cache voor de volgende
        raise
    except TimeoutError:
        if not grens.expired():
            raise
        logger.warning("DASHBOARD TIMEOUT na %.0f s", DASHBOARD_TIMEOUT_S)
        _laat_uitlopen(taak)
        return JSONResponse({"error": _over_de_tijdsgrens()}, status_code=504)
    except Druk as e:
        logger.warning("DASHBOARDPLAATSEN vol  max=%d  wacht=%ss", MAX_DASHBOARD_LOADS, DASHBOARD_QUEUE_TIMEOUT_S)
        return JSONResponse({"error": str(e)}, status_code=503)
    except BronNietBeschikbaar as e:
        # Geen "niet gevonden": de instelling is niet te bepalen zolang de bron uitligt.
        return JSONResponse({"error": str(e)}, status_code=503)


@router.get("/api/dashboard/regio", response_model=None, dependencies=_INGELOGD)
async def dashboard_regio(instelling: str = Query(...)) -> dict | JSONResponse:
    return await _laad_dashboard(load_dashboard_regio, instelling)


@router.get("/api/dashboard/nationaal", response_model=None, dependencies=_INGELOGD)
async def dashboard_nationaal(instelling: str = Query(...)) -> dict | JSONResponse:
    return await _laad_dashboard(load_dashboard_nationaal, instelling)


@router.get("/api/dashboard/rendement", response_model=None, dependencies=_INGELOGD)
async def dashboard_rendement(instelling: str = Query(...)) -> dict | JSONResponse:
    return await _laad_dashboard(load_dashboard_rendement, instelling)


@router.get("/api/dashboard/arbeidsmarktmatch", response_model=None, dependencies=_INGELOGD)
async def dashboard_arbeidsmarktmatch(instelling: str = Query(...)) -> dict | JSONResponse:
    return await _laad_dashboard(load_dashboard_arbeidsmarktmatch, instelling)


@router.get("/api/dashboard/financien", response_model=None, dependencies=_INGELOGD)
async def dashboard_financien(instelling: str = Query(...)) -> dict | JSONResponse:
    return await _laad_dashboard(load_dashboard_financien, instelling, beschikbaarheid.financien)


@router.get("/api/dashboard/personeel", response_model=None, dependencies=_INGELOGD)
async def dashboard_personeel(instelling: str = Query(...)) -> dict | JSONResponse:
    return await _laad_dashboard(load_dashboard_personeel, instelling, beschikbaarheid.wo_personeel)


@router.get("/api/dashboard/opleidingen", response_model=None, dependencies=_INGELOGD)
async def dashboard_opleidingen(instelling: str = Query(...)) -> dict | JSONResponse:
    # De Studiekeuzedatabase (#957): zonder de sleutel van LCSK bestaat het dashboard hier niet, zoals get_studiekeuze.
    return await _laad_dashboard(load_dashboard_opleidingen, instelling, beschikbaarheid.studiekeuze)


# ─── Wat geen dashboard-eindpunt is (#954) ───────────────────────────────────
# De eindpunten hierboven, zoals docs/api.md en docs/dashboards.md ze noemen. Een ander pad onder /api/dashboard of
# /api/dashboards gaf een kale 404; nu zegt het antwoord welke er wel zijn. /api/dashboard/instroom bestond tot 2.6.0
# (#930) en geeft 410 met waar de cijfers nu staan. Geen login nodig: er wordt niets geladen, en de paden staan in de
# docs. De routes staan na de eindpunten, zodat die voorgaan.
DASHBOARD_EINDPUNTEN = ("regio", "nationaal", "rendement", "arbeidsmarktmatch", "financien", "personeel", "opleidingen")
_WEL = ", ".join(f"/api/dashboard/{naam}" for naam in DASHBOARD_EINDPUNTEN) + ", elk met ?instelling=<naam>"
INSTROOM_WEG = (
    "/api/dashboard/instroom bestaat niet meer sinds versie 2.6.0: de cijfers van de eigen instelling staan in "
    f"/api/dashboard/regio. De dashboard-eindpunten zijn {_WEL}."
)
ONBEKEND_EINDPUNT = f"Geen dashboard-eindpunt. De dashboard-eindpunten zijn {_WEL}."


@router.get("/api/dashboard/instroom", include_in_schema=False)
async def dashboard_instroom_weg() -> JSONResponse:
    return JSONResponse({"error": INSTROOM_WEG}, status_code=410)


@router.get("/api/dashboard/{rest:path}", include_in_schema=False)
@router.get("/api/dashboards", include_in_schema=False)
@router.get("/api/dashboards/{rest:path}", include_in_schema=False)
async def onbekend_dashboard_eindpunt() -> JSONResponse:
    return JSONResponse({"error": ONBEKEND_EINDPUNT}, status_code=404)
