from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints

from core import config
from core.answer_feedback import antwoord_trace
from core.auth import get_current_user
from persistence import db as persistence_db

router = APIRouter(tags=["feedback"])


class AnswerFeedbackIn(BaseModel):
    conversation_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    message_index: int
    oordeel: Literal["up", "down"]
    toelichting: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""


def _require_enabled() -> None:
    # Bij aanroep gelezen, niet bij import: dezelfde schakelaar als de rapportfeedback.
    if not config.FEEDBACK_ENABLED:
        raise HTTPException(status_code=404, detail="Feedback staat uit")


@router.get("/api/answer-feedback", dependencies=[Depends(_require_enabled)])
async def get_answer_feedback(conversation_id: str, username: str = Depends(get_current_user)) -> dict[int, str]:
    return persistence_db.answer_feedback_for(username, conversation_id)


@router.post("/api/answer-feedback", dependencies=[Depends(_require_enabled)])
async def post_answer_feedback(body: AnswerFeedbackIn, username: str = Depends(get_current_user)) -> dict:
    """👍/👎 op een antwoord (#248); de trace komt uit het eigen opgeslagen gesprek."""
    messages = persistence_db.conversation_messages(username, body.conversation_id)
    trace = antwoord_trace(messages, body.message_index) if messages is not None else None
    if trace is None:
        raise HTTPException(status_code=404, detail="Antwoord niet gevonden")
    persistence_db.upsert_answer_feedback(
        username, body.conversation_id, body.message_index, body.oordeel, body.toelichting, trace
    )
    return {"ok": True}
