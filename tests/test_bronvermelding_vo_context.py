"""Een antwoord uit een vo-bron noemt bij de bron "vo-context voor vervolgonderwijs", uit code (#1051).

Het label komt uit de catalogus (`bron_titel`), niet uit de tekst van het model. De autouse-fixture in
tests/test_bronvermelding.py vervangt `bron_titel`; dit bestand heeft die fixture niet, dus hier staat de echte
catalogus achter de bronregel.
Gemeten op main (d11c22ac): de bronregel deed het al; dit zijn regressietests.
"""

import asyncio
import importlib
import json

import pandas as pd
import pytest

from agent.bronvermelding import bronnen_van
from agent.stream import StreamResult
from tools import store
from tools.scopeprofiel import VO_CONTEXT_DEEL
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

# Twee vo-bronnen uit VO_CONTEXT (een CBS-tabel en de DUO-prognoses) en twee gewone ho-bronnen.
_VO_BRONNEN = [("cbs", "85566NED", "get_cbs_data"), ("duo", "voprognoses", "get_duo_data")]
_HO_BRONNEN = [("cbs", "85423NED", "get_cbs_data"), ("duo", "p01hoinges", "get_duo_data")]


def _laad(bron: str, dataset: str) -> str:
    key = f"{bron}:{dataset}"
    store.put(key, pd.DataFrame({"AANTAL": [1200]}), KeyMeta(bron=bron, dataset=dataset))
    return key


def _stap(tool: str, key: str) -> tuple[str, str]:
    return tool, json.dumps({"data_key": key})


@pytest.mark.parametrize(("bron", "dataset", "tool"), _VO_BRONNEN)
def test_een_vo_bron_noemt_de_vo_context_in_de_bronregel(bron, dataset, tool):
    [regel] = bronnen_van([_stap(tool, _laad(bron, dataset))])
    assert regel.startswith(f"{bron.upper()} · ")
    assert VO_CONTEXT_DEEL in regel


@pytest.mark.parametrize(("bron", "dataset", "tool"), _HO_BRONNEN)
def test_een_gewone_ho_bron_krijgt_het_label_niet(bron, dataset, tool):
    [regel] = bronnen_van([_stap(tool, _laad(bron, dataset))])
    assert VO_CONTEXT_DEEL not in regel


def _einde(monkeypatch, bron: str, dataset: str, tool: str) -> dict:
    """Een beurt met een nepmodel: één laadstap op de vo-bron, dan een antwoord zonder het label."""
    key = _laad(bron, dataset)
    laad = {"id": "l", "name": tool, "arguments": json.dumps({"dataset_id": dataset})}
    stappen = [
        StreamResult(text="", tool_calls=[laad]),
        StreamResult(text="Na het vmbo stroomt het grootste deel door naar het mbo.", tool_calls=[]),
    ]

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    async def fake_execute_tool(call, emit, recept_van=None):
        return json.dumps({"data_key": key, "rijen": [{"AANTAL": 1200}]}), None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    vraag = "Hoeveel vmbo-leerlingen stromen door naar het mbo?"
    asyncio.run(run_module.run([{"role": "user", "content": vraag}], {}, emit, asyncio.Event(), model="openai/gpt-4o"))
    return next(e for e in reversed(events) if e["type"] == "message_end")


@pytest.mark.parametrize(("bron", "dataset", "tool"), _VO_BRONNEN)
def test_het_einde_van_de_beurt_noemt_de_vo_context_bij_de_bron(monkeypatch, bron, dataset, tool):
    einde = _einde(monkeypatch, bron, dataset, tool)
    assert VO_CONTEXT_DEEL not in einde["content"]  # het model schreef het label niet
    assert any(VO_CONTEXT_DEEL in regel for regel in einde["bronnen"]), einde["bronnen"]
