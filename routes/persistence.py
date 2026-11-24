"""Gesprekken en werkboeken van de ingelogde gebruiker.

De handlers zijn gewone functies, geen coroutines: FastAPI draait ze dan in zijn threadpool. De
databaselaag is synchroon (sqlite3, psycopg2); in een `async def` zet elke aanroep de event loop
stil, en daarmee elke lopende chat-stream van alle gebruikers (#508).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, Strict, StrictInt, StrictStr, StringConstraints

from agent import beurtbewijs, recepten
from core import opslagquotum
from core.auth import get_current_user
from core.foutmeldingen import RAPPORT_NIET_GEVONDEN
from core.persoonsgegevens import veilige_gesprekstitel
from persistence import db as persistence_db

router = APIRouter(tags=["persistence"])

GESPREK_ELDERS_GEWIJZIGD = (
    "Dit gesprek is intussen in een ander tabblad of op een ander apparaat bijgewerkt. Het is niet overschreven."
)


def _binnen_quotum(username: str, soort: str, item_id: str, grootte: int) -> None:
    """Het opslagquotum van de gebruiker (#682, S24): erboven een 507 met de melding; er wordt niets bewaard."""
    if melding := opslagquotum.toets(username, soort, item_id, grootte):
        raise HTTPException(status_code=opslagquotum.STATUS, detail=melding)


class ConversationTitle(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


# Wat de database bewaart: een geheel getal van 64 bit. Daarbuiten geeft de binding een OverflowError (#1129).
_INT64_MIN, _INT64_MAX = -(2**63), 2**63 - 1

# Een eindig getal binnen dat bereik, geen tekst ("gisteren"), geen bool en geen NaN/Infinity: die gaven een 500 in plaats van 422 (#1064).
Tijdstempel = Annotated[
    StrictInt | Annotated[float, Strict(), Field(allow_inf_nan=False)],
    Field(ge=_INT64_MIN, le=_INT64_MAX),
]


class ConversationUpsert(BaseModel):
    """De body van PUT /api/conversations/{id}, zoals ChatPage.jsx hem stuurt; andere velden worden genegeerd."""

    title: StrictStr
    timestamp: Tijdstempel
    messages: list[dict]


class WorkbookUpsert(BaseModel):
    """De body van PUT /api/workbooks/{id} (serverFields in workbooks.js).

    Elk veld heeft het type dat de databaselaag bindt: een object of lijst in een tekstveld gaf anders een 500 bij
    de binding (#1128). Zo'n lijst of object krijgt de 422 van #637; `type` van de frontend wordt genegeerd.
    """

    title: StrictStr = ""
    description: StrictStr = ""
    messages: list | None = None
    figures: list | None = None
    instelling: StrictStr | None = None
    html_content: StrictStr | None = Field(default=None, alias="htmlContent")
    dashboard_spec: dict | None = Field(default=None, alias="dashboardSpec")
    created_at: StrictStr = Field(default="", alias="createdAt")


@router.get("/api/conversations")
def list_conversations(
    username: str = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
    before_ts: Annotated[int, Query(ge=_INT64_MIN, le=_INT64_MAX)] | None = None,
    before_id: str | None = None,
    q: str = "",
) -> list[dict]:
    """Newest first; pass the timestamp and id of the last one shown for the next page (#123).

    With `q`, only the conversations whose title or text contains it, in one page (#124).
    Each row is id, title and timestamp; the messages come from GET /api/conversations/{id} (#509).
    """
    if q.strip():
        return persistence_db.search_conversations(username, q.strip(), limit=limit)
    before = (before_ts, before_id) if before_ts is not None and before_id is not None else None
    return persistence_db.list_conversations(username, before=before, limit=limit)


@router.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: str, username: str = Depends(get_current_user)) -> dict:
    """One own conversation with its messages, for opening it from the list (#509)."""
    conversation = persistence_db.get_conversation(username, conv_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Gesprek niet gevonden")
    return conversation


@router.put("/api/conversations/{conv_id}")
def upsert_conversation(conv_id: str, body: ConversationUpsert, username: str = Depends(get_current_user)) -> dict:
    _binnen_quotum(username, "gesprek", conv_id, opslagquotum.grootte_gesprek(body.messages))
    # Geen BSN, e-mailadres of telefoonnummer in de titel, ook niet van een andere client (#552).
    try:
        persistence_db.upsert_conversation(
            username,
            conv_id,
            veilige_gesprekstitel(body.title),
            body.timestamp,
            body.messages,
        )
    except persistence_db.GesprekEldersGewijzigd:
        # Twee tabbladen met hetzelfde gesprek (#760): niets overschrijven; de client bewaart zijn versie apart.
        raise HTTPException(status_code=409, detail=GESPREK_ELDERS_GEWIJZIGD) from None
    # De recepten achter de tabellen van dit gesprek: zo overleven ze een herstart (#472).
    recepten.bewaar(username, conv_id, body.messages)
    # Het bewijs achter de antwoorden in dit gesprek: lineage, rekenbewijs, bronregels en figuurstappen (ADR-009, #875). Na de 409 hierboven.
    beurtbewijs.bewaar(username, conv_id, body.messages)
    return {"ok": True}


@router.patch("/api/conversations/{conv_id}")
def rename_conversation(
    conv_id: str,
    body: ConversationTitle,
    username: str = Depends(get_current_user),
) -> dict:
    if not persistence_db.rename_conversation(username, conv_id, veilige_gesprekstitel(body.title)):
        raise HTTPException(status_code=404, detail="Gesprek niet gevonden")
    return {"ok": True}


@router.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str, username: str = Depends(get_current_user)) -> dict:
    recepten.vergeet(username, persistence_db.recipes_for(username, conv_id))
    beurtbewijs.vergeet(username, persistence_db.beurtbewijs_hashes(username, conv_id))
    persistence_db.delete_conversation(username, conv_id)
    return {"ok": True}


@router.get("/api/workbooks")
def list_workbooks(username: str = Depends(get_current_user)) -> list[dict]:
    """Id, titel, beschrijving, instelling, datum en type per werkboek; de inhoud via GET …/{id} (#633)."""
    return persistence_db.list_workbooks(username)


@router.get("/api/workbooks/{wb_id}")
def get_workbook(wb_id: str, username: str = Depends(get_current_user)) -> dict:
    workbook = persistence_db.get_workbook(username, wb_id)
    if workbook is None:
        raise HTTPException(status_code=404, detail=RAPPORT_NIET_GEVONDEN)
    # Openen telt als gebruik: de bewaartermijn van het werkboek begint opnieuw (#485).
    persistence_db.werkboek_geopend(username, wb_id)
    return workbook


@router.put("/api/workbooks/{wb_id}")
def upsert_workbook(wb_id: str, body: WorkbookUpsert, username: str = Depends(get_current_user)) -> dict:
    _binnen_quotum(username, "werkboek", wb_id, opslagquotum.grootte_werkboek(body.model_dump(by_alias=True)))
    persistence_db.upsert_workbook(
        username,
        wb_id,
        body.title,
        body.description,
        messages=body.messages,
        figures=body.figures,
        instelling=body.instelling,
        html_content=body.html_content,
        dashboard_spec=body.dashboard_spec,
        created_at=body.created_at,
    )
    return {"ok": True}


@router.delete("/api/workbooks/{wb_id}")
def delete_workbook(wb_id: str, username: str = Depends(get_current_user)) -> dict:
    persistence_db.delete_workbook(username, wb_id)
    return {"ok": True}
