"""Een berichtlimiet op de chat (#444, SECURITY.md S5).

De WebSocket kende geen limiet op het aantal vragen per gebruiker: elke vraag, verduidelijking,
dashboard en rapport kost een modelaanroep. Nu telt een limiter per gebruiker (zonder login: per
verbinding) en krijgt een verzoek erboven een melding met de wachttijd in plaats van een taak.
Het ophalen van voorbeeldvragen kost geen model en telt niet mee.
"""

import asyncio

import pytest

from core.auth import FALLBACK_USER
from core.rate_limit import RateLimiter
from routes import chat
from routes.instellingen import TAG_STARTERS


@pytest.fixture
def limiet(monkeypatch):
    monkeypatch.setattr(chat, "_berichtlimiter", RateLimiter(max_attempts=2, window_seconds=600))
    monkeypatch.setattr(chat, "DASHBOARDS_ENABLED", True)

    async def geen_model(*args, **kwargs):
        return None

    monkeypatch.setattr(chat, "_process_message", geen_model)
    monkeypatch.setattr(chat, "_generate_dashboard", geen_model)
    monkeypatch.setattr(chat, "_generate_report", geen_model)


def _run(action: str, msg: dict, session: dict):
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    async def scenario():
        taak = await chat.ACTIES[action]({"action": action, **msg}, session, emit, None)
        if taak is not None:
            await taak
        return taak

    return asyncio.run(scenario()), events


def _geweigerd(events: list[dict]) -> bool:
    return any(e.get("type") == "error" and "Te veel verzoeken" in e.get("message", "") for e in events)


def test_boven_de_limiet_komt_een_melding_met_wachttijd_en_geen_taak(limiet):
    session = chat._new_session(username="anna")
    for _ in range(2):
        taak, events = _run("message", {"content": "Hoeveel studenten?"}, session)
        assert taak is not None and not _geweigerd(events)

    taak, events = _run("message", {"content": "En in 2024?"}, session)

    assert taak is None
    [fout] = [e for e in events if e.get("type") == "error"]
    assert "seconden" in fout["message"] and fout["modelafhankelijk"] is False


def test_de_limiet_geldt_per_gebruiker(limiet):
    anna, bob = chat._new_session(username="anna"), chat._new_session(username="bob")
    for _ in range(2):
        _run("message", {"content": "vraag"}, anna)
    assert _geweigerd(_run("message", {"content": "vraag"}, anna)[1])
    assert not _geweigerd(_run("message", {"content": "vraag"}, bob)[1])


def test_gasten_tellen_per_verbinding_en_een_reset_helpt_niet(limiet):
    een, twee = chat._new_session(), chat._new_session()
    assert een["username"] == FALLBACK_USER and een["verbinding"] != twee["verbinding"]
    for _ in range(2):
        _run("message", {"content": "vraag"}, een)
    chat._reset_session(een)
    assert _geweigerd(_run("message", {"content": "vraag"}, een)[1])
    assert not _geweigerd(_run("message", {"content": "vraag"}, twee)[1])


def test_verduidelijking_dashboard_en_rapport_tellen_mee(limiet):
    session = chat._new_session(username="anna")
    assert not _geweigerd(_run("clarification_choice", {"choice": "Laatste schooljaar"}, session)[1])
    assert not _geweigerd(_run("generate_dashboard", {}, session)[1])
    assert _geweigerd(_run("generate_report", {}, session)[1])


def test_voorbeeldvragen_kosten_geen_model_en_tellen_niet_mee(limiet):
    session = chat._new_session(username="anna")
    starter = next(iter(TAG_STARTERS))
    for _ in range(3):
        _, events = _run("message", {"content": starter}, session)
        assert any(e.get("type") == "starter_questions" for e in events) and not _geweigerd(events)


def test_de_limiet_komt_uit_de_configuratie():
    from core.config import CHAT_RATE_LIMIT, CHAT_RATE_WINDOW_S

    assert chat._berichtlimiter._max == CHAT_RATE_LIMIT
    assert chat._berichtlimiter._window == CHAT_RATE_WINDOW_S
