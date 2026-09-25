"""Getallen in een chatantwoord komen uit de data van het gesprek (#185).

Live-audit 7a: de chat gaf 6.340 waar de toolrijen 5.943 optelden, en "9,5%"
waar het 9,6% was. Rapport en dashboard werden gecontroleerd, de chat niet.
"""
import asyncio
import importlib
import json

from agent.stream import StreamResult

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_QUERY = {"id": "q", "name": "query_data", "arguments": '{"data_key": "duo:p02"}'}
_ROWS = json.dumps({"data_key": "duo:p02:a", "rijen": [{"AANTAL": 5943}]})


def _chat(monkeypatch, steps: list[StreamResult], messages=None):
    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    async def fake_execute_tool(call, emit):
        return _ROWS, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    text = asyncio.run(run_module.run(
        messages or [{"role": "user", "content": "Hoeveel eerstejaars?"}], {}, emit, asyncio.Event(),
        model="openai/gpt-4o",
    ))
    return text, events


def test_unsourced_number_gets_one_correction_and_the_unchecked_text_is_withdrawn(monkeypatch):
    text, events = _chat(monkeypatch, [
        StreamResult(text="", tool_calls=[_QUERY]),
        StreamResult(text="In totaal 6.340 eerstejaars.", tool_calls=[]),
        StreamResult(text="In totaal 5.943 eerstejaars.", tool_calls=[]),
    ])

    assert text == "In totaal 5.943 eerstejaars."
    types = [e["type"] for e in events]
    cancel = types.index("message_cancel")
    assert types[cancel + 1:].count("message_start") == 1
    end = events[-1]
    assert end["type"] == "message_end" and "unverified" not in end


def test_number_that_stays_unsourced_is_flagged_on_the_answer(monkeypatch):
    text, events = _chat(monkeypatch, [
        StreamResult(text="", tool_calls=[_QUERY]),
        StreamResult(text="In totaal 6.340 eerstejaars.", tool_calls=[]),
        StreamResult(text="Toch 6.340.", tool_calls=[]),
    ])

    assert text == "Toch 6.340."
    assert events[-1]["type"] == "message_end"
    assert events[-1]["unverified"] == ["6.340"]


def test_number_from_an_earlier_turn_is_sourced(monkeypatch):
    earlier = [
        {"role": "user", "content": "Hoeveel voltijdstudenten had de HU in 2021?"},
        {"role": "assistant", "content": "In 2021/22 waren het 28.355 personen."},
        {"role": "user", "content": "Herhaal dat getal."},
    ]
    text, events = _chat(monkeypatch, [StreamResult(text="Het waren 28.355 personen.", tool_calls=[])], earlier)

    assert text == "Het waren 28.355 personen."
    assert "message_cancel" not in [e["type"] for e in events]
    assert "unverified" not in events[-1]
