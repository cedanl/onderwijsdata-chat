from fastapi import APIRouter, Depends

from core.auth import get_current_user
from persistence import db as persistence_db

router = APIRouter(tags=["persistence"])


@router.get("/api/conversations")
async def list_conversations(username: str = Depends(get_current_user)) -> list[dict]:
    return persistence_db.list_conversations(username)


@router.put("/api/conversations/{conv_id}")
async def upsert_conversation(conv_id: str, body: dict, username: str = Depends(get_current_user)) -> dict:
    persistence_db.upsert_conversation(
        username, conv_id, body["title"], body["timestamp"], body["messages"],
    )
    return {"ok": True}


@router.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str, username: str = Depends(get_current_user)) -> dict:
    persistence_db.delete_conversation(username, conv_id)
    return {"ok": True}


@router.get("/api/workbooks")
async def list_workbooks(username: str = Depends(get_current_user)) -> list[dict]:
    return persistence_db.list_workbooks(username)


@router.put("/api/workbooks/{wb_id}")
async def upsert_workbook(wb_id: str, body: dict, username: str = Depends(get_current_user)) -> dict:
    persistence_db.upsert_workbook(
        username, wb_id, body.get("title", ""),
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
async def delete_workbook(wb_id: str, username: str = Depends(get_current_user)) -> dict:
    persistence_db.delete_workbook(username, wb_id)
    return {"ok": True}
