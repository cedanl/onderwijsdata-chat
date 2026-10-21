"""Je eigen gegevens: alles wat de server onder je account bewaart (AVG, #485).

De handlers zijn gewone functies en de export een synchrone generator: Starlette leest hem in zijn
threadpool, dus de databaselaag zet de event loop niet stil (#508).
"""

import logging
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import recepten
from core import auth
from core.auth import get_current_user
from persistence import export, verwijderen

from .auth import vergeet_oidc_gebruiker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mijn-gegevens"])

GEEN_EIGEN_ACCOUNT = "Zonder inloggen is er geen eigen account om te verwijderen."


def bestandsnaam(nu: datetime) -> str:
    return f"openedudata-mijn-gegevens-{nu:%Y-%m-%d}.json"


@router.get("/api/mijn-gegevens/export")
def exporteer(username: str = Depends(get_current_user)) -> StreamingResponse:
    """Alle gesprekken, werkboeken, feedback en datarecepten van deze gebruiker als JSON-bijlage (#645).

    De export bevat persoonsgegevens (accountnaam, vrije tekst): alleen met het eigen token en nooit in
    een cache. Hij wordt rij voor rij geschreven; breekt hij halverwege af, dan ziet de browser een
    onvolledige download.
    """
    nu = datetime.now(UTC)
    headers = {
        "Content-Disposition": f'attachment; filename="{bestandsnaam(nu)}"',
        "Cache-Control": "no-store",
    }
    return StreamingResponse(export.export_json_chunks(username, nu), media_type="application/json", headers=headers)


def eigen_account(username: str = Depends(get_current_user)) -> str:
    """De ingelogde gebruiker; zonder login 404: dan is iedereen de gedeelde `gast`, en die wist niet het werk van
    alle bezoekers. AUTH_ENABLED wordt bij elke aanroep gelezen."""
    if not auth.AUTH_ENABLED:
        raise HTTPException(status_code=404, detail=GEEN_EIGEN_ACCOUNT)
    return username


class Bevestiging(BaseModel):
    """Precies `{"bevestig": "verwijder"}`: zonder die tekst 422 en blijft alles staan."""

    bevestig: Literal["verwijder"]


@router.delete("/api/mijn-gegevens")
def verwijder_alles(
    bevestiging: Bevestiging,
    username: Annotated[str, Depends(eigen_account)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Verwijder al mijn gegevens (#646, AVG art. 17): alle rijen van dit account, in één transactie.

    Daarna vergeet het geheugen de gebruiker (wachtende recepten, SRAM-gegevens) en wordt dit token ingetrokken,
    zoals bij uitloggen (#479). Faalt de transactie, dan blijft alles staan en blijft het token geldig, zodat
    opnieuw proberen kan; een tweede keer geeft nul rijen. Andere tokens van het account (een ander apparaat)
    blijven geldig tot ze verlopen. Antwoord en log noemen alleen aantallen, nooit inhoud of de naam (#475).
    """
    aantallen = verwijderen.verwijder_alles(username)
    logger.info("verwijder mijn gegevens: %s", ", ".join(f"{soort}={n}" for soort, n in aantallen.items()))
    recepten.vergeet_gebruiker(username)
    vergeet_oidc_gebruiker(username)
    auth.revoke_token(auth.bearer_token(authorization))
    return {"ok": True, "verwijderd": aantallen}
