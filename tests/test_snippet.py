import asyncio
import json
import sys
import types
from typing import Any
from unittest.mock import patch

import pandas as pd
import plotly.graph_objects as go
import pytest

from agent import loop as loop_module
from tools import store
from tools.kpi import compute_kpi
from tools.query import query_data
from tools.snippet import generate


def test_query_data_with_filters_and_aggregation():
    snippet = generate(
        "query_data",
        {
            "data_key": "duo:p02ho1ejrs:Eerstejaarsingeschrevenen wo",
            "filters": {"INSTELLINGSNAAM_ACTUEEL": "VU Amsterdam", "TYPE_HOGER_ONDERWIJS": "bachelor"},
            "group_by": ["STUDIEJAAR"],
            "aggregate": {"AANTAL": "sum"},
        },
    )
    assert snippet is not None
    assert 'duo.load("p02ho1ejrs"' in snippet
    # Dezelfde semantiek als query_data: tekstvorm, zonder hoofdletters (#227).
    assert "df[df['INSTELLINGSNAAM_ACTUEEL'].astype(str).str.lower().isin(['vu amsterdam'])]" in snippet
    assert "groupby" in snippet
    assert "print(df)" in snippet


def test_query_data_minimal():
    snippet = generate("query_data", {"data_key": "duo:abc:resource"})
    assert snippet is not None
    assert 'duo.load("abc"' in snippet
    assert "groupby" not in snippet


def test_query_data_with_columns():
    snippet = generate(
        "query_data",
        {
            "data_key": "duo:x:y",
            "columns": ["A", "B"],
        },
    )
    assert snippet is not None
    assert "['A', 'B']" in snippet


def test_query_data_cbs_key_without_known_load_says_so_instead_of_naming_the_store():
    snippet = generate("query_data", {"data_key": "cbs:83753NED:abc123"})
    assert snippet is not None
    assert "store" not in snippet
    assert "Geen laadstap bekend" in snippet


def test_query_data_filter_operators():
    snippet = generate(
        "query_data",
        {
            "data_key": "duo:x:y",
            "filters": {"JAAR__gte": 2020, "REGIO__in": ["Noord", "Zuid"]},
        },
    )
    assert snippet is not None
    assert ">=" in snippet
    assert "isin" in snippet


def test_query_data_filter_plain_key_list():
    snippet = generate(
        "query_data",
        {
            "data_key": "duo:x:y",
            "filters": {"SECTOR": ["Techniek", "Zorg"]},
        },
    )
    assert snippet is not None
    assert "isin" in snippet
    assert "SECTOR" in snippet


def test_run_analysis_returns_code():
    code = "result = df.sum()"
    snippet = generate("run_analysis", {"code": code})
    assert snippet is not None
    assert snippet == code


def test_get_duo_data():
    snippet = generate("get_duo_data", {"dataset_id": "p02ho1ejrs", "resource": "Eerstejaarsingeschrevenen wo"})
    assert snippet is not None
    assert 'duo.load("p02ho1ejrs"' in snippet
    assert "Eerstejaarsingeschrevenen wo" in snippet


def test_get_cbs_data_with_filters():
    snippet = generate(
        "get_cbs_data",
        {
            "dataset_id": "83753NED",
            "filters": {"$filter": "Perioden eq '2023JJ00'"},
        },
    )
    assert snippet is not None
    assert 'data("83753NED"' in snippet
    assert "Perioden" in snippet


def test_create_plot_with_data_key():
    snippet = generate(
        "create_plot",
        {
            "data_key": "duo:p02ho1ejrs:resource:result",
            "chart_type": "line",
            "x": "STUDIEJAAR",
            "y": "AANTAL",
            "title": "Test grafiek",
        },
    )
    assert snippet is not None
    assert "px.line" in snippet
    assert "store" not in snippet
    assert "STUDIEJAAR" in snippet
    # Geen gehardcode data-waarden
    assert "[{" not in snippet


@pytest.mark.parametrize(
    "args, functie",
    [
        ({"x": "STUDIEJAAR"}, "px.line"),  # auto op een tijdas: create_plot tekent een lijn (#240)
        ({"x": "STUDIEJAAR", "chart_type": "bar"}, "px.bar"),
        ({"x": "SECTOR", "is_share": True}, "px.pie"),
    ],
)
def test_create_plot_snippet_volgt_het_grafiektype_van_de_app(args, functie):
    """Audit 11: de tool meldde een lijngrafiek, de snippet gaf px.bar (#245)."""
    snippet = generate("create_plot", {"data_key": "duo:x:y:result", "y": "AANTAL", "title": "t", **args})
    assert f"fig = {functie}(" in snippet


