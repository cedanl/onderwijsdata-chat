import pandas as pd
import pytest
import plotly.graph_objects as go

from tools import store
from tools.plot import create_plot

_ROWS = [
    {"jaar": "2020", "waarde": 100},
    {"jaar": "2021", "waarde": 120},
    {"jaar": "2022", "waarde": 110},
]

_ROWS_GROUPED = [
    {"jaar": "2020", "waarde": 100, "groep": "A"},
    {"jaar": "2020", "waarde": 80,  "groep": "B"},
    {"jaar": "2021", "waarde": 120, "groep": "A"},
    {"jaar": "2021", "waarde": 90,  "groep": "B"},
]


def test_returns_tuple_of_str_and_figure():
    msg, fig = create_plot(_ROWS, "bar", "jaar", "waarde", "Test")
    assert isinstance(msg, str)
    assert isinstance(fig, go.Figure)


def test_result_message_contains_title():
    msg, _ = create_plot(_ROWS, "line", "jaar", "waarde", "Mijn Grafiek")
    assert "Mijn Grafiek" in msg


def test_result_message_contains_datapoint_count():
    msg, _ = create_plot(_ROWS, "bar", "jaar", "waarde", "T")
    assert str(len(_ROWS)) in msg


@pytest.mark.parametrize("chart_type", ["bar", "line", "scatter", "histogram"])
def test_chart_types_produce_figure(chart_type):
    _, fig = create_plot(_ROWS, chart_type, "jaar", "waarde", "T")
    assert len(fig.data) > 0


def test_pie_chart():
    _, fig = create_plot(_ROWS, "pie", "jaar", "waarde", "T")
    assert len(fig.data) > 0


def test_color_by_creates_one_trace_per_group():
    _, fig = create_plot(_ROWS_GROUPED, "bar", "jaar", "waarde", "T", color_by="groep")
    assert len(fig.data) == 2


def test_color_by_line_chart():
    _, fig = create_plot(_ROWS_GROUPED, "line", "jaar", "waarde", "T", color_by="groep")
    assert len(fig.data) == 2


def test_data_key_reads_from_store():
    df = pd.DataFrame(_ROWS)
    store.put("test:plot:result", df)
    msg, fig = create_plot(data_key="test:plot:result", chart_type="bar", x="jaar", y="waarde", title="Store test")
    assert isinstance(fig, go.Figure)
    assert "3" in msg


def test_data_key_missing_returns_error():
    msg, fig = create_plot(data_key="nonexistent:key", chart_type="bar", x="x", y="y", title="T")
    assert "Geen data" in msg
    assert fig is None


def test_no_data_no_key_returns_error():
    msg, fig = create_plot(chart_type="bar", x="x", y="y", title="T")
    assert "Geen data" in msg
    assert fig is None


# --- create_choropleth_map ---

from unittest.mock import patch
from tools.plot import create_choropleth_map

_CHOROPLETH_ROWS = [
    {"RegioS": "PV20", "Waarde": 100},
    {"RegioS": "PV21", "Waarde": 200},
]

_FAKE_GEOJSON = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "id": "PV20", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[[5, 52], [6, 52], [6, 53], [5, 52]]]}},
    {"type": "Feature", "id": "PV21", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[[5, 51], [6, 51], [6, 52], [5, 51]]]}},
]}


def test_choropleth_data_key_reads_from_store():
    df = pd.DataFrame(_CHOROPLETH_ROWS)
    store.put("test:choro:result", df)
    with patch("tools.plot._load_geojson", return_value=_FAKE_GEOJSON):
        msg, fig = create_choropleth_map(data_key="test:choro:result", location_col="RegioS", value_col="Waarde", title="Kaart test")
    assert isinstance(fig, go.Figure)
    assert "2" in msg


def test_choropleth_data_key_missing_returns_error():
    msg, fig = create_choropleth_map(data_key="nonexistent:key", location_col="R", value_col="V", title="T")
    assert "Geen data" in msg
    assert fig is None


def test_choropleth_no_data_no_key_returns_error():
    msg, fig = create_choropleth_map(location_col="R", value_col="V", title="T")
    assert "Geen data" in msg
    assert fig is None
