"""Het stappenbudget eindigt in een antwoord, niet in 'Probeer een specifiekere vraag' (#381, #332).

Eerst krijgt het model één afrondronde zonder tools. Lukt ook dat niet, dan zegt
code wat er wel is opgehaald en waar het vastliep: filter, bron of budget.
"""

import asyncio
import importlib
import json

import pandas as pd
import pytest

from agent.budget import AFRONDEN, DEELANTWOORD, zonder_antwoord
from agent.stream import StreamResult
from tools import fouten, store
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")


@pytest.fixture(autouse=True)
def _clean_store():
    store.clear()
    yield
    store.clear()


def _geladen(key="duo:p01hoinges:0"):
    store.put(key, pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron="duo", dataset="p01hoinges", resource=0))
    return json.dumps({"data_key": key, "totaal_rijen": 1})


_LEEG = json.dumps({"data_key": "duo:p01hoinges:0:ab", "totaal_rijen": 0, "rijen": []})
_ONBEREIKBAAR = fouten.melding(fouten.Fout.BRON_ONBEREIKBAAR, "CBS is nu niet bereikbaar (ConnectTimeout).")


def test_noemt_wat_wel_is_opgehaald():
    tekst = zonder_antwoord([("get_duo_data", _geladen()), ("get_duo_data", _geladen())])
    assert "DUO, dataset p01hoinges, resource 0" in tekst
    assert tekst.count("p01hoinges") == 1
    assert "specifieker" not in tekst


def test_vastgelopen_filter_heet_zo():
    tekst = zonder_antwoord(
        [("get_duo_data", _geladen()), ("query_data", _LEEG), ("query_data", "Kolom X bestaat niet")]
    )
    assert "filteren" in tekst
    assert "2 filterstappen" in tekst


def test_onbereikbare_bron_heet_zo():
    tekst = zonder_antwoord([("get_cbs_data", _ONBEREIKBAAR)])
    assert "niet bereikbaar" in tekst
    assert "Er is nog geen data opgehaald." in tekst


def test_anders_is_het_budget_op():
    tekst = zonder_antwoord([("search_catalog", "[]")])
    assert "maximale aantal stappen" in tekst


# ── In de chat ───────────────────────────────────────────────────────────────


def _chat(monkeypatch, steps: list[StreamResult], tool_result: str):
    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    async def fake_execute_tool(call, emit):
        return tool_result, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    monkeypatch.setattr(run_module, "MAX_TOOL_ITERATIONS", 2)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    session: dict = {}
    text = asyncio.run(
        run_module.run([{"role": "user", "content": "Hoeveel mbo-studenten?"}], session, emit, asyncio.Event())
    )
    return text, events


def _tools(n: int) -> list[StreamResult]:
    call = {"name": "get_duo_data", "arguments": '{"dataset_id": "p01hoinges"}'}
    return [StreamResult(text="", tool_calls=[{"id": str(i), **call}]) for i in range(n)]


def test_afrondronde_geeft_een_deelantwoord(monkeypatch):
    text, events = _chat(monkeypatch, [*_tools(2), StreamResult(text="Er is data geladen.", tool_calls=[])], _geladen())
    assert text == f"{DEELANTWOORD}\n\nEr is data geladen."
    assert events[-1]["type"] == "message_end"
    assert not any(e["type"] == "error" for e in events)


def test_deelantwoord_is_gemarkeerd_voor_de_herstelknop(monkeypatch):
    # Een ander model lukt vaak wel (#405, UX N10): de frontend toont dan 'Opnieuw met …'.
    _, events = _chat(monkeypatch, [*_tools(2), StreamResult(text="Er is data geladen.", tool_calls=[])], _geladen())
    assert events[-1]["partial"] is True


def test_zonder_afronding_zegt_code_wat_er_is(monkeypatch):
    text, events = _chat(monkeypatch, _tools(3), _geladen())
    end = events[-1]
    assert end["type"] == "message_end"
    assert end["content"] == text
    assert end["partial"] is True
    assert end["bronnen"] == []  # geen dataantwoord: geen vaste bouwstenen (#416)
    assert "DUO, dataset p01hoinges" in text
    assert not any(e["type"] == "error" for e in events)


def test_afronden_vraagt_om_te_zeggen_wat_ontbreekt():
    assert "geen tools" in AFRONDEN
    assert "wat je niet" in AFRONDEN
