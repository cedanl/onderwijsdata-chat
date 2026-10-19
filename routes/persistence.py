"""Gesprekken en werkboeken van de ingelogde gebruiker.

De handlers zijn gewone functies, geen coroutines: FastAPI draait ze dan in zijn threadpool. De
databaselaag is synchroon (sqlite3, psycopg2); in een `async def` zet elke aanroep de event loop
stil, en daarmee elke lopende chat-stream van alle gebruikers (#508).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, StringConstraints

from agent import recepten
from core.auth import get_current_user
from core.persoonsgegevens import veilige_gesprekstitel
from persistence import db as persistence_db

router = APIRouter(tags=["persistence"])


class ConversationTitle(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


@router.get("/api/conversations")
def list_conversations(
    username: str = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
    before_ts: int | None = None,
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
def upsert_conversation(conv_id: str, body: dict, username: str = Depends(get_current_user)) -> dict:
    # Geen BSN, e-mailadres of telefoonnummer in de titel, ook niet van een andere client (#552).
    persistence_db.upsert_conversation(
        username,
        conv_id,
        veilige_gesprekstitel(body["title"]),
        body["timestamp"],
        body["messages"],
    )
    # De recepten achter de tabellen van dit gesprek: zo overleven ze een herstart (#472).
    recepten.bewaar(username, conv_id, body["messages"])
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
    persistence_db.delete_conversation(username, conv_id)
    return {"ok": True}


@router.get("/api/workbooks")
def list_workbooks(username: str = Depends(get_current_user)) -> list[dict]:
    return persistence_db.list_workbooks(username)


@router.put("/api/workbooks/{wb_id}")
def upsert_workbook(wb_id: str, body: dict, username: str = Depends(get_current_user)) -> dict:
    persistence_db.upsert_workbook(
        username,
        wb_id,
        body.get("title", ""),
        body.get("description", ""),
        messages=body.get("messages"),
        figures=body.get("figures"),
        instelling=body.get("instelling"),
        html_content=body.get("htmlContent"),
        dashboard_spec=body.get("dashboardSpec"),
        created_at=body.get("createdAt", ""),
    )
    return {"ok": True}


@router.delete("/api/workbooks/{wb_id}")
def delete_workbook(wb_id: str, username: str = Depends(get_current_user)) -> dict:
    persistence_db.delete_workbook(username, wb_id)
    return {"ok": True}
