"""Je eigen gegevens: alles wat de server onder je account bewaart (AVG, #485).

De handler is een gewone functie en de export een synchrone generator: Starlette leest hem in zijn
threadpool, dus de databaselaag zet de event loop niet stil (#508).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core.auth import get_current_user
from persistence import export

router = APIRouter(tags=["mijn-gegevens"])


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
