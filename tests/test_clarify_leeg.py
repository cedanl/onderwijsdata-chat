"""Een verduidelijkingskaart zonder vraag of opties komt nooit bij de gebruiker (#1067).

Een `clarify_scope` met kapotte JSON-argumenten, zonder `vraag` of met te weinig `opties` beëindigde de beurt toch en
gaf een lege kaart: een bubbel zonder inhoud. Nu krijgt het model dezelfde terugmelding als bij elke andere tool en
gaat de beurt door; alleen een kaart met een vraag en minstens twee opties eindigt de beurt.
"""

import asyncio
import importlib
import json

import pytest

from agent.loop import ToolCall
from agent.run import verduidelijking_afgekeurd
from agent.stream import StreamResult

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_VRAAG = "Hoe komt het dat het aantal eerstejaars in de techniek daalt?"
_GOED = json.dumps({"vraag": "Welk schooljaar?", "opties": [{"label": "2024/25"}, {"label": "2025/26"}]})
_KAPOT = '{"vraag": "Welk schooljaar?", "opties": [niet-json'
_ANTWOORD = "Ik ga uit van het laatste schooljaar."


def _aanroep(arguments: str) -> StreamResult:
    return StreamResult(text="", tool_calls=[{"id": "c1", "name": "clarify_scope", "arguments": arguments}])


def _beurt(monkeypatch, stappen: list[StreamResult]) -> tuple[list[dict], list[list[dict]]]:
    """Eén chatbeurt met een nagebootst model; geeft de events en de berichten die het model per ronde kreeg."""
    gezien: list[list[dict]] = []

    async def fake_completion(*args, **kwargs):
        gezien.append(list(kwargs["messages"]))
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(run_module.run([{"role": "user", "content": _VRAAG}], {}, emit, asyncio.Event(), model="openai/gpt-4o"))
    return events, gezien


@pytest.mark.parametrize(
    "arguments",
    [
        _KAPOT,
        "{}",
        json.dumps({"vraag": "x", "opties": []}),
        json.dumps({"vraag": "x", "opties": [{"label": "Een"}]}),
        json.dumps({"vraag": "   ", "opties": [{"label": "A"}, {"label": "B"}]}),
        json.dumps({"vraag": "x", "opties": [{"label": "A"}, {"beschrijving": "geen label"}]}),
        json.dumps({"vraag": "x", "opties": "A of B"}),
    ],
)
@pytest.mark.usefixtures("zonder_scopekaart")
def test_een_kapotte_of_lege_verduidelijking_beeindigt_de_beurt_niet(monkeypatch, arguments):
    events, gezien = _beurt(monkeypatch, [_aanroep(arguments), StreamResult(text=_ANTWOORD, tool_calls=[])])

    assert not [e for e in events if e["type"] in ("clarification", "message_cancel")], events
    assert events[-1]["type"] == "message_end" and _ANTWOORD in events[-1]["content"]
    terugmelding = next(m for m in gezien[1] if m["role"] == "tool")
    assert terugmelding["content"].startswith("Fout:") and "clarify_scope" in terugmelding["content"]


@pytest.mark.usefixtures("zonder_scopekaart")
def test_een_kapotte_aanroep_krijgt_de_melding_van_elke_andere_tool(monkeypatch):
    _, gezien = _beurt(monkeypatch, [_aanroep(_KAPOT), StreamResult(text=_ANTWOORD, tool_calls=[])])

    terugmelding = next(m for m in gezien[1] if m["role"] == "tool")
    assert "geen geldige JSON" in terugmelding["content"]


@pytest.mark.usefixtures("zonder_scopekaart")
def test_na_een_lege_aanroep_mag_het_model_alsnog_een_goede_kaart_stellen(monkeypatch):
    events, _ = _beurt(monkeypatch, [_aanroep("{}"), _aanroep(_GOED)])

    kaarten = [e for e in events if e["type"] == "clarification"]
    assert len(kaarten) == 1
    assert kaarten[0]["vraag"] == "Welk schooljaar?" and len(kaarten[0]["opties"]) == 2


@pytest.mark.usefixtures("zonder_scopekaart")
def test_een_geldige_kaart_werkt_als_voorheen(monkeypatch):
    events, _ = _beurt(monkeypatch, [_aanroep(_GOED)])

    assert [e["type"] for e in events if e["type"] in ("message_cancel", "clarification")] == [
        "message_cancel",
        "clarification",
    ]


@pytest.mark.parametrize(
    ("args", "afgekeurd"),
    [
        ({"vraag": "Welk jaar?", "opties": [{"label": "A"}, {"label": "B"}]}, False),
        ({"vraag": "Welk jaar?", "opties": ["A", "B", "C"]}, False),
        ({"vraag": "Welk jaar?", "opties": [{"label": "A"}, "B"]}, False),
        ({"vraag": "Welk jaar?"}, True),
        ({"opties": [{"label": "A"}, {"label": "B"}]}, True),
        ({"vraag": 5, "opties": [{"label": "A"}, {"label": "B"}]}, True),
        ({"vraag": "Welk jaar?", "opties": ["A", ""]}, True),
        ({"vraag": "Welk jaar?", "opties": [{"label": "A"}, 7]}, True),
    ],
)
def test_alleen_een_vraag_met_minstens_twee_opties_is_een_kaart(args, afgekeurd):
    call = ToolCall("c1", "clarify_scope", json.dumps(args), args)

    assert (verduidelijking_afgekeurd(call) is not None) is afgekeurd
