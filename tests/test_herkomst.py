"""Herkomst van een data_key: bron plus de selecties ertussen, voor de grafiekexport (#118).

Een CSV naast de grafiek moet te herleiden zijn tot dataset en filters; anders
is het een tabel zonder bron.
"""

import json
from unittest.mock import patch

import pandas as pd
import plotly.io as pio
import pytest

from tools import store
from tools.csv_export import naar_csv
from tools.exportnoten import herkomstregels
from tools.plot import create_choropleth_map, create_plot
from tools.query import query_data
from tools.store import KeyMeta

_DF = pd.DataFrame(
    {
        "STUDIEJAAR": [2022, 2023, 2023],
        "INSTELLINGSNAAM": ["HU", "HU", "Avans"],
        "AANTAL": [10, 12, 7],
    }
)


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
    key = json.loads(
        query_data(
            "duo:p01hoinges:0", filters={"INSTELLINGSNAAM": "HU"}, group_by=["STUDIEJAAR"], aggregate={"AANTAL": "sum"}
        )
    )["data_key"]

    regels = store.herkomst(key)
    assert regels[0] == "bron: DUO, dataset p01hoinges, resource 0"
    assert (
        regels[1]
        == 'selectie: filters {"INSTELLINGSNAAM": "HU"}; groepering ["STUDIEJAAR"]; aggregatie {"AANTAL": "sum"}'
    )


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
    assert meta["herkomst"][: len(store.herkomst(key))] == store.herkomst(key)
    assert meta["herkomst"] == herkomstregels(key)


def test_de_grafiek_draagt_het_dataset_id_voor_de_csv_naam():
    """De grafiek-CSV heet <titel>_<dataset-id>.csv, net als de tabel-CSV (#533)."""
    _bron()
    key = json.loads(query_data("duo:p01hoinges:0", filters={"INSTELLINGSNAAM": "HU"}))["data_key"]

    _, fig = create_plot(chart_type="bar", x="STUDIEJAAR", y="AANTAL", title="HU", data_key=key)

    assert json.loads(pio.to_json(fig))["layout"]["meta"]["dataset"] == "p01hoinges"


def test_een_grafiek_zonder_data_key_heeft_geen_dataset_id():
    rows = [{"STUDIEJAAR": 2022, "AANTAL": 1}, {"STUDIEJAAR": 2023, "AANTAL": 2}]

    _, fig = create_plot(rows, "bar", "STUDIEJAAR", "AANTAL", "HU")

    assert "dataset" not in json.loads(pio.to_json(fig))["layout"]["meta"]


# --- de CSV bij een grafiek zegt hetzelfde als de tabel-CSV (#809) --------------------------------------------------


def _csvkop(key: str) -> list[str]:
    return [regel.removeprefix("# ") for regel in (naar_csv(key) or "").splitlines() if regel.startswith("# ")]


def _grafiek(key: str) -> list[str]:
    _, fig = create_plot(chart_type="bar", x="STUDIEJAAR", y="AANTAL", title="T", data_key=key)
    return json.loads(pio.to_json(fig))["layout"]["meta"]["herkomst"]


def test_een_grafiek_op_een_cbs_key_draagt_de_inhoudshash_van_de_tabel_csv():
    store.put("cbs:85423NED:0", _DF, KeyMeta(bron="cbs", dataset="85423NED"))

    hash_regels = [r for r in _csvkop("cbs:85423NED:0") if r.startswith("inhoudshash van de brontabel: ")]
    assert len(hash_regels) == 1
    assert hash_regels[0] in _grafiek("cbs:85423NED:0")


def test_een_grafiek_op_een_duo_selectie_draagt_de_md5_van_het_bestand():
    store.put("duo:p01hoinges:0", _DF, KeyMeta(bron="duo", dataset="p01hoinges", resource=0, bronhash="0123abcd" * 4))
    key = json.loads(query_data("duo:p01hoinges:0", filters={"INSTELLINGSNAAM": "HU"}))["data_key"]

    md5 = [r for r in _csvkop("duo:p01hoinges:0") if r.startswith("md5 van het DUO-bestand: 0123abcd")]
    assert len(md5) == 1
    assert md5[0] in herkomstregels("duo:p01hoinges:0")
    assert _grafiek("duo:p01hoinges:0") == _csvkop("duo:p01hoinges:0") == herkomstregels("duo:p01hoinges:0")
    assert _grafiek(key) == herkomstregels(key)


def test_ook_de_kaart_draagt_de_herkomstregels():
    rijen = pd.DataFrame({"RegioS": ["PV20", "PV21"], "Waarde": [1, 2]})
    store.put("cbs:85354NED:kaart", rijen, KeyMeta(bron="cbs", dataset="85354NED"))
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": code,
                "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [[[5, 51], [6, 51], [6, 52], [5, 51]]]},
            }
            for code in ("PV20", "PV21")
        ],
    }
    with patch("tools.plot._load_geojson", return_value=geojson):
        _, fig = create_choropleth_map(
            data_key="cbs:85354NED:kaart", location_col="RegioS", value_col="Waarde", title="K"
        )

    regels = json.loads(pio.to_json(fig))["layout"]["meta"]["herkomst"]
    assert regels == herkomstregels("cbs:85354NED:kaart")
    assert any(r.startswith("inhoudshash van de brontabel: ") for r in regels)
