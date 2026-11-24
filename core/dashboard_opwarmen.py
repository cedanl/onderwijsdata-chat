"""De dashboards opwarmen na een start (#1166).

Een dashboard-eindpunt laadt zijn bronnen bij de eerste aanvraag; na een (her)start wachtte de eerste gebruiker daardoor
10-23 s. `opwarming` start na het opstarten een achtergrondtaak die elke lader één keer aanroept voor één instelling per
soort (hbo, wo, mbo). De caches zijn per bron, niet per instelling (`core/actualiteit.py`, `data/instellingen.py`): een
andere instelling van dezelfde soort is daarna ook warm. hbo en wo delen de DUO-bestanden, maar alleen een universiteit
laadt WOPI (personeel); een mbo-instelling laadt andere bestanden.

- Alleen met ENABLE_DASHBOARDS en DASHBOARD_WARMUP (standaard aan); een bron die hier uit staat
  (`tools/beschikbaarheid.py`) wordt niet geladen, zoals de route hem ook niet laadt.
- Na elkaar, elke lading in de executor en in een plaats van de dashboards (`_in_een_plaats`, MAX_DASHBOARD_LOADS):
  de opwarming bezet hooguit één plaats en verdringt geen aanvraag van een gebruiker. Een trage lading schrijft de
  gewone regel `DASHBOARD traag`.
- Een fout of een volle wachtrij stopt de opwarming en de app niet: één WARNING met het eindpunt en het foutkenmerk,
  zonder de instelling (#475). Aan het eind één INFO-regel met de eindpunten en de duur.
- Bij het afsluiten wordt de taak geannuleerd en afgewacht. Een lading die op dat moment in een thread loopt, kan Python
  niet onderbreken; die maakt haar thread af, zoals een lading van een gebruiker.
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncGenerator, Callable

from core.logging_util import foutkenmerk
from data.dashboard import (
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

logger = logging.getLogger(__name__)

# Per soort één instelling, in deze volgorde.
SOORTEN = ("hbo", "wo", "mbo")


def kies_instellingen(register: list[dict]) -> list[str]:
    """Per soort de eerste instelling van het register (dat staat op naam) met een bekende provincie: de kaart en de
    UWV-vacatures van een dashboard hebben die nodig, dus zo laadt de opwarming die bronnen ook. Heeft geen enkele
    instelling van de soort een provincie, dan de eerste; een soort die ontbreekt, valt weg."""
    gekozen = []
    for soort in SOORTEN:
        van_soort = [i for i in register if i.get("type") == soort]
        if van_soort:
            gekozen.append(next((i for i in van_soort if i.get("provincie")), van_soort[0])["naam"])
    return gekozen


def _eindpunten() -> list[tuple[str, Callable[[str], dict]]]:
    """De eindpunten die hier bestaan, de drie traagste eerst. Bij het aanroepen opgezocht, zodat de regels van
    beschikbaarheid gelden zoals ze nu staan."""
    alle: list[tuple[str, Callable[[str], dict], Callable[[], bool] | None]] = [
        ("regio", load_dashboard_regio, None),
        ("rendement", load_dashboard_rendement, None),
        ("financien", load_dashboard_financien, beschikbaarheid.financien),
        ("nationaal", load_dashboard_nationaal, None),
        ("arbeidsmarktmatch", load_dashboard_arbeidsmarktmatch, None),
        ("personeel", load_dashboard_personeel, beschikbaarheid.wo_personeel),
        ("opleidingen", load_dashboard_opleidingen, beschikbaarheid.studiekeuze),
    ]
    return [(naam, lader) for naam, lader, bron_aan in alle if bron_aan is None or bron_aan()]


def _mislukt(eindpunt: str, e: Exception) -> None:
    logger.warning("DASHBOARD opwarmen mislukt: eindpunt=%s %s", eindpunt, foutkenmerk(e))
    # De tekst en de traceback kunnen de instelling noemen: alleen op DEBUG (#475).
    logger.debug("DASHBOARD opwarmen mislukt: eindpunt=%s", eindpunt, exc_info=e)


async def _opwarmen() -> None:
    # Hier en niet bovenaan: `routes` laadt `core.auth`, dat bij een login zonder CHAT_SECRET of een ongeldige
    # sessieduur al bij het laden weigert; dan eindigde de start in een traceback in plaats van de ene melding van
    # Config.validate (#1164).
    from routes.instellingen import _in_een_plaats

    begin = time.monotonic()
    try:
        # Het register bouwt zich uit DUO-bestanden: dat hoort bij de opwarming, en dus in de executor.
        register = await asyncio.get_running_loop().run_in_executor(None, get_all_instellingen)
    except Exception as e:
        _mislukt("instellingen", e)
        return
    namen = kies_instellingen(register)
    if not namen:
        logger.warning("DASHBOARD opwarmen overgeslagen: het register van instellingen is leeg")
        return
    gelukt: list[str] = []
    mislukt: list[str] = []
    for eindpunt, lader in _eindpunten():
        fout = False
        for naam in namen:
            try:
                await _in_een_plaats(lader, naam)
            except Exception as e:  # Druk, BronNietBeschikbaar of iets onverwachts: de volgende lading gaat door
                _mislukt(eindpunt, e)
                fout = True
        (mislukt if fout else gelukt).append(eindpunt)
    logger.info(
        "DASHBOARD opgewarmd: eindpunten=%s mislukt=%s instellingen=%d duur=%.1f s",
        ",".join(gelukt) or "-",
        ",".join(mislukt) or "-",
        len(namen),
        time.monotonic() - begin,
    )


@contextlib.asynccontextmanager
async def opwarming(aan: bool) -> AsyncGenerator[asyncio.Task | None]:
    """De opwarming als achtergrondtaak zolang de app draait; de start wacht er niet op. Uit: geen taak."""
    if not aan:
        yield None
        return
    taak = asyncio.create_task(_opwarmen(), name="dashboard-opwarmen")
    try:
        yield taak
    finally:
        taak.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await taak
