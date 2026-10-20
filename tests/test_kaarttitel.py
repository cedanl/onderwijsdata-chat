"""Een kaart met leesbare titels (#640): de kleurenbalk heet naar de maat, niet naar de kolom.

De kleurenbalk heette "MboStudenten_1" (de kolomnaam) en de titel "Mbo-studenten perprovincie". De
kleurenbalk krijgt dezelfde titel als een grafiekas (`kolomlabel`, #418); een titel waarin "per" aan het
niveauwoord vastzit, krijgt zijn spatie terug, ook in create_plot.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from tools import store
from tools.plot import create_choropleth_map, create_plot, schone_titel

_VORM = {"type": "Polygon", "coordinates": [[[5, 52], [6, 52], [6, 53], [5, 52]]]}
_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "id": code, "properties": {"statnaam": naam}, "geometry": _VORM}
        for code, naam in {"PV20": "Groningen", "PV26": "Utrecht"}.items()
    ],
}
_RIJEN = [{"RegioS": "PV20", "MboStudenten_1": 100}, {"RegioS": "PV26", "MboStudenten_1": 200}]


@pytest.fixture(autouse=True)
def _geojson():
    with patch("tools.plot._load_geojson", return_value=_GEOJSON):
        store.clear()
        yield
        store.clear()


def _kaart(kolomtitels: dict | None, title: str = "Mbo-studenten per provincie"):
    store.put(
        "cbs:85353NED", pd.DataFrame(_RIJEN), store.KeyMeta(bron="cbs", dataset="85353NED", kolomtitels=kolomtitels)
    )
    return create_choropleth_map(
        data_key="cbs:85353NED", location_col="RegioS", value_col="MboStudenten_1", title=title, level="provincie"
    )


def test_de_kleurenbalk_heet_naar_de_titel_uit_de_bron():
    _, fig = _kaart({"MboStudenten_1": "Mbo-studenten"})
    assert fig is not None
    assert fig.layout.coloraxis.colorbar.title.text == "Mbo-studenten"
    assert "Mbo-studenten=" in fig.data[0].hovertemplate  # ook het hoverlabel noemt de maat


def test_zonder_titels_uit_de_bron_volgt_de_kleurenbalk_kolomlabel():
    store.put(
        "duo:x:y", pd.DataFrame([{"PROVINCIE": "PV20", "AANTAL_STUDENTEN": 5}]), store.KeyMeta(bron="duo", dataset="x")
    )
    _, fig = create_choropleth_map(data_key="duo:x:y", location_col="PROVINCIE", value_col="AANTAL_STUDENTEN")
    assert fig is not None
    assert fig.layout.coloraxis.colorbar.title.text == "Aantal studenten"


def test_de_export_houdt_de_kolomnaam_van_de_bron():
    _, fig = _kaart({"MboStudenten_1": "Mbo-studenten"})
    assert fig is not None
    assert fig.layout.meta["value_col"] == "MboStudenten_1"
    assert fig.layout.meta["data"][0]["MboStudenten_1"] == 100


def test_een_vastgeplakte_titel_krijgt_zijn_spatie_terug_in_kaart_en_melding():
    melding, fig = _kaart(None, title="Mbo-studenten perprovincie")
    assert fig is not None
    assert fig.layout.title.text == "Mbo-studenten per provincie"
    assert melding.startswith("Kaart 'Mbo-studenten per provincie' aangemaakt")


@pytest.mark.parametrize(
    ("titel", "verwacht"),
    [
        ("Mbo-studenten perprovincie", "Mbo-studenten per provincie"),
        ("Studenten pergemeente, 2024", "Studenten per gemeente, 2024"),
        ("Uitval perCOROP-gebied", "Uitval per COROP-gebied"),
        ("Uitval percorop", "Uitval per corop"),
        ("Instroom perregio", "Instroom per regio"),
        ("PERPROVINCIE", "PER PROVINCIE"),
        ("Perprovincie gezien", "Per provincie gezien"),
        ("Mbo-studenten per provincie", "Mbo-studenten per provincie"),
        ("Uitval in perspectief", "Uitval in perspectief"),
        ("Personeel per instelling", "Personeel per instelling"),
        ("Superprovincie", "Superprovincie"),
        ("", ""),
    ],
)
def test_alleen_per_aan_een_niveauwoord_krijgt_een_spatie(titel, verwacht):
    assert schone_titel(titel) == verwacht


def test_ook_de_grafiektitel_gaat_door_dezelfde_opschoning():
    store.put("test:640", pd.DataFrame([{"JAAR": 2023, "N": 1}, {"JAAR": 2024, "N": 2}]))
    melding, fig = create_plot(data_key="test:640", chart_type="bar", x="JAAR", y="N", title="Studenten perprovincie")
    assert fig is not None
    assert fig.layout.title.text == "Studenten per provincie"
    assert "'Studenten per provincie'" in melding
