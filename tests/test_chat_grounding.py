"""Getallen in een chatantwoord komen uit de data van het gesprek (#185).

Live-audit 7a: de chat gaf 6.340 waar de toolrijen 5.943 optelden, en "9,5%"
waar het 9,6% was. Rapport en dashboard werden gecontroleerd, de chat niet.
"""
import asyncio
import importlib
import json

import pandas as pd

from agent.stream import StreamResult
from tools import store
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_QUERY = {"id": "q", "name": "query_data", "arguments": '{"data_key": "duo:p02"}'}
_ROWS = json.dumps({"data_key": "duo:p02:a", "rijen": [{"AANTAL": 5943}]})


def _chat(monkeypatch, steps: list[StreamResult], messages=None, tool_result: str = _ROWS):
    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    async def fake_execute_tool(call, emit):
        return tool_result, None

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
    assert end["type"] == "message_end" and "controle" not in end


def test_number_that_stays_unsourced_is_flagged_on_the_answer(monkeypatch):
    text, events = _chat(monkeypatch, [
        StreamResult(text="", tool_calls=[_QUERY]),
        StreamResult(text="In totaal 6.340 eerstejaars.", tool_calls=[]),
        StreamResult(text="Toch 6.340.", tool_calls=[]),
    ])

    assert text == "Toch 6.340."
    assert events[-1]["type"] == "message_end"
    assert events[-1]["controle"] == ["6.340 staat niet in de opgehaalde data."]


def test_number_from_an_earlier_turn_is_sourced(monkeypatch):
    earlier = [
        {"role": "user", "content": "Hoeveel voltijdstudenten had de HU in 2021?"},
        {"role": "assistant", "content": "In 2021/22 waren het 28.355 personen."},
        {"role": "user", "content": "Herhaal dat getal."},
    ]
    text, events = _chat(monkeypatch, [StreamResult(text="Het waren 28.355 personen.", tool_calls=[])], earlier)

    assert text == "Het waren 28.355 personen."
    assert "message_cancel" not in [e["type"] for e in events]
    assert "controle" not in events[-1]


def test_wrong_schooljaar_gets_a_correction_with_the_right_code(monkeypatch):
    """Live-audit 7a: gevraagd 2025/26, geselecteerd 2024, antwoord 7.418 (#187)."""
    import pandas as pd

    from tools import store
    from tools.store import KeyMeta

    store.clear()
    store.put("duo:p01hoinges:3", pd.DataFrame({"STUDIEJAAR": [2024, 2025], "AANTAL": [7418, 7408]}),
              KeyMeta(bron="duo", dataset="p01hoinges", resource=3, periodekolom="STUDIEJAAR", schooljaren=(2024, 2025)))
    query = lambda jaar, cid: {"id": cid, "name": "query_data",  # noqa: E731
                               "arguments": json.dumps({"data_key": "duo:p01hoinges:3", "filters": {"STUDIEJAAR": jaar}})}
    steps = [
        StreamResult(text="", tool_calls=[query(2024, "a")]),
        StreamResult(text="In 2025/26 waren het 7.418 deeltijdstudenten.", tool_calls=[]),
        StreamResult(text="", tool_calls=[query(2025, "b")]),
        StreamResult(text="In 2025/26 waren het 7.408 deeltijdstudenten.", tool_calls=[]),
    ]
    seen: list = []

    async def fake_completion(*args, **kwargs):
        seen.append(list(kwargs["messages"]))
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    text = asyncio.run(run_module.run(
        [{"role": "user", "content": "Hoeveel deeltijdstudenten had de HU in 2025/26?"}], {}, emit,
        asyncio.Event(), model="openai/gpt-4o",
    ))
    store.clear()

    assert text == "In 2025/26 waren het 7.408 deeltijdstudenten."
    correctie = seen[2][-1]["content"]
    assert "2025/26" in correctie and "STUDIEJAAR=2025" in correctie
    assert "controle" not in events[-1]


