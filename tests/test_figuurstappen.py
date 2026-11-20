"""De server legt bij elke figuur uit het gesprek haar stap vast, zodat het rapport haar opnieuw kan maken (#993)."""

import asyncio
import importlib
import json

import pandas as pd
import plotly.graph_objects as go
import pytest

from agent import figuurstappen
from agent.loop import ToolCall
from agent.session_data import neem_beurtbewijs
from tools import store
from tools.schemas import TOOL_CREATE_CHOROPLETH_MAP, TOOL_CREATE_PLOT, TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS

run_module = importlib.import_module("agent.run")

_KEY = "test:figuurstap993"
_ANDER = "test:figuurstap993:ander"
_PLOT = {"data_key": _KEY, "chart_type": "bar", "x": "JAAR", "y": "AANTAL", "title": "Aantal per jaar"}


@pytest.fixture(autouse=True)
def _data():
    store.put(_KEY, pd.DataFrame({"JAAR": [2023, 2024], "AANTAL": [10, 12]}))
    store.put(_ANDER, pd.DataFrame({"JAAR": [2023], "AANTAL": [3]}))


def _figuur(titel: str = "Aantal per jaar") -> go.Figure:
    return go.Figure(go.Bar(x=[2023, 2024], y=[10, 12]), layout={"title": {"text": titel}})


def test_een_grafiek_legt_tool_argumenten_titel_en_key_vast():
    sessie: dict = {}

    figuurstappen.leg_vast(sessie, TOOL_CREATE_PLOT, _PLOT, "Staafgrafiek aangemaakt.", _figuur())

    assert figuurstappen.stappen(sessie) == [
        {
            "id": figuurstappen.figuur_id(TOOL_CREATE_PLOT, _PLOT),
            "tool": TOOL_CREATE_PLOT,
            "arguments": _PLOT,
            "titel": "Aantal per jaar",
            "keys": [_KEY],
        }
    ]


def test_de_id_volgt_uit_tool_en_argumenten():
    assert figuurstappen.figuur_id(TOOL_CREATE_PLOT, _PLOT) == figuurstappen.figuur_id(TOOL_CREATE_PLOT, dict(_PLOT))
    assert figuurstappen.figuur_id(TOOL_CREATE_PLOT, _PLOT) != figuurstappen.figuur_id(
        TOOL_CREATE_PLOT, {**_PLOT, "chart_type": "line"}
    )
    assert len(figuurstappen.figuur_id(TOOL_CREATE_PLOT, _PLOT)) == 12


def test_dezelfde_stap_twee_keer_is_een_figuur():
    sessie: dict = {}
    for _ in range(2):
        figuurstappen.leg_vast(sessie, TOOL_CREATE_PLOT, _PLOT, "ok", _figuur())

    assert len(figuurstappen.stappen(sessie)) == 1


@pytest.mark.parametrize(
    ("tool", "argumenten", "resultaat", "figuur"),
    [
        (TOOL_CREATE_PLOT, _PLOT, "ok", None),  # geen figuur
        (TOOL_QUERY_DATA, {"data_key": _KEY}, "ok", _figuur()),  # geen figuurtool
        (TOOL_CREATE_PLOT, {**_PLOT, "data": [{"JAAR": 1, "AANTAL": 99}]}, "ok", _figuur()),  # rijen van het model
        (TOOL_CREATE_PLOT, {k: v for k, v in _PLOT.items() if k != "data_key"}, "ok", _figuur()),  # geen key
        (TOOL_CREATE_PLOT, "geen dict", "ok", _figuur()),
    ],
    ids=["zonder-figuur", "andere-tool", "data-van-het-model", "zonder-key", "kapotte-argumenten"],
)
def test_wat_niet_opnieuw_te_maken_is_wordt_niet_vastgelegd(tool, argumenten, resultaat, figuur):
    sessie: dict = {}

    figuurstappen.leg_vast(sessie, tool, argumenten, resultaat, figuur)

    assert figuurstappen.stappen(sessie) == []


def test_een_script_rust_op_zijn_data_key_de_key_die_het_maakte_en_wat_het_las():
    code = f"a = store_get('{_ANDER}')\nresult = df.to_dict('records')"
    resultaat = json.dumps({"data_key": "analysis:abc123", "rijen": []})
    sessie: dict = {}

    figuurstappen.leg_vast(sessie, TOOL_RUN_ANALYSIS, {"code": code, "data_key": _KEY}, resultaat, _figuur())

    assert figuurstappen.stappen(sessie)[0]["keys"] == [_KEY, "analysis:abc123", _ANDER]


def test_een_script_zonder_data_key_rust_op_wat_het_las():
    code = f"a = store_get('{_ANDER}')\nresult = {{'n': len(a)}}"
    resultaat = json.dumps({"gelezen": [_ANDER], "resultaat": {"n": 1}})
    sessie: dict = {}

    figuurstappen.leg_vast(sessie, TOOL_RUN_ANALYSIS, {"code": code}, resultaat, _figuur())

    assert figuurstappen.stappen(sessie)[0]["keys"] == [_ANDER]


def test_de_titel_is_platte_tekst_op_een_regel_en_begrensd():
    assert figuurstappen.titel(_figuur("Instroom<br><b>2020–2024</b>")) == "Instroom 2020–2024"
    assert figuurstappen.titel(go.Figure()) == ""
    lang = figuurstappen.titel(_figuur("x" * 500))
    assert len(lang) == figuurstappen.MAX_TITEL and lang.endswith("…")


def test_nieuwe_stappen_gaan_in_de_rij_van_de_volgende_afgeronde_beurt():
    sessie: dict = {}
    figuurstappen.leg_vast(sessie, TOOL_CREATE_PLOT, _PLOT, "ok", _figuur())

    assert [s["tool"] for s in figuurstappen.neem_nieuwe(sessie)] == [TOOL_CREATE_PLOT]
    assert figuurstappen.neem_nieuwe(sessie) == []
    assert len(figuurstappen.stappen(sessie)) == 1  # de sessie houdt ze


def test_de_sessie_kent_hoogstens_de_laatste_stappen():
    sessie: dict = {}
    for i in range(figuurstappen._MAX_STAPPEN + 5):
        figuurstappen.leg_vast(sessie, TOOL_CREATE_PLOT, {**_PLOT, "title": f"T{i}"}, "ok", _figuur())

    stappen = figuurstappen.stappen(sessie)
    assert len(stappen) == figuurstappen._MAX_STAPPEN and stappen[-1]["arguments"]["title"] == f"T{i}"


def test_de_chat_legt_de_stap_vast_als_een_tool_een_figuur_gaf():
    """`run._bewaar_stap` is de plek waar de chat elke toolstap ziet: daar komt de figuurstap vandaan."""
    sessie: dict = {"messages": [{"role": "user", "content": "Maak een kaart"}]}
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    call = ToolCall(id="c", name=TOOL_CREATE_CHOROPLETH_MAP, arguments="{}", args={"data_key": _KEY, "title": "Kaart"})
    asyncio.run(run_module._bewaar_stap(sessie, emit, call, "Kaart 'Kaart' aangemaakt.", _figuur("Kaart")))

    [stap] = figuurstappen.stappen(sessie)
    assert stap["tool"] == TOOL_CREATE_CHOROPLETH_MAP and stap["titel"] == "Kaart"
    assert [e["type"] for e in events] == ["figure"]
    # Lineage, rekenbewijs en bronregels gaan los van de figuurstappen.
    assert neem_beurtbewijs(sessie)[0] == {}
