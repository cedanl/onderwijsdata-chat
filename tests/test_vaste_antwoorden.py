"""Betekenisvragen over -1 en weigeringen komen uit code (#324, #330)."""

import asyncio
import importlib

import pytest

from agent.stream import StreamResult
from agent.vaste_antwoorden import SENTINEL_ANTWOORD, WEIGER_ANTWOORD, sentinelvraag, weigering

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")


@pytest.mark.parametrize(
    "vraag",
    [
        "Wat betekent −1 in DUO-data?",
        "wat betekent -1 in de data",
        "Wat is -1 bij DUO?",
        "Waarvoor staat − 1 in een cel?",
    ],
)
def test_betekenisvraag_over_min_een_krijgt_het_vaste_antwoord(vraag):
    assert sentinelvraag(vraag) == SENTINEL_ANTWOORD


@pytest.mark.parametrize(
    "vraag",
    ["Hoeveel studenten had de HU in 2024?", "Wat betekent een groei van -1,5% voor het hbo?", "Wat is 21 of -10?"],
)
def test_andere_vragen_zijn_geen_betekenisvraag(vraag):
    assert sentinelvraag(vraag) is None


def test_vast_antwoord_noemt_geen_verzonnen_drempel():
    assert "1–4" not in SENTINEL_ANTWOORD and "onderdrukte cel" in SENTINEL_ANTWOORD


@pytest.mark.parametrize(
    "tekst",
    [
        "Ik kan geen antwoord geven.",
        "Ik kan daar niet mee helpen.",
        "Deze vraag valt daar buiten.",
        "Dat valt buiten mijn bereik.",
    ],
)
def test_weigering_zonder_tools_wordt_het_vaste_antwoord(tekst):
    assert weigering(tekst, []) == WEIGER_ANTWOORD


def test_weigering_na_toolgebruik_blijft_het_antwoord_van_het_model():
    assert weigering("Voor 2019 kan ik geen antwoord geven.", [{"name": "query_data", "arguments": "{}"}]) is None


def test_voorbeeldvragen_gaan_over_onderwijsdata():
    assert "eerstejaars" in WEIGER_ANTWOORD and "?" in WEIGER_ANTWOORD


def _run(monkeypatch, vraag, steps):
    async def fake_completion(*a, **k):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    text = asyncio.run(
        run_module.run([{"role": "user", "content": vraag}], {}, emit, asyncio.Event(), model="openai/gpt-4o")
    )
    return text, events


def test_run_beantwoordt_de_sentinelvraag_zonder_model(monkeypatch):
    text, events = _run(monkeypatch, "Wat betekent −1 in DUO-data?", [])
    assert text == SENTINEL_ANTWOORD
    assert [e["type"] for e in events] == ["message_start", "message_end"]


def test_run_vervangt_een_kale_weigering(monkeypatch):
    text, events = _run(
        monkeypatch, "Wanneer speelt Ajax thuis?", [StreamResult(text="Ik kan geen antwoord geven.", tool_calls=[])]
    )
    assert text == WEIGER_ANTWOORD
    assert events[-1]["content"] == WEIGER_ANTWOORD
