"""Gesloten foutcodes voor toolresultaten (#331).

Een ruwe providerfout ("Fout bij ophalen CBS data: <httpx-tekst>") is voor het model
een nieuwe prompt: elke variant gaf een ander pad, en niets stopte een tool die steeds
hetzelfde misging. Een fout heeft hier een vaste code plus een vaste Nederlandse tekst;
de ruwe tekst gaat naar het log. Aan de code ziet de toolloop dat dezelfde tool twee
keer dezelfde fout gaf (agent/loop.py zet hem dan op slot).
"""

import json
import logging
import re
from enum import StrEnum

import httpx

from . import store

logger = logging.getLogger(__name__)


class Fout(StrEnum):
    BRON_WEIGERT = "bron_weigert"  # HTTP 4xx: de aanvraag zelf klopt niet
    BRON_ONBEREIKBAAR = "bron_onbereikbaar"  # HTTP 5xx, timeout of netwerk
    BRON_FOUT = "bron_fout"  # de bron of het package faalde op een andere manier
    ONBEKENDE_DATA_KEY = "onbekende_data_key"
    TOOLFOUT = "toolfout"  # een exception in de tool zelf


_CODE = re.compile(r"^Fout \(([a-z_]+)\): ")


def melding(code: Fout, tekst: str) -> str:
    return f"Fout ({code}): {tekst}"


def code(result: str) -> str | None:
    """De foutcode van een toolresultaat; None als het geen gecodeerde fout is.

    compute_kpi verpakt fouten als {"fout": ...}; ook die wordt gelezen.
    """
    if result.startswith("{"):
        try:
            parsed = json.loads(result)
        except ValueError:
            return None
        result = parsed.get("fout", "") if isinstance(parsed, dict) else ""
        if not isinstance(result, str):
            return None
    m = _CODE.match(result)
    return m.group(1) if m else None


def bronfout(bron: str, e: Exception, uitleg: str = "") -> str:
    """Een providerfout als code en vaste tekst; de ruwe tekst gaat naar het log.

    Een ValueError komt uit de eigen packages (riodata, onderwijsdata), die een aanvraag
    lokaal toetsen ("Geen resource met 'mbo'", de geldige resources): die tekst helpt
    het model verder en blijft staan.
    """
    logger.warning("%s-fout: %r", bron, e)
    if isinstance(e, ValueError):
        return melding(Fout.BRON_WEIGERT, f"{bron}: {e}{uitleg}")
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status < 500:
            return melding(Fout.BRON_WEIGERT, f"{bron} weigerde de aanvraag (HTTP {status}).{uitleg}")
        return melding(Fout.BRON_ONBEREIKBAAR, f"{bron} gaf een serverfout (HTTP {status}).{uitleg}")
    if isinstance(e, httpx.TransportError):
        return melding(Fout.BRON_ONBEREIKBAAR, f"{bron} is nu niet bereikbaar ({type(e).__name__}).{uitleg}")
    return melding(Fout.BRON_FOUT, f"Laden uit {bron} mislukte ({type(e).__name__}).{uitleg}")


def toolfout(naam: str, e: Exception) -> str:
    logger.error("Tool %s faalde: %r", naam, e, exc_info=e)
    return melding(Fout.TOOLFOUT, f"{naam} faalde ({type(e).__name__}). Controleer de argumenten.")


def onbekende_key(data_key: str) -> str:
    beschikbaar = store.list_keys()
    hint = f" Beschikbare datasets: {beschikbaar}." if beschikbaar else ""
    return melding(
        Fout.ONBEKENDE_DATA_KEY,
        f"Geen data gevonden voor '{data_key}'.{hint} Laad eerst data via get_duo_data, get_cbs_data of get_rio_data.",
    )


_ALTERNATIEVEN = {
    "get_cbs_data": "Controleer codes met get_cbs_dimension of kies met search_catalog een andere tabel.",
    "get_cbs_dimension": "Gebruik de dimensies uit dataset_details.",
    "get_duo_data": "Kies met dataset_details een ander bestand of met search_catalog een andere dataset.",
    "get_rio_data": "Kies met dataset_details andere filters of met search_catalog een andere bron.",
}
_DATA_KEY = "Gebruik een data_key letterlijk uit een eerder toolresultaat."


def op_slot(naam: str, foutcode: str) -> str:
    """Wat het model hoort als het een tool op slot opnieuw aanroept."""
    alternatief = _ALTERNATIEVEN.get(naam, _DATA_KEY if foutcode == Fout.ONBEKENDE_DATA_KEY else "")
    delen = [
        f"OP SLOT: {naam} gaf twee keer dezelfde fout ({foutcode}) en wordt deze beurt niet meer uitgevoerd.",
        alternatief,
        "Of zeg met de resultaten die je hebt dat de data nu niet beschikbaar is.",
    ]
    return " ".join(d for d in delen if d)
