"""Herhaal deze analyse (#1240): de CBS-tabellen achter een eigen antwoord opnieuw bij de bron, met de verschillen.

Geen modelaanroep, maar wel een aanroep naar de bron: daarom dezelfde grenzen als een chatbericht. Het herhalen telt
mee in de berichtlimiet (dezelfde limiet als de chat, 429 met Retry-After) en staat stil als het tokenbudget op is
(402, de melding van `tokenbudget.over_budget`), ook al kost het zelf geen tokens: anders was dit een gratis
bronproxy. Een antwoord van een ander geeft hetzelfde 404 als een onbekend antwoord, zoals bij gesprekken en
/api/data/csv.
"""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from agent import herhaling
from core import tokenbudget
from core.auth import get_current_user

from . import chat

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

NIET_GEVONDEN = "Dit antwoord is niet (meer) te herhalen. Stel de vraag opnieuw voor de nieuwste cijfers."
TE_LAAT = "De bron antwoordde niet op tijd. Probeer het later opnieuw."
# Een paar aanroepen naar CBS (data, TableInfos en de dimensies) per tabel, voor hooguit vijf tabellen.
HERHAAL_TIMEOUT_S = 120
_ANTWOORD = Path(pattern=r"^[0-9a-f]{64}$", description="De sha256 (hex) van de tekst van het antwoord.")


@router.post("/api/conversations/{conv_id}/antwoorden/{antwoord}/herhaal")
async def herhaal_analyse(
    conv_id: str, antwoord: Annotated[str, _ANTWOORD], username: str = Depends(get_current_user)
) -> dict:
    """Haal de CBS-tabellen achter een eigen antwoord opnieuw op en zet ze naast de stand van toen.

    Per tabel `status` (`ongewijzigd`, `bijgewerkt`, `niet_te_vergelijken` of `mislukt`), `samenvatting`, `toen` en
    `nu` (`bijgewerkt_op`, `hash`) en `verschil` (`cellen`, `eerste`, `rijen_erbij`, `rijen_weg`); een bronfout of
    scopeweigering is `mislukt` met een `melding`, geen 5xx. Het eerdere antwoord en de data in de app veranderen niet.
    """
    if (wacht := await asyncio.to_thread(chat._berichtlimiter.probeer, username)) is not None:
        logger.warning("HERHAAL berichtlimiet bereikt  wacht=%ds", wacht)
        raise HTTPException(429, chat._LIMIET_MELDING.format(wacht=wacht), headers={"Retry-After": str(wacht)})
    if melding := await asyncio.to_thread(tokenbudget.over_budget, username):
        logger.warning("HERHAAL tokenbudget op")
        raise HTTPException(402, melding)
    try:
        uitkomst = await asyncio.wait_for(
            asyncio.to_thread(herhaling.herhaal, username, conv_id, antwoord), HERHAAL_TIMEOUT_S
        )
    except TimeoutError:
        logger.warning("HERHAAL tijdsgrens van %ds bereikt", HERHAAL_TIMEOUT_S)
        raise HTTPException(504, TE_LAAT) from None
    if uitkomst is None:
        raise HTTPException(404, NIET_GEVONDEN)
    return uitkomst
