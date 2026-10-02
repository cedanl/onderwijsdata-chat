"""Herkomst van een data_key: bron plus de selecties ertussen, voor de grafiekexport (#118).

Een CSV naast de grafiek moet te herleiden zijn tot dataset en filters; anders
is het een tabel zonder bron.
"""
import json

import pandas as pd
import plotly.io as pio
import pytest

from tools import store
from tools.plot import create_plot
from tools.query import query_data
from tools.store import KeyMeta

_DF = pd.DataFrame({
    "STUDIEJAAR": [2022, 2023, 2023],
    "INSTELLINGSNAAM": ["HU", "HU", "Avans"],
    "AANTAL": [10, 12, 7],
})


@pytest.fixture(autouse=True)
def _clean_store():
    store.clear()
    yield
    store.clear()


def _bron():
    store.put("duo:p01hoinges:0", _DF, KeyMeta(bron="duo", dataset="p01hoinges", resource=0))


def test_een_geladen_key_noemt_bron_dataset_en_resource():
    _bron()
    assert store.herkomst("duo:p01hoinges:0") == ["bron: DUO, dataset p01hoinges, resource 0"]


def test_een_selectie_noemt_ook_de_filters_kolommen_en_aggregatie():
    _bron()
    key = json.loads(query_data("duo:p01hoinges:0", filters={"INSTELLINGSNAAM": "HU"},
                                group_by=["STUDIEJAAR"], aggregate={"AANTAL": "sum"}))["data_key"]

    regels = store.herkomst(key)
    assert regels[0] == "bron: DUO, dataset p01hoinges, resource 0"
    assert regels[1] == 'selectie: filters {"INSTELLINGSNAAM": "HU"}; groepering ["STUDIEJAAR"]; aggregatie {"AANTAL": "sum"}'


def test_een_selectie_van_een_selectie_houdt_beide_stappen_in_volgorde():
    _bron()
    k1 = json.loads(query_data("duo:p01hoinges:0", filters={"INSTELLINGSNAAM": "HU"}))["data_key"]
    k2 = json.loads(query_data(k1, filters={"STUDIEJAAR__gte": 2023}))["data_key"]

    assert store.herkomst(k2)[1:] == [
        'selectie: filters {"INSTELLINGSNAAM": "HU"}',
        'selectie: filters {"STUDIEJAAR__gte": 2023}',
    ]


def test_een_onbekende_key_heeft_geen_herkomst():
    assert store.herkomst("nergens") == []


def test_de_grafiek_draagt_de_herkomst_voor_de_export():
    _bron()
    key = json.loads(query_data("duo:p01hoinges:0", filters={"INSTELLINGSNAAM": "HU"}))["data_key"]

    _, fig = create_plot(chart_type="bar", x="STUDIEJAAR", y="AANTAL", title="HU", data_key=key)

    meta = json.loads(pio.to_json(fig))["layout"]["meta"]
    assert meta["herkomst"] == store.herkomst(key)
