import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from core.auth import get_current_user
from tools import store
from tools.csv_export import naar_csv

router = APIRouter(tags=["data"])


@router.get("/api/data/csv")
async def data_csv(key: str, _username: str = Depends(get_current_user)) -> Response:
    """De tabel achter een antwoord als CSV-bijlage (#269)."""
    csv = naar_csv(key)
    if csv is None:
        # De store leeft in het geheugen: na een herstart is de tabel weg.
        raise HTTPException(404, "Deze data is niet meer beschikbaar. Stel de vraag opnieuw om haar op te halen.")
    known = store.meta(key)
    naam = re.sub(r"[^A-Za-z0-9_-]", "_", known.dataset if known else "data")
    # Met BOM, anders leest Excel é als Ã©.
    return Response(
        "﻿" + csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{naam}.csv"'},
    )
