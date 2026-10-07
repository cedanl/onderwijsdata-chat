"""Grafieken tonen geen ruwe kolomnamen en codes (#418, CH-11).

Ondanks de leesbare titels uit #405 stonden er nog Perioden_label en MboStudenten_1
als astitel (CBS), OPLEIDINGSVORM met DT/DU/VT op de x-as en MAN/ONBEKEND/VROUW in
de legenda (DUO). De titels komen uit de bron: CBS geeft per kolom een titel in
DataProperties, DUO's opleidingsvormcodes staan in de datasetbeschrijving.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from tools import store
from tools.analysis import run_analysis
from tools.cbs import clear_dimensions, get_cbs_data
from tools.plot import create_plot
from tools.query import query_data
from tools.store import KeyMeta

_DEFS = {
    "Onderwijssoort": {"type": "Dimension", "title": "Onderwijssoort"},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "MboStudenten_1": {"type": "Topic", "title": "Mbo-studenten"},
}
_ROWS = [
    {"Onderwijssoort": "A1", "Perioden": "2023SJ00", "MboStudenten_1": 37221},
    {"Onderwijssoort": "A1", "Perioden": "2024SJ00", "MboStudenten_1": 3303},
]
_DIMENSIES = {
    "Onderwijssoort": [{"Key": "A1", "Title": "Mbo"}],
    "Perioden": [{"Key": "2023SJ00", "Title": "2023/'24"}, {"Key": "2024SJ00", "Title": "2024/'25"}],
}


@pytest.fixture
def cbs_key():
    def fake_get(dataset_id, endpoint, **params):
        return _DIMENSIES.get(endpoint, [])

    with (
        patch("tools.cbs.data", return_value=_ROWS),
        patch("tools.cbs.definitions", return_value=_DEFS),
        patch("tools.cbs.get", side_effect=fake_get),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        yield json.loads(get_cbs_data("99999NED"))["data_key"]
    clear_dimensions()


def test_cbs_astitels_komen_uit_de_kolomtitels_van_de_bron(cbs_key):
    _, fig = create_plot(data_key=cbs_key, chart_type="line", x="Perioden_label", y="MboStudenten_1", title="T")
    assert fig.layout.xaxis.title.text == "Studiejaar"
    assert fig.layout.yaxis.title.text == "Mbo-studenten"
    # De export houdt de bronnamen (#217).
    assert fig.layout.meta["x"] == "Perioden_label"


def test_ook_na_een_bewerking_met_query_data(cbs_key):
    afgeleid = json.loads(query_data(cbs_key, columns=["Perioden_label", "MboStudenten_1"]))["data_key"]
    _, fig = create_plot(data_key=afgeleid, chart_type="bar", x="Perioden_label", y="MboStudenten_1", title="T")
    assert fig.layout.xaxis.title.text == "Studiejaar"
    assert fig.layout.yaxis.title.text == "Mbo-studenten"


def test_een_periode_zonder_schooljaren_heet_periode():
    from tools.cbs import kolomtitels

    assert kolomtitels(_DEFS, schooljaren=None)["Perioden"] == "Periode"
    assert kolomtitels(_DEFS, schooljaren=(2023,))["Perioden"] == "Studiejaar"


_DUO_KEY = "duo:p01hoinges:0"


@pytest.fixture
def duo_key():
    store.put(
        _DUO_KEY,
        pd.DataFrame(
            {
                "OPLEIDINGSVORM": ["VT", "DT", "DU", "VT", "DT", "DU"],
                "GESLACHT": ["MAN", "VROUW", "ONBEKEND", "VROUW", "MAN", "VROUW"],
                "AANTAL_INGESCHREVENEN": [10, 20, 30, 40, 50, 60],
            }
        ),
        KeyMeta(bron="duo", dataset="p01hoinges"),
    )
    yield _DUO_KEY


def test_opleidingsvormcodes_worden_woorden(duo_key):
    _, fig = create_plot(data_key=duo_key, chart_type="bar", x="OPLEIDINGSVORM", y="AANTAL_INGESCHREVENEN", title="T")
    assert fig.layout.xaxis.title.text == "Opleidingsvorm"
    assert set(fig.data[0].x) == {"Voltijd", "Deeltijd", "Duaal"}
    # De export houdt de codes uit de bron.
    assert {rij["OPLEIDINGSVORM"] for rij in fig.layout.meta["data"]} == {"VT", "DT", "DU"}


def test_geslacht_in_de_legenda_in_gewone_schrijfwijze(duo_key):
    _, fig = create_plot(
        data_key=duo_key,
        chart_type="bar",
        x="OPLEIDINGSVORM",
        y="AANTAL_INGESCHREVENEN",
        title="T",
        color_by="GESLACHT",
        highlight="VROUW",
    )
    assert fig.layout.legend.title.text == "Geslacht"
    assert {t.name for t in fig.data} == {"Man", "Vrouw", "Onbekend"}
    # highlight noemt de waarde uit de data, niet het label.
    kleuren = {t.name: t.marker.color for t in fig.data}
    assert kleuren["Vrouw"] != kleuren["Man"] == kleuren["Onbekend"]


def test_opleidingsvorm_buiten_de_ho_bestanden_blijft_staan():
    # Elders betekent OPLEIDINGSVORM iets anders (#371): geen vertaling zonder bron.
    store.put(
        "duo:ander:0",
        pd.DataFrame({"OPLEIDINGSVORM": ["DT", "VT"], "N": [1, 2]}),
        KeyMeta(bron="duo", dataset="ander"),
    )
    _, fig = create_plot(data_key="duo:ander:0", chart_type="bar", x="OPLEIDINGSVORM", y="N", title="T")
    assert list(fig.data[0].x) == ["DT", "VT"]


def test_figuur_uit_run_analysis_krijgt_leesbare_titels_en_nederlandse_notatie(cbs_key):
    _, fig = run_analysis(
        code="figure = px.bar(df, x='Perioden_label', y='MboStudenten_1')\nresult = {'ok': True}",
        data_key=cbs_key,
    )
    assert fig.layout.xaxis.title.text == "Studiejaar"
    assert fig.layout.yaxis.title.text == "Mbo-studenten"
    assert fig.layout.separators == ",."
    # De exportrijen houden de bronnamen.
    assert fig.layout.meta["x"] == "Perioden_label"
