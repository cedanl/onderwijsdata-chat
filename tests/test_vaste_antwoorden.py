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
        # #403: een langere vraag raakte de regex niet; Opus antwoordde uit het geheugen.
        "In de DUO-data staan soms waarden van -1. Wat betekent dat, en hoe moet ik daarmee rekenen?",
        "Ik zie -1 in het bestand met eerstejaars; waar staat dat voor?",
    ],
)
def test_betekenisvraag_over_min_een_krijgt_het_vaste_antwoord(vraag):
    assert sentinelvraag(vraag) == SENTINEL_ANTWOORD


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel studenten had de HU in 2024?",
        "Wat betekent een groei van -1,5% voor het hbo?",
        "Wat is 21 of -10?",
        "Het aantal daalde met -1 procentpunt; hoeveel studenten zijn dat?",
    ],
)
def test_andere_vragen_zijn_geen_betekenisvraag(vraag):
    assert sentinelvraag(vraag) is None


def test_vast_antwoord_noemt_geen_verzonnen_drempel():
    assert "onderdrukte cel" in SENTINEL_ANTWOORD and "minder dan" not in SENTINEL_ANTWOORD


def test_vast_antwoord_noemt_de_duo_regel_met_bron_en_duo_als_afzender():
    # CH-16 (#423): het antwoord was kaal en sprak over "de app".
    assert "1 t/m 4 gepubliceerd als 4" in SENTINEL_ANTWOORD
    assert "Bron: de DUO-bestandsbeschrijving" in SENTINEL_ANTWOORD
    assert "de app" not in SENTINEL_ANTWOORD


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


def test_bewering_zonder_tools_en_zonder_data_wordt_de_weigering():
    """#403: gpt-oss verzon 'op 30 september 2023' zonder tool of bron."""
    assert weigering("Ajax speelt thuis tegen PSV op 30 september 2023.", []) == WEIGER_ANTWOORD


def test_vervolgvraag_over_eerdere_data_mag_zonder_tools_een_getal_noemen():
    assert weigering("Dat is een daling van 2,8%.", [], eerder_gesprek=True) is None


def test_antwoord_zonder_getal_en_zonder_tools_blijft():
    assert weigering("Hallo! Stel gerust een vraag over onderwijsdata.", []) is None


def test_run_vervangt_een_verzonnen_feit_zonder_tools(monkeypatch):
    text, _ = _run(
        monkeypatch,
        "Wanneer speelt Ajax thuis tegen PSV?",
        [StreamResult(text="Ajax speelt thuis tegen PSV op 30 september 2023.", tool_calls=[])] * 3,
    )
    assert text == WEIGER_ANTWOORD
