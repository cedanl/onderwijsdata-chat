import sys
import types
from unittest.mock import patch

import pandas as pd
import plotly.graph_objects as go
import pytest

from tools import store
from tools.snippet import generate


def test_query_data_with_filters_and_aggregation():
    snippet = generate("query_data", {
        "data_key": "duo:p02ho1ejrs:Eerstejaarsingeschrevenen wo",
        "filters": {"INSTELLINGSNAAM_ACTUEEL": "VU Amsterdam", "TYPE_HOGER_ONDERWIJS": "bachelor"},
        "group_by": ["STUDIEJAAR"],
        "aggregate": {"AANTAL": "sum"},
    })
    assert snippet is not None
    assert 'duo.load("p02ho1ejrs"' in snippet
    assert 'df[df["INSTELLINGSNAAM_ACTUEEL"] == \'VU Amsterdam\']' in snippet
    assert "groupby" in snippet
    assert "print(df)" in snippet


def test_query_data_minimal():
    snippet = generate("query_data", {"data_key": "duo:abc:resource"})
    assert snippet is not None
    assert 'duo.load("abc"' in snippet
    assert "groupby" not in snippet


def test_query_data_with_columns():
    snippet = generate("query_data", {
        "data_key": "duo:x:y",
        "columns": ["A", "B"],
    })
    assert snippet is not None
    assert "['A', 'B']" in snippet


def test_query_data_cbs_key_without_known_load_says_so_instead_of_naming_the_store():
    snippet = generate("query_data", {"data_key": "cbs:83753NED:abc123"})
    assert snippet is not None
    assert "store" not in snippet
    assert "Geen laadstap bekend" in snippet


def test_query_data_filter_operators():
    snippet = generate("query_data", {
        "data_key": "duo:x:y",
        "filters": {"JAAR__gte": 2020, "REGIO__in": ["Noord", "Zuid"]},
    })
    assert snippet is not None
    assert ">=" in snippet
    assert "isin" in snippet


def test_query_data_filter_plain_key_list():
    snippet = generate("query_data", {
        "data_key": "duo:x:y",
        "filters": {"SECTOR": ["Techniek", "Zorg"]},
    })
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
    snippet = generate("get_cbs_data", {
        "dataset_id": "83753NED",
        "filters": {"$filter": "Perioden eq '2023JJ00'"},
    })
    assert snippet is not None
    assert 'data("83753NED"' in snippet
    assert "Perioden" in snippet


def test_create_plot_with_data_key():
    snippet = generate("create_plot", {
        "data_key": "duo:p02ho1ejrs:resource:result",
        "chart_type": "line",
        "x": "STUDIEJAAR",
        "y": "AANTAL",
        "title": "Test grafiek",
    })
    assert snippet is not None
    assert "px.line" in snippet
    assert "store" not in snippet
    assert "STUDIEJAAR" in snippet
    # Geen gehardcode data-waarden
    assert "[{" not in snippet


def test_create_plot_with_inline_data_fallback():
    snippet = generate("create_plot", {
        "data": [{"JAAR": 2021, "AANTAL": 100}],
        "chart_type": "bar",
        "x": "JAAR",
        "y": "AANTAL",
        "title": "Test",
    })
    assert snippet is not None
    assert "px.bar" in snippet
    assert "2021" in snippet


def test_create_plot_with_color_by():
    snippet = generate("create_plot", {
        "data_key": "duo:x:y:result",
        "chart_type": "bar",
        "x": "X", "y": "Y", "title": "t",
        "color_by": "G",
    })
    assert snippet is not None
    assert 'color="G"' in snippet


def test_create_choropleth_with_data_key():
    snippet = generate("create_choropleth_map", {
        "data_key": "cbs:83753NED:result",
        "location_col": "RegioS",
        "value_col": "Waarde",
        "title": "Kaart",
    })
    assert snippet is not None
    assert "store" not in snippet
    assert "choropleth_map" in snippet
    assert "RegioS" in snippet


def test_create_choropleth_with_inline_data():
    snippet = generate("create_choropleth_map", {
        "data": [{"RegioS": "PV20", "Waarde": 100}],
        "location_col": "RegioS",
        "value_col": "Waarde",
        "title": "Kaart",
    })
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
    "cbs": ("cbs:85423NED:ab12cd34", "get_cbs_data",
            {"dataset_id": "85423NED", "filters": {"$filter": "Perioden eq '2023JJ00'"}},
            ("cbs", "85423NED", {"$filter": "Perioden eq '2023JJ00'"})),
    "rio": ("rio:erkenningen:status=actief", "get_rio_data",
            {"resource": "erkenningen", "filters": {"status": "actief"}},
            ("rio", "erkenningen", {"status": "actief", "page": 0, "pageSize": 50})),
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
    store.put("duo:p01hoinges:3", pd.DataFrame(_ROWS), store.KeyMeta(
        bron="duo", dataset="p01hoinges", laad=("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})))
    store.derive("duo:p01hoinges:3", "analysis:1", pd.DataFrame([{"JAAR": 2021, "AANTAL": float("nan")}]))

    snippet = generate("create_plot", {"data_key": "analysis:1", "x": "JAAR", "y": "AANTAL", "title": "t"})
    namespace = _run(snippet)

    assert clean_packages == []  # de bron wordt niet opnieuw geladen: de rijen staan in de snippet
    assert namespace["df"].to_dict("records") == [{"JAAR": 2021, "AANTAL": None}]


def test_big_derived_result_loads_the_source_with_a_note(clean_packages):
    store.put("duo:p01hoinges:3", pd.DataFrame(_ROWS), store.KeyMeta(
        bron="duo", dataset="p01hoinges", laad=("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})))
    store.derive("duo:p01hoinges:3", "analysis:2", pd.DataFrame({"A": range(500)}))

    snippet = generate("query_data", {"data_key": "analysis:2"})

    assert 'duo.load("p01hoinges", 3)' in snippet
    assert "NB:" in snippet


def test_loaders_record_the_call_that_a_snippet_needs():
    store.clear()
    from tools.duo import get_duo_data
    from tools.rio import get_rio_data

    with patch("tools.duo._duo.load", return_value=pd.DataFrame(_ROWS)), \
         patch("tools.duo._duo.column_definitions", return_value={}):
        get_duo_data("p01hoinges", 3)
    with patch("tools.rio.fetch", return_value=_ROWS), patch("tools.rio.rio_filters", return_value=[]):
        get_rio_data("erkenningen", {"status": "actief"})

    assert store.meta("duo:p01hoinges:3").laad == ("get_duo_data", {"dataset_id": "p01hoinges", "resource": 3})
    assert store.meta("rio:erkenningen:status=actief").laad == (
        "get_rio_data", {"resource": "erkenningen", "filters": {"status": "actief"}})
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

