"""Feedback op een rapport, en algemene feedback via de Feedback-link (#600).

Gewone functies, geen coroutines: de databaselaag is synchroon en hoort in de threadpool van
FastAPI, niet op de event loop (#508, zie routes/persistence.py).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints

from core.algemene_feedback import MAX_TEKST, PAGINA_PATROON, Soort
from core.auth import FALLBACK_USER, get_current_user
from core.config import FEEDBACK_ENABLED
from core.feedback import QUESTIONS, clean_instelling, validate_answers
from core.rate_limit import RateLimiter
from persistence import db as persistence_db

router = APIRouter(tags=["feedback"])

# Per gebruiker per rapport, niet per IP: zonder login heet iedereen "gast" en
# achter de ingress delen alle bezoekers één IP. Zo kan een zaal vol gasten
# tegelijk feedback geven, maar niet één rapport blijven bestoken.
_limiter = RateLimiter(max_attempts=3, window_seconds=600)

# Algemene feedback per gebruiker, ruimer dan per rapport: in een gedeeld account (iedereen "gast") delen
# alle bezoekers deze grens, dus een zaal vol testers moet er samen een paar kwijt kunnen.
_algemeen_limiter = RateLimiter(max_attempts=10, window_seconds=600)

_Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


def _object(report_type: str) -> str:
    """Het woord voor wat de gebruiker beoordeelt: een dashboard heet in de melding geen rapport (#795)."""
    return "dashboard" if report_type == "dashboard" else "rapport"


class FeedbackIn(BaseModel):
    workbook_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    report_type: _Short
    report_title: _Short = ""
    # De instelling die de gebruiker in de app koos; leeg als hij er geen koos. Wordt bijgeknipt, niet geweigerd.
    instelling: str | None = None
    answers: dict[str, object]


class AlgemeneFeedbackIn(BaseModel):
    tekst: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEKST)]
    soort: Soort | None = None
    pagina: Annotated[str, StringConstraints(pattern=PAGINA_PATROON)] = "/"


def _require_enabled() -> None:
    if not FEEDBACK_ENABLED:
        raise HTTPException(status_code=404, detail="Feedback staat uit")


@router.get("/api/feedback/questions", dependencies=[Depends(_require_enabled)])
def get_questions() -> list[dict]:
    return list(QUESTIONS)


@router.get("/api/feedback/given", dependencies=[Depends(_require_enabled)])
def get_given(username: str = Depends(get_current_user)) -> list[str]:
    # Gasten delen één naam; dan zou feedback van de één bij iedereen als gegeven tonen.
    if username == FALLBACK_USER:
        return []
    return persistence_db.list_feedback_workbooks(username)


@router.post("/api/feedback", dependencies=[Depends(_require_enabled)])
def post_feedback(body: FeedbackIn, username: str = Depends(get_current_user)) -> dict:
    try:
        answers = validate_answers(body.answers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    # Alleen op een eigen werkboek; anders vervuilt de telling per rapport (#389).
    if not persistence_db.workbook_belongs_to(username, body.workbook_id):
        raise HTTPException(status_code=404, detail=f"{_object(body.report_type).capitalize()} niet gevonden")
    key = f"{username}|{body.workbook_id}"
    if not _limiter.is_allowed(key):
        retry = _limiter.retry_after(key)
        raise HTTPException(
            status_code=429,
            detail=(
                f"Je hebt net al feedback op dit {_object(body.report_type)} gegeven. "
                f"Probeer het over {retry} seconden opnieuw."
            ),
            headers={"Retry-After": str(retry)},
        )
    persistence_db.add_feedback(
        username,
        body.workbook_id,
        body.report_type,
        body.report_title,
        answers,
        clean_instelling(body.instelling),
    )
    return {"ok": True}


@router.post("/api/feedback/algemeen", dependencies=[Depends(_require_enabled)])
def post_algemene_feedback(body: AlgemeneFeedbackIn, username: str = Depends(get_current_user)) -> dict:
    """Een idee, probleem of compliment los van een antwoord of rapport (#600)."""
    if not _algemeen_limiter.is_allowed(username):
        retry = _algemeen_limiter.retry_after(username)
        raise HTTPException(
            status_code=429,
            detail=f"Je hebt net al een paar keer feedback gegeven. Probeer het over {retry} seconden opnieuw.",
            headers={"Retry-After": str(retry)},
        )
    persistence_db.add_algemene_feedback(username, body.soort or "", body.tekst, body.pagina)
    return {"ok": True}