def test_create_plot_with_inline_data_fallback():
    snippet = generate(
        "create_plot",
        {
            "data": [{"JAAR": 2021, "AANTAL": 100}],
            "chart_type": "bar",
            "x": "JAAR",
            "y": "AANTAL",
            "title": "Test",
        },
    )
    assert snippet is not None
    assert "px.bar" in snippet
    assert "2021" in snippet


def test_create_plot_with_color_by():
    snippet = generate(
        "create_plot",
        {
            "data_key": "duo:x:y:result",
            "chart_type": "bar",
            "x": "X",
            "y": "Y",
            "title": "t",
            "color_by": "G",
        },
    )
    assert snippet is not None
    assert 'color="G"' in snippet


def test_create_choropleth_with_data_key():
    snippet = generate(
        "create_choropleth_map",
        {
            "data_key": "cbs:83753NED:result",
            "location_col": "RegioS",
            "value_col": "Waarde",
            "title": "Kaart",
        },
    )
    assert snippet is not None
    assert "store" not in snippet
    assert "choropleth_map" in snippet
    assert "RegioS" in snippet


def test_create_choropleth_with_inline_data():
    snippet = generate(
        "create_choropleth_map",
        {
            "data": [{"RegioS": "PV20", "Waarde": 100}],
            "location_col": "RegioS",
            "value_col": "Waarde",
            "title": "Kaart",
        },
    )
    assert snippet is not None
    assert "PV20" in snippet
    assert "DataFrame" in snippet


def test_unknown_tool_returns_none():
    assert generate("search_catalog", {"query": "test"}) is None


# --- #131: een snippet draait buiten de app, met alleen de gedocumenteerde pakketten ---

_ROWS = [{"JAAR": 2021, "AANTAL": 10}, {"JAAR": 2022, "AANTAL": 20}]


@pytest.fixture
def clean_packages(monkeypatch):
    """Vervang het publieke pakket door een dubbelganger; `store` blijft onbereikbaar."""
    calls: list = []

    def fake_cbs(dataset_id, **params):
        calls.append(("cbs", dataset_id, params))
        return _ROWS

    def fake_fetch(resource, **params):
        calls.append(("rio", resource, params))
        return _ROWS

    def fake_duo(dataset_id, resource=0, **kwargs):
        calls.append(("duo", dataset_id, resource))
        return pd.DataFrame(_ROWS)

    duo_module = types.ModuleType("riodata.duo")
    duo_module.load = fake_duo
    riodata = types.ModuleType("riodata")
    riodata.fetch, riodata.duo = fake_fetch, duo_module
    onderwijsdata = types.ModuleType("onderwijsdata")
    onderwijsdata.data = fake_cbs
    monkeypatch.setitem(sys.modules, "riodata", riodata)
    monkeypatch.setitem(sys.modules, "riodata.duo", duo_module)
    monkeypatch.setitem(sys.modules, "onderwijsdata", onderwijsdata)
    monkeypatch.setattr(go.Figure, "show", lambda self, *a, **k: None)
    store.clear()
    yield calls
    store.clear()


def _run(snippet: str) -> dict:
    namespace: dict = {}
    exec(snippet, namespace)
    return namespace


_LOADS = {
    "duo": ("duo:p01hoinges:3", "get_duo_data", {"dataset_id": "p01hoinges", "resource": 3}, ("duo", "p01hoinges", 3)),
    "cbs": (
        "cbs:85423NED:ab12cd34",
        "get_cbs_data",
        {"dataset_id": "85423NED", "filters": {"$filter": "Perioden eq '2023JJ00'"}},
        ("cbs", "85423NED", {"$filter": "Perioden eq '2023JJ00'"}),
    ),
    "rio": (
        "rio:erkenningen:status=actief",
        "get_rio_data",
        {"resource": "erkenningen", "filters": {"status": "actief"}},
        ("rio", "erkenningen", {"status": "actief", "page": 0, "pageSize": 50}),
    ),
}


@pytest.mark.parametrize("bron", ["duo", "cbs", "rio"])
@pytest.mark.parametrize("tool", ["query_data", "create_plot", "run_analysis"])
def test_snippet_runs_without_the_store_and_loads_the_source(clean_packages, bron, tool):
    key, laadtool, laadargs, verwacht = _LOADS[bron]
    store.put(key, pd.DataFrame(_ROWS), store.KeyMeta(bron=bron, dataset="x", laad=(laadtool, laadargs)))
    args = {
        "query_data": {"data_key": key},
        "create_plot": {"data_key": key, "x": "JAAR", "y": "AANTAL", "title": "t"},
        "run_analysis": {"data_key": key, "code": "result = int(df['AANTAL'].sum())"},
    }[tool]

    snippet = generate(tool, args)
    namespace = _run(snippet)

    assert "store" not in snippet
    assert clean_packages == [verwacht]
    assert len(namespace["df"]) == 2


