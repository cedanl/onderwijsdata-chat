"""Uitkomst van een toolstap voor de redeneerkaart (#386).

Een filter dat 0 rijen oplevert of faalt, mag in de kaart niet als geslaagde
stap staan. De uitkomst wordt in code uit het toolresultaat gelezen.
"""

import asyncio
import json

import pandas as pd

from agent import loop as loop_module
from tools import TOOL_QUERY_DATA, outcome, store
from tools.query import query_data


def _leeg() -> str:
    return json.dumps(
        {"data_key": "k", "totaal_rijen": 0, "rijen": [], "melding": "0 rijen", "suggesties": {"Niveau": ["Hbo", "Wo"]}}
    )


def test_gevuld_filter_is_geslaagd():
    result = json.dumps({"data_key": "k", "totaal_rijen": 1, "rijen": [{"N": 1}]})
    assert outcome(TOOL_QUERY_DATA, result) == {}


def test_leeg_filter_heet_leeg_met_bestaande_waarden():
    uit = outcome(TOOL_QUERY_DATA, _leeg())
    assert uit["status"] == "empty"
    assert uit["status_label"] == "Filter leverde 0 rijen op"
    assert uit["suggesties"] == {"Niveau": ["Hbo", "Wo"]}


def test_foutmelding_van_query_data_heet_mislukt():
    uit = outcome(TOOL_QUERY_DATA, "Kolommen niet gevonden: ['X']. Beschikbaar: ['A']")
    assert uit == {"status": "error", "status_label": "Filter mislukt"}


def test_dispatchfout_heet_mislukt():
    assert outcome(TOOL_QUERY_DATA, "Fout bij uitvoeren van query_data: boem")["status"] == "error"


def test_andere_tools_krijgen_geen_uitkomst():
    assert outcome("search_catalog", "[]") == {}


def test_echte_query_data_zonder_treffers_heet_leeg():
    df = pd.DataFrame({"Niveau": ["Hbo", "Wo"], "N": [1, 2]})
    store.put("cbs:test:uitkomst", df, store.KeyMeta(bron="cbs", dataset="test:uitkomst"))
    result = query_data("cbs:test:uitkomst", filters={"Niveau": "T001038"})
    assert outcome(TOOL_QUERY_DATA, result)["status"] == "empty"


def test_tool_end_event_draagt_de_uitkomst(monkeypatch):
    monkeypatch.setattr(loop_module, "dispatch", lambda name, args: (_leeg(), None))
    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    args = {"data_key": "k", "filters": {"Niveau": "T001038"}}
    call = loop_module.ToolCall(id="t1", name=TOOL_QUERY_DATA, arguments=json.dumps(args), args=args)
    asyncio.run(loop_module._execute_tool(call, emit))

    end = next(e for e in events if e["type"] == "tool_end")
    assert end["status"] == "empty"
    assert end["status_label"] == "Filter leverde 0 rijen op"
