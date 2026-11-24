"""Een bewaard rapport als bewerkbaar Word-document (#1038).

`POST /api/workbooks/{id}/docx` rendert het rapport zoals het in de database staat (html_content), niet wat de client
stuurt: het lichaam bevat alleen de grafieken als PNG (tools/rapport_docx/afbeeldingen.py). Alleen een eigen werkboek;
een vreemd of onbekend id krijgt dezelfde 404 als GET /api/workbooks/{id}. Databank, lezen en renderen zijn synchroon
en gaan in een thread, zodat de event loop en de chat-streams van anderen doorlopen (#508).
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from core.auth import get_current_user
from core.bestandsnaam import rapportdeel
from core.foutmeldingen import RAPPORT_NIET_GEVONDEN
from core.openapi_schema import bijlage
from core.rate_limit import RateLimiter
from persistence import db as persistence_db
from tools.rapport_docx import AfbeeldingFout, kan_docx, lees_grafieken, rapport_uit_html, render_docx

logger = logging.getLogger(__name__)

router = APIRouter(tags=["persistence"])

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
GEEN_RAPPORT = "Dit is geen rapport, dus er is geen Word-document van te maken."

# Een Word-document kost rekentijd; per gebruiker een ruime grens, want gasten delen één naam.
_limiter = RateLimiter(max_attempts=30, window_seconds=60, naam="rapport_docx")


def bestandsnaam(titel: str) -> str:
    """Dezelfde naam als workbookFilename in de app (core/bestandsnaam.py, #1124, #1125)."""
    return f"{rapportdeel(titel)}.docx"


def _maak(username: str, wb_id: str, content_type: str | None, lichaam: bytes) -> tuple[str, bytes, int, int]:
    werkboek = persistence_db.get_workbook(username, wb_id)
    if werkboek is None:
        raise HTTPException(status_code=404, detail=RAPPORT_NIET_GEVONDEN)
    html = werkboek.get("html_content")
    if not kan_docx(html):
        raise HTTPException(status_code=422, detail=GEEN_RAPPORT)
    rapport = rapport_uit_html(html)
    try:
        grafieken = lees_grafieken(content_type, lichaam, len(rapport.visualisaties))
    except AfbeeldingFout as fout:
        raise HTTPException(status_code=fout.status, detail=fout.melding) from None
    docx = render_docx(rapport, grafieken)
    return werkboek.get("title") or rapport.titel, docx, len(grafieken), len(rapport.visualisaties)


@router.post(
    "/api/workbooks/{wb_id}/docx",
    response_class=Response,
    responses=bijlage(DOCX_TYPE, "Het rapport als bewerkbaar Word-document."),
)
async def rapport_docx(wb_id: str, request: Request, username: str = Depends(get_current_user)) -> Response:
    if (wacht := await asyncio.to_thread(_limiter.probeer, username)) is not None:
        raise HTTPException(
            status_code=429,
            detail=f"Je hebt net al veel Word-documenten gemaakt. Probeer het over {wacht} seconden opnieuw.",
            headers={"Retry-After": str(wacht)},
        )
    lichaam = await request.body()
    titel, docx, met_grafiek, visualisaties = await asyncio.to_thread(
        _maak, username, wb_id, request.headers.get("content-type"), lichaam
    )
    logger.info("Word-export werkboek=%r grafieken=%d/%d bytes=%d", wb_id, met_grafiek, visualisaties, len(docx))
    headers = {"Content-Disposition": f'attachment; filename="{bestandsnaam(titel)}"'}
    return Response(docx, media_type=DOCX_TYPE, headers=headers)
