import pytest
import plotly.graph_objects as go

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
