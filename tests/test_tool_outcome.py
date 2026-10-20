"""Uitkomst van een toolstap voor de redeneerkaart (#386, #640).

Een filter dat 0 rijen oplevert of faalt, en een opvraag die de scopegrens weigert, mag in
de kaart niet als geslaagde stap staan. De uitkomst wordt in code uit het toolresultaat gelezen.
"""

import asyncio
import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent import loop as loop_module
from tools import TOOL_QUERY_DATA, catalog, outcome, scopeprofiel, store
from tools.query import query_data
from tools.schemas import (
    TOOL_DATASET_DETAILS,
    TOOL_GET_CBS_DATA,
    TOOL_GET_CBS_DIMENSION,
    TOOL_GET_DUO_DATA,
    TOOL_GET_RIO_DATA,
    TOOL_GET_RIO_INSTELLING,
)


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


# Een stap op de scopegrens (#640): de tool weigerde, dus geen groene "CBS data opgehaald".
@pytest.mark.parametrize(
    ("naam", "resultaat", "label"),
    [
        (TOOL_GET_CBS_DATA, scopeprofiel.buiten_scope("CBS"), "CBS-opvraag geweigerd (buiten scope)"),
        (TOOL_GET_DUO_DATA, scopeprofiel.buiten_scope("DUO"), "DUO-opvraag geweigerd (buiten scope)"),
        (TOOL_GET_RIO_DATA, scopeprofiel.buiten_scope("RIO", register=True), "RIO-opvraag geweigerd (buiten scope)"),
        (TOOL_GET_RIO_INSTELLING, scopeprofiel.buiten_scope("RIO"), "RIO-opvraag geweigerd (buiten scope)"),
        (TOOL_DATASET_DETAILS, scopeprofiel.buiten_scope("DUO"), "Opvraag geweigerd (buiten scope)"),
        (TOOL_GET_CBS_DIMENSION, scopeprofiel.buiten_scope("CBS"), "Opvraag geweigerd (buiten scope)"),
    ],
)
def test_een_stap_op_de_scopegrens_heet_geweigerd(naam, resultaat, label):
    uit = outcome(naam, json.dumps(resultaat, ensure_ascii=False))
    assert uit == {"status": "buiten_scope", "status_label": label}


@pytest.mark.parametrize(
    "resultaat",
    [
        json.dumps({"data_key": "cbs:85353NED", "rijen": 10, "melding": "geladen"}),
        json.dumps({"bron": "CBS", "buiten_scope": False}),
        json.dumps({"bron": "CBS", "buiten_scope": "ja"}),
        json.dumps([{"buiten_scope": True}]),
        "Dataset 'X' staat niet in de catalogus.",
    ],
)
def test_een_gewoon_resultaat_van_een_laadtool_heeft_geen_uitkomst(resultaat):
    assert outcome(TOOL_GET_CBS_DATA, resultaat) == {}


def test_tool_end_van_een_po_tabel_heet_geweigerd(monkeypatch):
    """De echte get_cbs_data met een po-tabel uit de catalogus: geen data, dus geen data_key of export_key."""
    po = {"leverancier": "CBS", "_cbs_id": "80040ned", "bron": "Vo; leerlingen", "onderwijstype": ["VO"]}
    caches = (catalog._cbs_alles, catalog._cbs, catalog._rio_duo_alles, catalog._rio_duo)
    monkeypatch.setattr(catalog, "_cbs_catalog", lambda: [po])
    monkeypatch.setattr(catalog, "_rio_catalog", lambda **_: [])
    for c in caches:
        c.cache_clear()
    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    args = {"dataset_id": "80040ned"}
    call = loop_module.ToolCall(id="t1", name=TOOL_GET_CBS_DATA, arguments=json.dumps(args), args=args)
    try:
        with patch("tools.cbs.data") as data:
            asyncio.run(loop_module._execute_tool(call, emit))
    finally:
        for c in caches:
            c.cache_clear()

    data.assert_not_called()
    start = next(e for e in events if e["type"] == "tool_start")
    end = next(e for e in events if e["type"] == "tool_end")
    assert start["label"] == "CBS data opgehaald"  # vóór het resultaat; de uitkomst volgt in tool_end
    assert end["status"] == "buiten_scope"
    assert end["status_label"] == "CBS-opvraag geweigerd (buiten scope)"
    assert "data_key" not in end
    assert "export_key" not in end