@pytest.mark.parametrize("bron", ["duo", "cbs", "rio"])
def test_load_snippet_runs_and_carries_source_id_and_filters(clean_packages, bron):
    _, laadtool, laadargs, verwacht = _LOADS[bron]

    snippet = generate(laadtool, laadargs)
    _run(snippet)

    assert clean_packages == [verwacht]
    assert all(str(v) in snippet for v in [laadargs.get("dataset_id") or laadargs["resource"]])


# --- #624: een afgeleide snippet herhaalt de stappen van zijn ouder ---


_BRONKEY = "duo:p01hoinges:3"
_SELECTIE = "duo:p01hoinges:3:sel"
_SELECTIE_RECEPT = {
    "afgeleid_van": _BRONKEY,
    "tool": "query_data",
    "args": {"filters": {"JAAR": "2022"}},
    "stap": 'filters {"JAAR": 2022}',
}


@pytest.fixture
def keten(clean_packages):
    """Bron plus een afgeleide selectie, met het recept zoals de sessie het onthoudt (#472)."""
    store.put(
        _BRONKEY,
        pd.DataFrame(_ROWS),
        store.KeyMeta(
            bron="duo", dataset="p01hoinges", laad=("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})
        ),
    )
    store.derive(_BRONKEY, _SELECTIE, pd.DataFrame([{"JAAR": 2022, "AANTAL": 20.0}]), stap=_SELECTIE_RECEPT["stap"])
    return {_SELECTIE: _SELECTIE_RECEPT}


def test_grafiek_snippet_laat_de_laadstap_en_de_stappen_van_de_ouder_zien(clean_packages, keten):
    snippet = generate(
        "create_plot",
        {"data_key": _SELECTIE, "x": "JAAR", "y": "AANTAL", "title": "t"},
        recept_van=keten.get,
    )

    assert snippet is not None
    assert 'duo.load("p01hoinges", 3)' in snippet  # de laadstap van de bron
    assert "pd.DataFrame([" not in snippet  # geen rijen uit de eerdere stap
    namespace = _run(snippet)
    assert clean_packages == [("duo", "p01hoinges", 3)]
    assert namespace["df"]["JAAR"].tolist() == [2022]  # de filter van de ouder is toegepast


def test_kpi_snippet_laat_de_laadstap_en_de_stappen_van_de_ouder_zien(clean_packages, keten):
    args = {"data_key": _SELECTIE, "value_column": "AANTAL", "metric": "sum", "label": "Totaal"}
    snippet = generate("compute_kpi", args, recept_van=keten.get)

    assert snippet is not None
    assert 'duo.load("p01hoinges", 3)' in snippet
    assert "pd.DataFrame([" not in snippet
    namespace = _run(snippet)
    assert clean_packages == [("duo", "p01hoinges", 3)]
    assert namespace["kpi"] == 20.0


def test_snippet_in_een_schone_namespace_volgt_de_dubbelganger_van_het_pakket(clean_packages, keten, monkeypatch):
    """Acceptatie #624: de dubbelganger bepaalt de uitkomst, niet de ingebakken rijen."""
    args = {"data_key": _SELECTIE, "value_column": "AANTAL", "metric": "sum", "label": "Totaal"}
    snippet = generate("compute_kpi", args, recept_van=keten.get)
    assert snippet is not None
    assert _run(snippet)["kpi"] == 20.0

    monkeypatch.setattr("riodata.duo.load", lambda *a, **k: pd.DataFrame([{"JAAR": 2022, "AANTAL": 7.0}]))
    assert _run(snippet)["kpi"] == 7.0  # dezelfde code, andere data uit het pakket


def test_selectie_op_een_selectie_herhaalt_beide_stappen(clean_packages, keten):
    tweede = f"{_SELECTIE}:kolommen"
    store.derive(_SELECTIE, tweede, pd.DataFrame([{"JAAR": 2022}]), stap="kolommen ['JAAR']")
    recepten = {
        **keten,
        tweede: {"afgeleid_van": _SELECTIE, "tool": "query_data", "args": {"columns": ["JAAR"]}, "stap": "kolommen"},
    }

    snippet = generate("query_data", {"data_key": tweede}, recept_van=recepten.get)

    assert snippet is not None
    assert 'duo.load("p01hoinges", 3)' in snippet
    assert "isin(['2022'])" in snippet  # de filter van de eerste stap
    assert "['JAAR']" in snippet  # de kolommen van de tweede stap
    assert "pd.DataFrame([" not in snippet


def test_vaste_maat_met_som_herhaalt_de_bron_en_de_som_van_de_leerwegen():
    """Voorbeeld 1 van #624: de mbo-som is zelf geen query_data-stap, maar het recept is dat wel."""
    args = {"maat": "mbo_studenten_instelling", "instelling": "ROC Mondriaan", "vorm": "bol"}
    recept = {"afgeleid_van": "duo:mbo-studenten-per-instelling:0", "tool": "get_maat", "args": args}

    snippet = generate(
        "compute_kpi",
        {
            "data_key": "duo:mbo-studenten-per-instelling:0:recept",
            "value_column": "AANTAL",
            "metric": "sum",
            "label": "L",
        },
        recept_van=lambda key: recept if key.startswith("duo:mbo-studenten-per-instelling") else None,
    )

    assert snippet is not None
    assert 'duo.load("mbo-studenten-per-instelling"' in snippet
    assert "BOLVT" in snippet and "BOLDT" in snippet  # de som van de leerwegkolommen
    assert "pd.DataFrame([" not in snippet


# --- #624, vervolg: een eigen berekening (run_analysis) herhaalt haar script, niet haar rijen ---


_ANALYSE = "analysis:0123456789ab"
_ANALYSE_CODE = "result = df[df['JAAR'] == 2022].assign(DUBBEL=lambda d: d['AANTAL'] * 2)"
_ANALYSE_STAP = "eigen berekening (run_analysis)"
_ANALYSE_RECEPT = {
    "afgeleid_van": _BRONKEY,
    "tool": "run_analysis",
    "args": {"code": _ANALYSE_CODE},
    "stap": _ANALYSE_STAP,
    "herlaadbaar": False,
}


@pytest.fixture
def berekening(clean_packages):
    """Bron plus een eigen berekening erop, met het script zoals recepten.van_session het uit de sessie meegeeft."""
    store.put(
        _BRONKEY,
        pd.DataFrame(_ROWS),
        store.KeyMeta(
            bron="duo", dataset="p01hoinges", laad=("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})
        ),
    )
    store.derive(_BRONKEY, _ANALYSE, pd.DataFrame([{"JAAR": 2022, "AANTAL": 20.0, "DUBBEL": 40.0}]), stap=_ANALYSE_STAP)
    return {_ANALYSE: _ANALYSE_RECEPT}


def test_kpi_op_een_eigen_berekening_herhaalt_de_laadstap_en_het_script(clean_packages, berekening):
    args = {"data_key": _ANALYSE, "value_column": "DUBBEL", "metric": "sum", "label": "Dubbel"}
    snippet = generate("compute_kpi", args, recept_van=berekening.get)

    assert snippet is not None
    assert 'duo.load("p01hoinges", 3)' in snippet
    assert _ANALYSE_CODE in snippet
    assert "pd.DataFrame([" not in snippet  # geen kopie van de uitkomst
    namespace = _run(snippet)
    assert clean_packages == [("duo", "p01hoinges", 3)]
    assert namespace["kpi"] == 40.0


def test_grafiek_op_een_eigen_berekening_volgt_de_dubbelganger_van_het_pakket(clean_packages, berekening, monkeypatch):
    """Acceptatie #624 voor een berekening: andere data uit het pakket, andere uitkomst."""
    args = {"data_key": _ANALYSE, "x": "JAAR", "y": "DUBBEL", "title": "t"}
    snippet = generate("create_plot", args, recept_van=berekening.get)

    assert snippet is not None
    assert "pd.DataFrame([" not in snippet
    assert _run(snippet)["df"]["DUBBEL"].tolist() == [40.0]
    monkeypatch.setattr("riodata.duo.load", lambda *a, **k: pd.DataFrame([{"JAAR": 2022, "AANTAL": 7.0}]))
    assert _run(snippet)["df"]["DUBBEL"].tolist() == [14.0]


def test_berekening_op_een_selectie_herhaalt_de_selectie_en_dan_het_script(clean_packages, keten):
    analyse = "analysis:op-selectie"
    code = "result = df.assign(DUBBEL=df['AANTAL'] * 2)"
    store.derive(_SELECTIE, analyse, pd.DataFrame([{"JAAR": 2022, "AANTAL": 20.0, "DUBBEL": 40.0}]), stap=_ANALYSE_STAP)
    recepten = {
        **keten,
        analyse: {"afgeleid_van": _SELECTIE, "tool": "run_analysis", "args": {"code": code}, "stap": _ANALYSE_STAP},
    }
    args = {"data_key": analyse, "value_column": "DUBBEL", "metric": "sum", "label": "L"}

    snippet = generate("compute_kpi", args, recept_van=recepten.get)

    assert snippet is not None
    assert 'duo.load("p01hoinges", 3)' in snippet
    assert snippet.index("isin(['2022'])") < snippet.index(code)  # eerst de selectie, dan het script
    assert "pd.DataFrame([" not in snippet
    assert _run(snippet)["kpi"] == 40.0


def test_berekening_op_een_berekening_herhaalt_eerst_het_script_van_de_ouder(clean_packages, berekening):
    code = "result = {'som': float(df['DUBBEL'].sum())}"

    snippet = generate("run_analysis", {"data_key": _ANALYSE, "code": code}, recept_van=berekening.get)

    assert snippet is not None
    assert snippet.index(_ANALYSE_CODE) < snippet.index(code)
    assert snippet.count("import plotly.express as px") == 1  # de imports staan één keer, bovenaan de keten
    assert "pd.DataFrame([" not in snippet
    assert _run(snippet)["result"] == {"som": 40.0}


def test_berekening_zonder_script_in_het_recept_blijft_een_eerlijke_kopie(clean_packages, berekening):
    """Na een herstart kent de sessie het script niet meer (#472): dan blijft de kopie, met de opmerking."""
    zonder_script = {_ANALYSE: {"afgeleid_van": _BRONKEY, "stap": _ANALYSE_STAP, "herlaadbaar": False}}
    args = {"data_key": _ANALYSE, "value_column": "DUBBEL", "metric": "sum", "label": "Dubbel"}

    snippet = generate("compute_kpi", args, recept_van=zonder_script.get)

    assert snippet is not None
    assert "groeien niet mee met de bron" in snippet
    assert _run(snippet)["kpi"] == 40.0
    assert clean_packages == []


def test_kpi_na_een_echte_berekening_herhaalt_het_script_via_de_sessie(clean_packages):
    """De keten van de app zelf: run_analysis in de sandbox, de sessie onthoudt de stap, de KPI-snippet herhaalt hem."""
    from agent import recepten
    from agent.session_data import record_data_key
    from tools.analysis import run_analysis

    store.put(
        _BRONKEY,
        pd.DataFrame(_ROWS),
        store.KeyMeta(
            bron="duo", dataset="p01hoinges", laad=("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})
        ),
    )
    recepten.wis()
    session = {"username": "alice"}
    args = {"code": _ANALYSE_CODE, "data_key": _BRONKEY}
    uitkomst = run_analysis(**args)
    assert isinstance(uitkomst, str), uitkomst
    record_data_key(session, uitkomst, {"name": "run_analysis", "arguments": args})
    analyse = json.loads(uitkomst)["data_key"]
    kpi = {"data_key": analyse, "value_column": "DUBBEL", "metric": "sum", "label": "Dubbel"}

    snippet = generate("compute_kpi", kpi, recept_van=recepten.van_session(session))
    recepten.wis()

    assert snippet is not None
    assert 'duo.load("p01hoinges", 3)' in snippet
    assert _ANALYSE_CODE in snippet
    assert "pd.DataFrame([" not in snippet
    assert _run(snippet)["kpi"] == 40.0


def test_onbekende_keten_bakt_de_waarden_in_met_een_eerlijke_opmerking(clean_packages):
    """Zonder recept (na een herstart, #472, of een eigen berekening) blijft inbakken de noodoplossing."""
    store.put(
        _BRONKEY,
        pd.DataFrame(_ROWS),
        store.KeyMeta(
            bron="duo", dataset="p01hoinges", laad=("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})
        ),
    )
    store.derive(_BRONKEY, "analysis:1", pd.DataFrame([{"JAAR": 2021, "AANTAL": float("nan")}]))

    snippet = generate("create_plot", {"data_key": "analysis:1", "x": "JAAR", "y": "AANTAL", "title": "t"})
    assert snippet is not None
    namespace = _run(snippet)

    assert clean_packages == []  # de bron wordt niet geladen: de rijen staan als kopie in de snippet
    assert "groeien niet mee met de bron" in snippet
    assert namespace["df"].to_dict("records") == [{"JAAR": 2021, "AANTAL": None}]


def test_grote_afgeleide_uitkomst_laad_de_bron_met_een_eerlijk_nb(clean_packages):
    """Te veel rijen om te kopiëren zonder keten: de bron, met een NB dat de uitkomst kan afwijken."""
    store.put(
        _BRONKEY,
        pd.DataFrame(_ROWS),
        store.KeyMeta(
            bron="duo", dataset="p01hoinges", laad=("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})
        ),
    )
    store.derive(_BRONKEY, "analysis:2", pd.DataFrame({"A": range(500)}))

    snippet = generate("query_data", {"data_key": "analysis:2"})

    assert snippet is not None
    assert 'duo.load("p01hoinges", 3)' in snippet
    assert "NB:" in snippet
    assert "kan afwijken van wat de app toonde" in snippet


def test_tool_end_snippet_volgt_de_keten_van_de_stap(clean_packages, monkeypatch):
    """Naad met de gespreksexport (#366): tool_end draagt de snippet die de export bewaart."""
    store.put(
        _BRONKEY,
        pd.DataFrame(_ROWS),
        store.KeyMeta(
            bron="duo", dataset="p01hoinges", laad=("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})
        ),
    )
    store.derive(_BRONKEY, _SELECTIE, pd.DataFrame([{"JAAR": 2022, "AANTAL": 20.0}]), stap=_SELECTIE_RECEPT["stap"])
    monkeypatch.setattr(loop_module, "dispatch", lambda name, args: (json.dumps({"data_key": _SELECTIE}), None))
    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    args = {"data_key": _SELECTIE, "x": "JAAR", "y": "AANTAL", "title": "t"}
    call = loop_module.ToolCall(id="t1", name="create_plot", arguments=json.dumps(args), args=args)
    asyncio.run(loop_module._execute_tool(call, emit, recept_van={_SELECTIE: _SELECTIE_RECEPT}.get))
    end = next(e for e in events if e["type"] == "tool_end")

    assert 'duo.load("p01hoinges", 3)' in end["snippet"]
    assert "pd.DataFrame([" not in end["snippet"]


def test_loaders_record_the_call_that_a_snippet_needs(zonder_scopegrens):
    store.clear()
    from tools.duo import get_duo_data
    from tools.rio import get_rio_data

    with (
        patch("tools.duo._duo.load", return_value=pd.DataFrame(_ROWS)),
        patch("tools.duo._duo.column_definitions", return_value={}),
    ):
        get_duo_data("p01hoinges", 3)
    with patch("tools.rio.fetch", return_value=_ROWS):
        get_rio_data("erkenningen", {"plaatsnaam": "Utrecht"})

    assert store.meta("duo:p01hoinges:3").laad == ("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})
    assert store.meta("rio:erkenningen:plaatsnaam=Utrecht").laad == (
        "get_rio_data",
        {"resource": "erkenningen", "filters": {"plaatsnaam": "Utrecht"}},
    )
    store.clear()


def test_duo_snippet_adds_the_studiejaar_label_the_app_adds(clean_packages):
    snippet = generate("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})
    namespace: dict = {}
    # De dubbelganger levert JAAR/AANTAL; zonder STUDIEJAAR blijft het label achterwege.
    exec(snippet, namespace)
    assert "STUDIEJAAR_LABEL" not in namespace["df"].columns

    import riodata.duo

    riodata.duo.load = lambda *a, **k: pd.DataFrame({"STUDIEJAAR": [2021, 2025]})
    namespace = {}
    exec(snippet, namespace)
    assert namespace["df"]["STUDIEJAAR_LABEL"].tolist() == ["2021/2022", "2025/2026"]


# --- #227: de snippet geeft hetzelfde resultaat als de tool, niet alleen een draaiend script ---

# Ruwe DUO-data zoals duo.load() hem geeft: JAAR als int, -1 voor onderdrukte cellen.
_RUW = pd.DataFrame(
    [
        {"JAAR": 2024, "INSTELLING": "VU Amsterdam", "EX": 9000},
        {"JAAR": 2024, "INSTELLING": "UvA", "EX": 911},
        {"JAAR": 2024, "INSTELLING": "Klein", "EX": -1},
        {"JAAR": 2025, "INSTELLING": "VU Amsterdam", "EX": 8000},
        {"JAAR": 2025, "INSTELLING": "UvA", "EX": 918},
        {"JAAR": 2025, "INSTELLING": "Klein", "EX": -1},
        {"JAAR": 2025, "INSTELLING": "Kleiner", "EX": -1},
    ]
)
_DUO_KEY = "duo:p02ho1ejrs:0"


@pytest.fixture
def duo_in_app_en_snippet(clean_packages):
    """Dezelfde ruwe data in de store (via put, dus gemaskeerd) en achter duo.load in de snippet."""
    import riodata.duo

    riodata.duo.load = lambda *a, **k: _RUW.copy()
    store.put(
        _DUO_KEY,
        _RUW.copy(),
        store.KeyMeta(
            bron="duo", dataset="p02ho1ejrs", laad=("get_duo_data", {"dataset_id": "p02ho1ejrs", "resource": 0})
        ),
    )


def _records(df: pd.DataFrame) -> list[dict]:
    """Vergelijkbare rijen: NA als None, getallen als float."""
    return [
        {k: (None if pd.isna(v) else float(v) if isinstance(v, (int, float)) else v) for k, v in rij.items()}
        for rij in df.to_dict("records")
    ]


@pytest.mark.parametrize(
    "args",
    [
        {"filters": {"JAAR": "2025"}},  # string-filter op een int-kolom
        {"filters": {"INSTELLING": "vu amsterdam"}},  # hoofdletterverschil
        {"filters": {"INSTELLING__in": ["uva", "VU AMSTERDAM"]}},
        {"filters": {"JAAR__eq": 2024}},
        {"filters": {"JAAR__gte": 2025}},
        {"filters": {"JAAR__lte": "2024"}},
        {"filters": {"JAAR__gte": 2024}, "group_by": ["JAAR"], "aggregate": {"EX": "sum"}},  # -1 telt niet mee
        {"group_by": ["JAAR"], "aggregate": {"EX": "count"}},
        {"group_by": ["INSTELLING"], "aggregate": {"EX": "sum"}},  # alleen -1: leeg, geen 0 (#394)
        {"group_by": ["JAAR"], "aggregate": {"INSTELLING": "count"}},  # tekstkolom: geen 0 (#411)
        {"group_by": ["JAAR"], "aggregate": {"INSTELLING": "nunique", "EX": "size"}},
    ],
)
def test_query_data_snippet_geeft_wat_de_app_geeft(duo_in_app_en_snippet, args):
    app = json.loads(query_data(_DUO_KEY, **args))
    namespace = _run(generate("query_data", {"data_key": _DUO_KEY, **args}))
    # De datakolommen: een groepsrij noemt haar onderdrukte cellen erbij (CH-07), dat is geen data.
    kolommen = list(store.get(app["data_key"]).columns)
    assert _records(namespace["df"]) == _records(pd.DataFrame(app["rijen"])[kolommen])


# Codes als tekst met voorloopnul (riodata 0.5.0, #542): het model schrijft 363, de kolom heeft '0363'.
_CODES = pd.DataFrame([{"GEMEENTENUMMER": "0363", "N": 1}, {"GEMEENTENUMMER": "0080", "N": 2}])
_CODE_KEY = "duo:adressen_ho:0"


@pytest.mark.parametrize(
    "args",
    [
        {"filters": {"GEMEENTENUMMER": 363}},  # zonder voorloopnul: gelezen als 0363
        {"filters": {"GEMEENTENUMMER": "0363"}},  # exact
        {"filters": {"GEMEENTENUMMER__in": ["363", "0080"]}},  # één exacte treffer wint: 363 niet erbij
        {"filters": {"GEMEENTENUMMER__in": [363, 80]}},
    ],
)
def test_code_zonder_voorloopnul_geeft_in_de_snippet_wat_de_app_geeft(clean_packages, monkeypatch, args):
    import riodata.duo

    monkeypatch.setattr(riodata.duo, "load", lambda *a, **k: _CODES.copy())
    store.put(
        _CODE_KEY,
        _CODES.copy(),
        store.KeyMeta(
            bron="duo", dataset="adressen_ho", laad=("get_duo_data", {"dataset_id": "adressen_ho", "resource": 0})
        ),
    )
    app = json.loads(query_data(_CODE_KEY, **args))
    snippet = generate("query_data", {"data_key": _CODE_KEY, **args})
    assert snippet is not None
    assert _records(_run(snippet)["df"]) == _records(pd.DataFrame(app["rijen"]))


def test_snippet_sluit_duo_minus_een_uit_net_als_de_app(duo_in_app_en_snippet):
    # Audit ronde 2, N1(b): app 8.918, snippet 8.915 — de -1-cellen telden mee.
    args = {"filters": {"JAAR": 2025}, "group_by": ["JAAR"], "aggregate": {"EX": "sum"}}
    namespace = _run(generate("query_data", {"data_key": _DUO_KEY, **args}))
    assert namespace["df"]["EX"].tolist() == [8918]


@pytest.mark.parametrize("metric", ["last", "first", "sum", "mean", "delta", "pct_change", "index"])
def test_kpi_snippet_laadt_zelf_en_rekent_hetzelfde(duo_in_app_en_snippet, metric):
    # Een KPI-snippet las een df uit een eerdere stap: niet zelfstandig (audit 10).
    args: dict[str, Any] = {"data_key": _DUO_KEY, "value_column": "EX", "metric": metric, "sort_column": "JAAR"}
    app = json.loads(compute_kpi(**args))
    namespace = _run(generate("compute_kpi", args) or "")
    assert namespace["kpi"] == pytest.approx(app["raw"])


@pytest.mark.parametrize("bereik", [{"van": 2024}, {"tot": 2024}, {"van": 2024, "tot": 2025}])
def test_kpi_snippet_past_van_en_tot_toe_zoals_de_app(duo_in_app_en_snippet, bereik):
    args: dict[str, Any] = {
        "data_key": _DUO_KEY,
        "value_column": "EX",
        "metric": "delta",
        "sort_column": "JAAR",
        "label": "L",
        **bereik,
    }
    app = json.loads(compute_kpi(**args))
    namespace = _run(generate("compute_kpi", args) or "")
    assert namespace["kpi"] == pytest.approx(app["raw"])


def test_query_data_snippet_rondt_prognoses_af_zoals_de_app():
    """De snippet toont hetzelfde getal als de tool: hele personen bij een prognose (#247)."""
    store.put(
        "duo:voprognoses:0",
        pd.DataFrame([{"AANTAL": 1.5}]),
        store.KeyMeta(
            bron="duo", dataset="voprognoses", laad=("get_duo_data", {"dataset_id": "voprognoses", "resource": 0})
        ),
    )
    assert "print(df.round())" in generate("query_data", {"data_key": "duo:voprognoses:0"})


# ── Databewerking uit de tool-response (#4) ──────────────────────────────────


def test_databewerking_uit_de_response_staat_als_commentaar_bovenaan():
    noot = "38 cellen met DUO-sentinel -1 in 'AANTAL' uitgesloten — totalen zijn hierdoor een ondergrens"
    result = json.dumps({"data_key": "duo:abc:resource:ab12", "totaal_rijen": 3, "databewerking": [noot]})
    snippet = generate("query_data", {"data_key": "duo:abc:resource"}, result)
    assert snippet is not None
    regels = snippet.splitlines()
    assert regels[:2] == ["# Databewerking in de app:", f"# {noot}"]
    assert 'duo.load("abc"' in snippet


def test_cbs_afronding_en_afgekapte_pagina_staan_in_de_snippet():
    result = json.dumps(
        {"data_key": "cbs:83753NED", "opgehaalde_rijen": 9999, "volledig": False, "afronding": "Afgerond op 10-tallen."}
    )
    snippet = generate("get_cbs_data", {"dataset_id": "83753NED"}, result)
    assert snippet is not None
    assert "# Afgerond op 10-tallen." in snippet
    assert "# Afgekapt: 9999 rijen opgehaald, niet de hele bron." in snippet


def test_rio_pagina_met_meer_beschikbaar_is_afgekapt():
    result = json.dumps({"data_key": "rio:x", "opgehaalde_rijen": 100, "meer_beschikbaar": True})
    snippet = generate("get_rio_data", {"resource": "x"}, result)
    assert snippet is not None
    assert "# Afgekapt: 100 rijen opgehaald" in snippet


@pytest.mark.parametrize(
    "result",
    [None, "", "Fout: dataset bestaat niet", json.dumps([1, 2]), json.dumps({"data_key": "duo:abc:resource"})],
)
def test_zonder_bewerking_blijft_de_snippet_gelijk(result):
    args = {"data_key": "duo:abc:resource"}
    assert generate("query_data", args, result) == generate("query_data", args)


def test_tool_end_snippet_draagt_de_databewerking(monkeypatch):
    """Naad: de loop geeft de response door aan de snippet."""
    noot = "2 cellen met DUO-sentinel -1 in 'AANTAL' uitgesloten"
    result = json.dumps({"data_key": "duo:abc:resource:ab12", "totaal_rijen": 1, "databewerking": [noot]})
    monkeypatch.setattr(loop_module, "dispatch", lambda name, args: (result, None))
    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    args = {"data_key": "duo:abc:resource"}
    call = loop_module.ToolCall(id="t1", name="query_data", arguments=json.dumps(args), args=args)
    asyncio.run(loop_module._execute_tool(call, emit))
    end = next(e for e in events if e["type"] == "tool_end")
    assert f"# {noot}" in end["snippet"]


def test_create_plot_snippet_tekent_lange_namen_liggend_zoals_de_app():
    namen = ["Universiteit van Amsterdam", "Vrije Universiteit Amsterdam", "Universiteit Utrecht"]
    snippet = generate(
        "create_plot",
        {
            "data": [{"INSTELLING": n, "AANTAL": i} for i, n in enumerate(namen)],
            "chart_type": "bar",
            "x": "INSTELLING",
            "y": "AANTAL",
            "title": "t",
            "color_by": "INSTELLING",
        },
    )
    assert snippet is not None
    assert 'fig = px.bar(df, x="AANTAL", y="INSTELLING", orientation="h", title="t")' in snippet
    assert 'autorange="reversed"' in snippet


def test_get_cbs_data_snippet_toont_het_compilaat_van_een_gesloten_selectie():
    """Het model stuurt een selectie, de server bouwt de filter (#343): de snippet laadt met die filter (#531)."""
    snippet = generate(
        "get_cbs_data",
        {"dataset_id": "85353NED", "selectie": {"dimensies": {"Geslacht": "4000"}, "periode": ["2021/22"]}},
    )
    assert snippet is not None
    assert 'data("85353NED"' in snippet
    assert "trim(Geslacht) eq '4000'" in snippet and "trim(Perioden) eq '2021SJ00'" in snippet
    assert "selectie" not in snippet


def test_create_plot_snippet_zet_de_y_as_op_nul_zoals_de_app():
    """#741: de snippet tekent de grafiek die de gebruiker zag, ook met de as vanaf 0."""
    args = {"data_key": "duo:x:y:result", "chart_type": "line", "x": "STUDIEJAAR", "y": "AANTAL", "title": "t"}
    vrij, vanaf_nul = generate("create_plot", args), generate("create_plot", {**args, "y_vanaf_nul": True})
    assert vrij is not None and vanaf_nul is not None
    assert "rangemode" not in vrij
    assert 'fig.update_yaxes(rangemode="tozero")' in vanaf_nul
