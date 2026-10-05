import json
import sys
import types
from typing import Any
from unittest.mock import patch

import pandas as pd
import plotly.graph_objects as go
import pytest

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


def test_derived_result_becomes_rows_in_the_snippet(clean_packages):
    store.put(
        "duo:p01hoinges:3",
        pd.DataFrame(_ROWS),
        store.KeyMeta(
            bron="duo", dataset="p01hoinges", laad=("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})
        ),
    )
    store.derive("duo:p01hoinges:3", "analysis:1", pd.DataFrame([{"JAAR": 2021, "AANTAL": float("nan")}]))

    snippet = generate("create_plot", {"data_key": "analysis:1", "x": "JAAR", "y": "AANTAL", "title": "t"})
    namespace = _run(snippet)

    assert clean_packages == []  # de bron wordt niet opnieuw geladen: de rijen staan in de snippet
    assert namespace["df"].to_dict("records") == [{"JAAR": 2021, "AANTAL": None}]


def test_big_derived_result_loads_the_source_with_a_note(clean_packages):
    store.put(
        "duo:p01hoinges:3",
        pd.DataFrame(_ROWS),
        store.KeyMeta(
            bron="duo", dataset="p01hoinges", laad=("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})
        ),
    )
    store.derive("duo:p01hoinges:3", "analysis:2", pd.DataFrame({"A": range(500)}))

    snippet = generate("query_data", {"data_key": "analysis:2"})

    assert 'duo.load("p01hoinges", 3)' in snippet
    assert "NB:" in snippet


def test_loaders_record_the_call_that_a_snippet_needs():
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
    ],
)
def test_query_data_snippet_geeft_wat_de_app_geeft(duo_in_app_en_snippet, args):
    app = json.loads(query_data(_DUO_KEY, **args))
    namespace = _run(generate("query_data", {"data_key": _DUO_KEY, **args}))
    assert _records(namespace["df"]) == _records(pd.DataFrame(app["rijen"]))


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
