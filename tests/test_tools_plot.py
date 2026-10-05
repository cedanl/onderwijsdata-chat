import json

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import pytest

from tools import store
from tools.plot import create_plot

_ROWS = [
    {"jaar": "2020", "waarde": 100},
    {"jaar": "2021", "waarde": 120},
    {"jaar": "2022", "waarde": 110},
]

_ROWS_GROUPED = [
    {"jaar": "2020", "waarde": 100, "groep": "A"},
    {"jaar": "2020", "waarde": 80, "groep": "B"},
    {"jaar": "2021", "waarde": 120, "groep": "A"},
    {"jaar": "2021", "waarde": 90, "groep": "B"},
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
    assert fig is not None
    assert len(fig.data) > 0


def test_pie_chart():
    _, fig = create_plot(_ROWS, "pie", "jaar", "waarde", "T")
    assert fig is not None
    assert len(fig.data) > 0


def test_color_by_creates_one_trace_per_group():
    _, fig = create_plot(_ROWS_GROUPED, "bar", "jaar", "waarde", "T", color_by="groep")
    assert fig is not None
    assert len(fig.data) == 2


def test_color_by_line_chart():
    _, fig = create_plot(_ROWS_GROUPED, "line", "jaar", "waarde", "T", color_by="groep")
    assert fig is not None
    assert len(fig.data) == 2


def test_missing_y_column_gives_explanatory_message_not_empty_figure():
    # Live-audit 9: een verkeerd gespelde meetkolom gaf y=[None, None] en "2 datapunten
    # aangemaakt" i.p.v. een melding (#216).
    msg, fig = create_plot(_ROWS, "bar", "jaar", "niet_bestaand", "T")
    assert fig is None
    assert "niet_bestaand" in msg
    assert "waarde" in msg  # noemt de wel-bestaande kolommen


def test_missing_x_column_gives_explanatory_message():
    msg, fig = create_plot(_ROWS, "bar", "niet_bestaand", "waarde", "T")
    assert fig is None
    assert "niet_bestaand" in msg


def test_text_column_as_y_is_refused():
    rows = [{"jaar": "2020", "waarde": "veel"}, {"jaar": "2021", "waarde": "meer"}]
    msg, fig = create_plot(rows, "bar", "jaar", "waarde", "T")
    assert fig is None
    assert "tekst" in msg.lower()


def test_all_missing_y_values_gives_explanation_not_null_points():
    # DUO-sentinelmaskering levert pd.NA/None op; dat is geen lege grafiek waard,
    # maar een uitleg (#216).
    rows = [{"jaar": "2020", "waarde": None}, {"jaar": "2021", "waarde": None}]
    msg, fig = create_plot(rows, "bar", "jaar", "waarde", "T")
    assert fig is None
    assert "waarde" in msg


def test_result_message_names_the_actual_chart_type():
    # #117: de tekst moet kloppen met wat de figuur werkelijk is.
    line_msg, _ = create_plot(_ROWS, "line", "jaar", "waarde", "T")
    bar_msg, _ = create_plot(_ROWS, "bar", "jaar", "waarde", "T")
    assert "lijngrafiek" in line_msg.lower()
    assert "staafgrafiek" in bar_msg.lower()


def test_dutch_number_separators_on_the_layout():
    # #22: Nederlandse getalnotatie (30.083 i.p.v. 30,083) in labels en assen.
    _, fig = create_plot(_ROWS, "bar", "jaar", "waarde", "T")
    assert fig.layout.separators == ",."


def test_highlight_gives_one_group_the_accent_color_and_the_rest_grey():
    _, fig = create_plot(_ROWS_GROUPED, "bar", "jaar", "waarde", "T", color_by="groep", highlight="A")
    colors = {trace.name: trace.marker.color for trace in fig.data}
    assert colors["A"] != colors["B"]
    assert colors["B"] == "#B0B0B0"


def test_value_labels_shown_for_a_small_number_of_points():
    _, fig = create_plot(_ROWS, "bar", "jaar", "waarde", "T")
    assert fig.data[0].text is not None
    assert list(fig.data[0].text) == ["100", "120", "110"]


def test_value_labels_omitted_for_many_points_to_avoid_overlap():
    rows = [{"jaar": str(2000 + i), "waarde": i} for i in range(30)]
    _, fig = create_plot(rows, "bar", "jaar", "waarde", "T")
    assert fig.data[0].text is None


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

_FAKE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "PV20",
            "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [[[5, 52], [6, 52], [6, 53], [5, 52]]]},
        },
        {
            "type": "Feature",
            "id": "PV21",
            "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [[[5, 51], [6, 51], [6, 52], [5, 51]]]},
        },
    ],
}


def test_choropleth_data_key_reads_from_store():
    df = pd.DataFrame(_CHOROPLETH_ROWS)
    store.put("test:choro:result", df)
    with patch("tools.plot._load_geojson", return_value=_FAKE_GEOJSON):
        msg, fig = create_choropleth_map(
            data_key="test:choro:result", location_col="RegioS", value_col="Waarde", title="Kaart test"
        )
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


def test_create_plot_schema_biedt_geen_losse_datarijen_aan():
    """Het model mag alleen een data_key opgeven; datarijen typen is geen optie."""
    from tools.schemas import TOOL_CREATE_CHOROPLETH_MAP, TOOL_CREATE_PLOT, TOOL_SCHEMAS

    for naam in (TOOL_CREATE_PLOT, TOOL_CREATE_CHOROPLETH_MAP):
        schema = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == naam)
        params = schema["function"]["parameters"]
        assert "data" not in params["properties"], f"{naam} biedt nog een data-parameter aan"
        assert "data_key" in params["required"], f"{naam} vereist geen data_key"


