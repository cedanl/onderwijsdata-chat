import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from agent import recepten
from agent.publicatie import CSV, log_publicatie
from core.auth import get_current_user
from tools import herlaad
from tools.csv_export import bestandsnaam, naar_csv

router = APIRouter(tags=["data"])

_WEG = "Deze data is niet meer beschikbaar."
_OPNIEUW = "Stel de vraag opnieuw om haar op te halen."


@router.get("/api/data/csv")
async def data_csv(key: str, username: str = Depends(get_current_user)) -> Response:
    """De tabel achter een antwoord als CSV-bijlage (#269).

    De store leeft in het geheugen; na een herstart komt de tabel terug uit het recept
    van deze gebruiker (#472). Herladen gaat naar de bron, dus in een thread.

    De store is gedeeld over alle gebruikers, de export niet: alleen een key waar een eigen gesprek een
    recept van heeft (#13). Een vreemde key krijgt dezelfde melding als een verdwenen key, zodat de
    export niet bevestigt dat ze bestaat.
    """
    if await asyncio.to_thread(recepten.voor, username, key) is None:
        raise HTTPException(404, f"{_WEG} {_OPNIEUW}")
    herladen = await asyncio.to_thread(recepten.terughalen, username, key)
    if herladen is not None and not herladen.gelukt:
        raise HTTPException(502 if herladen.bronfout else 404, f"{_WEG} {herladen.melding} {_OPNIEUW}")
    csv = naar_csv(key, username)
    if csv is None:
        raise HTTPException(404, f"{_WEG} {_OPNIEUW}")
    log_publicatie(CSV, [key], username=username)
    headers = {"Content-Disposition": f'attachment; filename="{bestandsnaam(key)}"'}
    if notitie := herlaad.notitie(username, key):
        # De cijfers kunnen afwijken van het eerdere antwoord: de bron kan zijn gewijzigd. Ook in de CSV zelf.
        headers["X-Data-Herladen"] = notitie
    # Met BOM, anders leest Excel é als Ã©.
    return Response("﻿" + csv, media_type="text/csv; charset=utf-8", headers=headers)
