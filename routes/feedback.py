from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints

from core.auth import FALLBACK_USER, get_current_user
from core.config import FEEDBACK_ENABLED
from core.feedback import QUESTIONS, validate_answers
from core.rate_limit import RateLimiter
from persistence import db as persistence_db

router = APIRouter(tags=["feedback"])

# Per gebruiker per rapport, niet per IP: zonder login heet iedereen "gast" en
# achter de ingress delen alle bezoekers één IP. Zo kan een zaal vol gasten
# tegelijk feedback geven, maar niet één rapport blijven bestoken.
_limiter = RateLimiter(max_attempts=3, window_seconds=600)

_Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class FeedbackIn(BaseModel):
    workbook_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    report_type: _Short
    report_title: _Short = ""
    answers: dict[str, object]


def _require_enabled() -> None:
    if not FEEDBACK_ENABLED:
        raise HTTPException(status_code=404, detail="Feedback staat uit")


@router.get("/api/feedback/questions", dependencies=[Depends(_require_enabled)])
async def get_questions() -> list[dict]:
    return list(QUESTIONS)


@router.get("/api/feedback/given", dependencies=[Depends(_require_enabled)])
async def get_given(username: str = Depends(get_current_user)) -> list[str]:
    # Gasten delen één naam; dan zou feedback van de één bij iedereen als gegeven tonen.
    if username == FALLBACK_USER:
        return []
    return persistence_db.list_feedback_workbooks(username)


@router.post("/api/feedback", dependencies=[Depends(_require_enabled)])
async def post_feedback(body: FeedbackIn, username: str = Depends(get_current_user)) -> dict:
    try:
        answers = validate_answers(body.answers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    # Alleen op een eigen werkboek; anders vervuilt de telling per rapport (#389).
    if not persistence_db.workbook_belongs_to(username, body.workbook_id):
        raise HTTPException(status_code=404, detail="Rapport niet gevonden")
    key = f"{username}|{body.workbook_id}"
    if not _limiter.is_allowed(key):
        retry = _limiter.retry_after(key)
        raise HTTPException(
            status_code=429,
            detail=f"Je hebt net al feedback op dit rapport gegeven. Probeer het over {retry} seconden opnieuw.",
            headers={"Retry-After": str(retry)},
        )
    persistence_db.add_feedback(username, body.workbook_id, body.report_type, body.report_title, answers)
    return {"ok": True}
