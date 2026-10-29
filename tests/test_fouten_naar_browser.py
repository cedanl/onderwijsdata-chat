"""Geen ruwe uitzonderingstekst naar de browser (#503).

Per pad uit de bevinding: dashboard, rapport en refresh. Alleen een Gebruikersfout
— tekst die voor de gebruiker is geschreven — mag letterlijk door.
"""

import asyncio

import pytest

from agent.report import RAPPORT_GEWEIGERD, RapportGeweigerd
from core.errors import Gebruikersfout
from routes import chat

LEKKENDE_FOUT = ValueError("Expecting value: line 1 column 1 (char 0) in /app/data/cache/x.parquet")


def _emit_verzamelaar():
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    return events, emit


def test_dashboardfout_lekt_geen_exceptietekst(monkeypatch, caplog):
    async def kapot(session, emit, model=None):
        raise LEKKENDE_FOUT

    monkeypatch.setattr(chat, "generate_dashboard_spec", kapot)
    events, emit = _emit_verzamelaar()
    with caplog.at_level("ERROR"):
        asyncio.run(chat._generate_dashboard({"chat_settings": {}}, emit, None))

    fout = next(e for e in events if e["type"] == "error")
    assert "parquet" not in fout["message"] and "Expecting value" not in fout["message"]
    assert "fout-ID" in fout["message"]


def test_dashboard_gebruikersfout_bereikt_de_gebruiker(monkeypatch):
    async def geen_data(session, emit, model=None):
        raise Gebruikersfout("Geen datasets geladen. Stel eerst een vraag waarvoor data wordt opgehaald.")

    monkeypatch.setattr(chat, "generate_dashboard_spec", geen_data)
    events, emit = _emit_verzamelaar()
    asyncio.run(chat._generate_dashboard({"chat_settings": {}}, emit, None))

    fout = next(e for e in events if e["type"] == "error")
    assert "Geen datasets geladen" in fout["message"]


def test_rapportfout_lekt_geen_exceptietekst(monkeypatch, caplog):
    async def kapot(session, emit, model=None, stop_event=None, author=None, onderzoeksvraag=None):
        raise LEKKENDE_FOUT

    monkeypatch.setattr(chat, "generate_report_spec", kapot)
    events, emit = _emit_verzamelaar()
    with caplog.at_level("ERROR"):
        asyncio.run(chat._generate_report({"chat_settings": {}}, emit, None))

    fout = next(e for e in events if e["type"] == "report_error")
    assert "parquet" not in fout["message"] and "Expecting value" not in fout["message"]


def test_rapport_gebruikersfout_bereikt_de_gebruiker(monkeypatch):
    async def geweigerd(session, emit, model=None, stop_event=None, author=None, onderzoeksvraag=None):
        raise RapportGeweigerd

    monkeypatch.setattr(chat, "generate_report_spec", geweigerd)
    events, emit = _emit_verzamelaar()
    asyncio.run(chat._generate_report({"chat_settings": {}}, emit, None))

    fout = next(e for e in events if e["type"] == "report_error")
    assert fout == {"type": "report_error", "message": RAPPORT_GEWEIGERD, "herstel": "rapport"}


def test_refreshfout_lekt_geen_herlaadfouten(monkeypatch):
    """Als geen enkele dataset herlaadt, noemt de melding geen details per call."""

    def alles_mislukt(recipe):
        return [{"name": "get_duo_data", "arguments": "{}", "success": False, "error": "herladen mislukt"}]

    monkeypatch.setattr(chat, "replay_data_calls", alles_mislukt)
    with pytest.raises(chat.RefreshError) as exc_info:
        asyncio.run(chat._do_refresh([{"name": "get_duo_data", "arguments": "{}"}], [], {}))

    assert "herladen mislukt" not in str(exc_info.value)
    assert "De data kon niet opnieuw opgehaald worden: 1 van de 1 dataset(s)" in str(exc_info.value)