def test_other_institution_gets_a_correction_with_the_right_code(monkeypatch):
    """Live-audit 2: gevraagd de HU, gefilterd op 30TX (Aeres), reeks van Aeres getoond (#143)."""
    import pandas as pd

    from tools import store
    from tools.store import KeyMeta

    store.clear()
    store.put("duo:p01hoinges:3", pd.DataFrame({
        "INSTELLINGSCODE_ACTUEEL": ["25DW", "30TX"], "INSTELLINGSNAAM_ACTUEEL": ["Hogeschool Utrecht", "Aeres Hogeschool"],
        "AANTAL": [26370, 2880],
    }), KeyMeta(bron="duo", dataset="p01hoinges", resource=3,
                instellingskolom="INSTELLINGSCODE_ACTUEEL", instellingen=("25DW", "30TX")))
    query = lambda code, cid: {"id": cid, "name": "query_data",  # noqa: E731
                               "arguments": json.dumps({"data_key": "duo:p01hoinges:3",
                                                        "filters": {"INSTELLINGSCODE_ACTUEEL": code}})}
    steps = [
        StreamResult(text="", tool_calls=[query("30TX", "a")]),
        StreamResult(text="De HU had 2.880 voltijdstudenten.", tool_calls=[]),
        StreamResult(text="", tool_calls=[query("25DW", "b")]),
        StreamResult(text="De HU had 26.370 voltijdstudenten.", tool_calls=[]),
    ]
    seen: list = []

    async def fake_completion(*args, **kwargs):
        seen.append(list(kwargs["messages"]))
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    text = asyncio.run(run_module.run(
        [{"role": "user", "content": "Hoeveel voltijdstudenten had de HU?"}], {}, emit, asyncio.Event(),
        model="openai/gpt-4o",
    ))
    store.clear()

    assert text == "De HU had 26.370 voltijdstudenten."
    correctie = seen[2][-1]["content"]
    assert "Hogeschool Utrecht (25DW)" in correctie and "INSTELLINGSCODE_ACTUEEL=25DW" in correctie
    assert "controle" not in events[-1]


def test_count_on_a_truncated_rio_page_gets_a_correction(monkeypatch):
    # Live-audit 8 (#195): de tool meldde meer_beschikbaar, het antwoord zei toch "landelijk 50".
    store.clear()
    store.put("rio:erkenningen", pd.DataFrame({"code": range(50)}),
              KeyMeta(bron="rio", dataset="erkenningen", volledig=False))
    page = json.dumps({"data_key": "rio:erkenningen", "opgehaalde_rijen": 50, "meer_beschikbaar": True})
    text, events = _chat(monkeypatch, [
        StreamResult(text="", tool_calls=[{"id": "r", "name": "get_rio_data", "arguments": "{}"}]),
        StreamResult(text="Er zijn landelijk 50 erkenningen.", tool_calls=[]),
        StreamResult(text="Het landelijke totaal is met deze data niet vast te stellen.", tool_calls=[]),
    ], tool_result=page)
    store.clear()

    assert text == "Het landelijke totaal is met deze data niet vast te stellen."
    assert "message_cancel" in [e["type"] for e in events]


def test_wrong_label_next_to_a_correct_number_gets_a_correction(monkeypatch):
    # Live-audit 8 (#196): het getal klopte, de opleidingsvorm erbij niet.
    text, events = _chat(monkeypatch, [
        StreamResult(text="", tool_calls=[_QUERY]),
        StreamResult(text="Deeltijd (DU): 5.943 eerstejaars.", tool_calls=[]),
        StreamResult(text="Deeltijd (DT): 5.943 eerstejaars.", tool_calls=[]),
    ])

    assert text == "Deeltijd (DT): 5.943 eerstejaars."
    assert "message_cancel" in [e["type"] for e in events]
