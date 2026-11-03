"""Geen ruwe uitzonderingstekst naar de browser (#503).

Per pad uit de bevinding; dashboard en refresh zijn weg (#765), het rapport blijft. Alleen een Gebruikersfout
— tekst die voor de gebruiker is geschreven — mag letterlijk door.
"""

import asyncio

from agent.report import RAPPORT_GEWEIGERD, RapportGeweigerd
from routes import chat

LEKKENDE_FOUT = ValueError("Expecting value: line 1 column 1 (char 0) in /app/data/cache/x.parquet")


def _emit_verzamelaar():
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    return events, emit


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
