"""Je eigen gegevens: alles wat de server onder je account bewaart (AVG, #485).

De handlers zijn gewone functies en de export een synchrone generator: Starlette leest hem in zijn
threadpool, dus de databaselaag zet de event loop niet stil (#508).
"""

import logging
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import beurtbewijs, recepten
from core import auth
from core.auth import get_current_user
from core.openapi_schema import bijlage
from persistence import export, verwijderen

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mijn-gegevens"])

GEEN_EIGEN_ACCOUNT = "Zonder inloggen is er geen eigen account om te exporteren of te verwijderen."


def bestandsnaam(nu: datetime) -> str:
    return f"openedudata-mijn-gegevens-{nu:%Y-%m-%d}.json"


def eigen_account(username: str = Depends(get_current_user)) -> str:
    """De ingelogde gebruiker; zonder login 404: dan is iedereen de gedeelde `gast`, en die wist of exporteert niet het
    werk van alle bezoekers (#1118). AUTH_ENABLED wordt bij elke aanroep gelezen."""
    if not auth.AUTH_ENABLED:
        raise HTTPException(status_code=404, detail=GEEN_EIGEN_ACCOUNT)
    return username


@router.get(
    "/api/mijn-gegevens/export",
    response_class=StreamingResponse,
    responses=bijlage("application/json", "Alle gegevens van dit account als JSON-bijlage."),
)
def exporteer(username: Annotated[str, Depends(eigen_account)]) -> StreamingResponse:
    """Alle gesprekken, werkboeken, feedback, datarecepten, het bewijs per antwoord, het tokengebruik en het bewaarde
    SRAM-profiel van deze gebruiker als JSON-bijlage (#645, #1074, #1209).

    De export bevat persoonsgegevens (accountnaam, vrije tekst): alleen met het eigen token en nooit in
    een cache. Zonder login 404, zoals bij verwijderen (#1118). Hij wordt rij voor rij geschreven; breekt hij halverwege af, dan ziet de browser een
    onvolledige download.
    """
    nu = datetime.now(UTC)
    headers = {
        "Content-Disposition": f'attachment; filename="{bestandsnaam(nu)}"',
        "Cache-Control": "no-store",
    }
    return StreamingResponse(export.export_json_chunks(username, nu), media_type="application/json", headers=headers)


class Bevestiging(BaseModel):
    """Precies `{"bevestig": "verwijder"}`: zonder die tekst 422 en blijft alles staan."""

    bevestig: Literal["verwijder"]


@router.delete("/api/mijn-gegevens")
def verwijder_mijn_gegevens(
    bevestiging: Bevestiging,
    username: Annotated[str, Depends(eigen_account)],
) -> dict:
    """Verwijder al mijn gegevens (#646, AVG art. 17): alle rijen van dit account, in één transactie, ook het
    bewaarde SRAM-profiel (`oidc_gebruikers`, #984, #1209).

    Daarna vergeet het geheugen de gebruiker (wachtende recepten en bewijsrijen) en worden alle tokens van het account
    ingetrokken, ook die van een ander apparaat (#786): een open sessie daar kan dan geen gesprek meer terugzetten en
    sluit bij de volgende vraag. Faalt de transactie, dan blijft alles staan, ook het SRAM-profiel, en blijven de tokens
    geldig, zodat opnieuw proberen kan. Antwoord en log noemen alleen aantallen, nooit inhoud of de naam (#475).
    """
    aantallen = verwijderen.verwijder_alles(username)
    logger.info("verwijder mijn gegevens: %s", ", ".join(f"{soort}={n}" for soort, n in aantallen.items()))
    recepten.vergeet_gebruiker(username)
    beurtbewijs.vergeet_gebruiker(username)
    auth.revoke_all_tokens(username)
    return {"ok": True, "verwijderd": aantallen}