def test_single_datapoint_gives_no_figure_when_the_type_is_left_to_auto():
    msg, fig = create_plot([{"instelling": "HU", "aantal": 27441}], "auto", "instelling", "aantal", "Studenten")
    assert fig is None
    assert "27441" in msg


def test_explicit_bar_of_one_datapoint_is_plotted():
    # Live-audit 8 (#199): de gebruiker vroeg om een staafgrafiek van één jaar en kreeg niets.
    _, fig = create_plot([{"jaar": "2024/25", "aantal": 378490}], "bar", "jaar", "aantal", "Ingeschrevenen hbo")
    assert isinstance(fig, go.Figure)
    assert list(fig.data[0].y) == [378490]


def test_explicit_pie_of_one_datapoint_is_still_refused():
    # Eén taartpunt is altijd 100%: dat zegt niets.
    _, fig = create_plot([{"soort": "hbo", "aantal": 378490}], "pie", "soort", "aantal", "T")
    assert fig is None


def test_single_datapoint_via_data_key_gives_no_figure():
    store.put("test:een", pd.DataFrame([{"jaar": "2023", "waarde": 5}]))
    _, fig = create_plot(data_key="test:een", x="jaar", y="waarde", title="T")
    assert fig is None


def test_two_datapoints_still_plot():
    _, fig = create_plot(_ROWS[:2], "bar", "jaar", "waarde", "T")
    assert isinstance(fig, go.Figure)


def test_figure_carries_the_store_rows_for_the_csv_export():
    """De grafiek-CSV exporteert layout.meta.data (#183): elke rij uit de store,
    ook bij een herhaald x-label, met een ontbrekende waarde als null."""
    df = pd.DataFrame(
        {
            "SUBONDERDEEL": ["economie", "economie", "recht"],
            "AANTAL": [137.0, 2351.0, float("nan")],
        }
    )
    store.put("test:csv-export", df)

    _, fig = create_plot(data_key="test:csv-export", chart_type="bar", x="SUBONDERDEEL", y="AANTAL", title="t")

    meta = json.loads(pio.to_json(fig))["layout"]["meta"]
    assert meta["data"] == [
        {"SUBONDERDEEL": "economie", "AANTAL": 137.0},
        {"SUBONDERDEEL": "economie", "AANTAL": 2351.0},
        {"SUBONDERDEEL": "recht", "AANTAL": None},
    ]


# ── Tijdas (#240) ──

_HAN = [
    {"STUDIEJAAR": 2023, "aantal": 27367},
    {"STUDIEJAAR": 2024, "aantal": 26900},
    {"STUDIEJAAR": 2025, "aantal": 26445},
]


@pytest.mark.parametrize("kolom", ["STUDIEJAAR", "JAAR", "Perioden", "Perioden_label", "STUDIEJAAR_LABEL"])
def test_tijdreeks_zonder_typeverzoek_wordt_een_lijn(kolom):
    rows = [{kolom: r["STUDIEJAAR"], "aantal": r["aantal"]} for r in _HAN]
    msg, fig = create_plot(rows, "auto", kolom, "aantal", "T")
    assert fig.data[0].type == "scatter" and fig.data[0].mode.startswith("lines")
    assert "lijngrafiek" in msg.lower()


@pytest.mark.parametrize("chart_type", ["line", "bar"])
def test_jaartallen_op_de_as_zonder_tussenwaarden_of_duizendtalpunt(chart_type):
    # Audit 10: de HAN-grafiek toonde 2.023,5 / 2.024 / 2.024,5 op de x-as.
    _, fig = create_plot(_HAN, chart_type, "STUDIEJAAR", "aantal", "T")
    assert fig.layout.xaxis.type == "category"
    assert fig.layout.xaxis.categoryorder == "category ascending"


def test_geen_tijdas_houdt_een_gewone_as():
    _, fig = create_plot([{"regio": "A", "n": 1}, {"regio": "B", "n": 2}], "bar", "regio", "n", "T")
    assert fig.layout.xaxis.type is None


def test_prognosegrafiek_en_csv_tonen_hele_personen():
    """Audit 12: de prognose-CSV gaf 937657.4 terwijl de tekst hele personen toonde (#328, #247)."""
    store.put(
        "duo:voprognoses:0",
        pd.DataFrame([{"JAAR": 2030, "AANTAL": 937657.4}, {"JAAR": 2031, "AANTAL": 930001.6}]),
        store.KeyMeta(bron="duo", dataset="voprognoses"),
    )
    _, fig = create_plot(data_key="duo:voprognoses:0", chart_type="line", x="JAAR", y="AANTAL")
    assert fig is not None
    assert fig.layout.meta["data"] == [{"JAAR": 2030, "AANTAL": 937657}, {"JAAR": 2031, "AANTAL": 930002}]


def test_grafiek_buiten_prognoses_houdt_decimalen():
    store.put(
        "duo:x:0",
        pd.DataFrame([{"JAAR": 2030, "PCT": 12.5}, {"JAAR": 2031, "PCT": 13.25}]),
        store.KeyMeta(bron="duo", dataset="x"),
    )
    _, fig = create_plot(data_key="duo:x:0", chart_type="line", x="JAAR", y="PCT")
    assert fig is not None
    assert [r["PCT"] for r in fig.layout.meta["data"]] == [12.5, 13.25]
