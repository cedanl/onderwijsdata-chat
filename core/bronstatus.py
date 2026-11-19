"""Welke bronnen nu niet live zijn (#1057).

Op 18-11 was DUO niet live en merkte de gebruiker dat pas toen een tool midden in een vraag faalde. Deze module kijkt
vanuit de pod, dus met dezelfde uitgaande route als de tools, of elke bron waarvoor de chat live aanroept nu antwoordt, en
bewaart de uitkomst in het geheugen. `niet_live()` geeft alleen de bronnen die niet antwoorden; `/api/bronstatus` toont
die aan de frontend, die bij een lege lijst niets laat zien.

Een lichte probe, geen ijkwaarden: dat blijft `scripts/bronping.py`. Een bron telt als live bij een antwoord onder de 400;
een 404 of 410 (RIO v2 gaf op 19-10 HTTP 410 op elke aanroep) is dus niet live. Een mislukte probe wordt direct één keer
herhaald; pas als ook die mislukt, staat de bron als niet live. Het meldt niets over de oorzaak: alleen dat de bron niet
antwoordt, nooit een URL of foutklasse (#1053).

De bewaking draait als achtergrondtaak naast de app (`bewaking`), blokkeert nooit het opstarten of een verzoek, en is
met `BRONSTATUS_INTERVAL_S=0` uit. De stand is per proces; elke pod meet zelf wat hij ziet.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime

import httpx
from onderwijsbronnen.cbs.client import BASE_API as CBS_API
from onderwijsbronnen.duo import CKAN_BASE as DUO_CKAN
from onderwijsbronnen.rio.client import BASE_URL as RIO_API
from onderwijsbronnen.uwv import CKAN_BASE as UWV_CKAN

from core import actualiteit
from core.logging_util import foutkenmerk

logger = logging.getLogger(__name__)

# Het antwoord van een probe mag niet langer duren dan dit; een hangende bron is niet live.
TIMEOUT_S = 5.0
# Tussen een mislukte probe en de herpoging, zodat één haperende verbinding niet meteen telt.
HERPOGING_PAUZE_S = 2.0
# De inspectie heeft geen API; haar basispagina (tools/inspectie.py leest de ods-bestanden daarvandaan) is de probe.
INSPECTIE_URL = "https://www.onderwijsinspectie.nl"


@dataclass(frozen=True)
class Bron:
    naam: str
    label: str
    url: str
    params: dict | None = None


# De bronnen waarvoor de chat live aanroept. De basis-URL's komen uit de bronpakketten; geen tweede lijst per bron.
# Een stabiele, goedkope aanroep per bron: de tabelinfo van één CBS-tabel, CKAN's status_show, één RIO-erkenning.
BRONNEN = (
    Bron("cbs", "CBS", f"{CBS_API}/85423NED/TableInfos"),
    Bron("duo", "DUO", f"{DUO_CKAN}/status_show"),
    Bron("rio", "RIO", f"{RIO_API}/erkenningen", {"pageSize": 1}),
    Bron("uwv", "UWV", f"{UWV_CKAN}/status_show"),
    Bron("inspectie", "Onderwijsinspectie", INSPECTIE_URL),
)


@dataclass
class _Stand:
    live: bool
    laatst_live: datetime | None = None


_stand: dict[str, _Stand] = {}


async def _antwoordt(client: httpx.AsyncClient, bron: Bron) -> bool:
    try:
        antwoord = await client.get(bron.url, params=bron.params)
    except httpx.HTTPError:
        return False
    return antwoord.status_code < 400


async def _live(client: httpx.AsyncClient, bron: Bron) -> bool:
    """Antwoordt de bron? Bij een mislukking één herpoging na een korte pauze."""
    if await _antwoordt(client, bron):
        return True
    await asyncio.sleep(HERPOGING_PAUZE_S)
    return await _antwoordt(client, bron)


def _bewaar(bron: Bron, live: bool) -> None:
    eerder = _stand.get(bron.naam)
    laatst_live = actualiteit.nu() if live else (eerder.laatst_live if eerder else None)
    _stand[bron.naam] = _Stand(live=live, laatst_live=laatst_live)
    was_live = eerder is None or eerder.live
    if was_live and not live:
        logger.warning("BRONSTATUS %s is niet live", bron.naam)
    elif live and not was_live:
        logger.info("BRONSTATUS %s is weer live", bron.naam)


async def controleer(client: httpx.AsyncClient) -> None:
    """Eén ronde: elke bron tegelijk, met één herpoging per mislukte probe."""
    uitkomsten = await asyncio.gather(*(_live(client, bron) for bron in BRONNEN))
    for bron, live in zip(BRONNEN, uitkomsten, strict=True):
        _bewaar(bron, live)


def niet_live() -> list[dict]:
    """De bronnen die in de laatste ronde niet antwoordden; leeg zolang er nog geen ronde was of alles live is."""
    lijst = []
    for bron in BRONNEN:
        stand = _stand.get(bron.naam)
        if stand is None or stand.live:
            continue
        lijst.append(
            {
                "bron": bron.naam,
                "naam": bron.label,
                "tekst": (
                    f"{bron.label} is op dit moment niet bereikbaar. Antwoorden die {bron.label}-data nodig hebben "
                    "kunnen falen of ontbreken."
                ),
                "laatst_live": stand.laatst_live.isoformat() if stand.laatst_live else None,
            }
        )
    return lijst


async def _draai(interval: float) -> None:
    async with httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=True) as client:
        while True:
            try:
                await controleer(client)
            except Exception as e:  # een fout in één ronde mag de bewaking niet stoppen
                logger.warning("BRONSTATUS ronde mislukt: %s", foutkenmerk(e))
                logger.debug("BRONSTATUS ronde mislukt", exc_info=True)
            await asyncio.sleep(interval)


@contextlib.asynccontextmanager
async def bewaking(interval: float) -> AsyncGenerator[asyncio.Task | None]:
    """Houdt de stand bij zolang de app draait: een ronde bij het opstarten, daarna elke `interval` seconden.

    Met interval 0 (of lager) staat de bewaking uit en komt er geen taak; de lijst blijft dan leeg."""
    if interval <= 0:
        yield None
        return
    taak = asyncio.create_task(_draai(interval), name="bronstatus")
    try:
        yield taak
    finally:
        taak.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await taak
