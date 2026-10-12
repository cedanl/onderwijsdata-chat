import asyncio
import json

import pytest

from agent.report import RAPPORT_GEWEIGERD, RapportGeweigerd
from agent.session_data import DATA_WEG
from core.errors import Gebruikersfout
from routes import chat


def _run_report(monkeypatch, exc: Exception) -> list[dict]:
    async def failing_generate(*args, **kwargs):
        raise exc

    monkeypatch.setattr(chat, "generate_report_spec", failing_generate)
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    asyncio.run(chat._generate_report({"username": "u"}, emit, model=None))
    return events


def test_unexpected_report_error_hides_exception_text(monkeypatch):
    events = _run_report(monkeypatch, TypeError("unhashable type: 'dict'"))
    [error] = [e for e in events if e["type"] == "report_error"]
    assert "unhashable" not in error["message"]
    assert "Rapport kon niet worden gemaakt" in error["message"]


def test_expected_report_error_keeps_its_guidance(monkeypatch):
    # Alleen een Gebruikersfout draagt tekst die voor de gebruiker is geschreven (#503);
    # een kale ValueError valt sindsdien onder de generieke melding.
    msg = "Geen datasets geladen. Stel eerst een vraag waarvoor data wordt opgehaald."
    events = _run_report(monkeypatch, Gebruikersfout(msg))
    [error] = [e for e in events if e["type"] == "report_error"]
    assert error["message"] == msg


def test_json_decode_error_hides_parser_error(monkeypatch):
    # A JSONDecodeError (LLM produced invalid structured output, e.g. a raw
    # control character) is a ValueError subclass but must NOT surface its
    # raw text — the user gets the generic guidance instead.
    exc = json.JSONDecodeError("Invalid control character at: line 4 column 33 (char 179)", "x", 179)
    events = _run_report(monkeypatch, exc)
    [error] = [e for e in events if e["type"] == "report_error"]
    assert "Invalid control character" not in error["message"]
    assert "Rapport kon niet worden gemaakt" in error["message"]


def test_refused_report_offers_a_report_retry(monkeypatch):
    # #515: a report stopped by the consistency check can be made again from the chat message.
    events = _run_report(monkeypatch, RapportGeweigerd())
    [error] = [e for e in events if e["type"] == "report_error"]
    assert error == {"type": "report_error", "message": RAPPORT_GEWEIGERD, "herstel": "rapport"}


@pytest.mark.parametrize(
    "exc",
    [
        Gebruikersfout("Geen datasets geladen. Stel eerst een vraag waarvoor data wordt opgehaald."),
        # Data gone after a restart: a report retry can only fail again.
        Gebruikersfout(DATA_WEG),
        TypeError("unhashable type: 'dict'"),
    ],
)
def test_other_report_errors_offer_no_report_retry(monkeypatch, exc):
    events = _run_report(monkeypatch, exc)
    [error] = [e for e in events if e["type"] == "report_error"]
    assert "herstel" not in error
