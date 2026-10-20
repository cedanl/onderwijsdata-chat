"""Het recept bij een kaart tekent dezelfde kaart als de app (#630).

Het recept draait buiten de app: zonder `tools`, met alleen pandas, plotly en urllib. Deze tests voeren het uit
tegen een dubbelganger van de GeoJSON en vergelijken de figuur met die van `create_choropleth_map`.
"""

import io
import json
from unittest.mock import patch

import pandas as pd
import plotly.graph_objects as go
import pytest

from tools import store
from tools.plot import create_choropleth_map
from tools.snippet import generate

_VORM = {"type": "Polygon", "coordinates": [[[5, 52], [6, 52], [6, 53], [5, 52]]]}


def _geo(namen: dict[str, str]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": code, "properties": {"statnaam": naam}, "geometry": _VORM}
            for code, naam in namen.items()
        ],
    }


_GEOJSON = {
    "provincie": _geo({"PV20": "Groningen", "PV21": "Fryslân", "PV22": "Drenthe", "PV26": "Utrecht"}),
    "gemeente": _geo(
        {
            "GM0014": "Groningen",
            "GM0344": "Utrecht",
            "GM0363": "Amsterdam",
            "GM0518": "'s-Gravenhage",
            "GM0164": "Hengelo (O.)",
            "GM0893": "Bergen (L.)",
            "GM0373": "Bergen (NH.)",
        }
    ),
    "corop": _geo({"CR01": "Oost-Groningen", "CR17": "Utrecht"}),
}
_URL_NIVEAU = {
    "https://cartomap.github.io/nl/wgs84/provincie_2024.geojson": "provincie",
    "https://cartomap.github.io/nl/wgs84/gemeente_2024.geojson": "gemeente",
    "https://cartomap.github.io/nl/wgs84/coropgebied_2024.geojson": "corop",
}


def _urlopen(url, timeout=None):
    return io.BytesIO(json.dumps(_GEOJSON[_URL_NIVEAU[url]]).encode())  # BytesIO is zelf een contextmanager


@pytest.fixture(autouse=True)
def _buiten_de_app(monkeypatch):
    monkeypatch.setattr(go.Figure, "show", lambda self, *a, **k: None)
    with (
        patch("tools.plot._load_geojson", side_effect=lambda niveau: _GEOJSON[niveau]),
        patch("urllib.request.urlopen", _urlopen),
    ):
        store.clear()
        yield
        store.clear()


def _args(locaties: list, level: str = "auto") -> dict:
    rijen = [{"LOC": loc, "N": i + 1} for i, loc in enumerate(locaties)]
    return {"data": rijen, "location_col": "LOC", "value_col": "N", "title": "Kaart", "level": level}


def _app(args: dict) -> tuple[str, go.Figure]:
    store.put("test:kaart630", pd.DataFrame(args["data"]))
    melding, fig = create_choropleth_map(
        data_key="test:kaart630",
        location_col=args["location_col"],
        value_col=args["value_col"],
        title=args["title"],
        level=args["level"],
    )
    assert fig is not None, melding
    return melding, fig


def _recept(args: dict, melding: str) -> dict:
    snippet = generate("create_choropleth_map", args, melding)
    assert snippet is not None
    namespace: dict = {}
    exec(snippet, namespace)
    return namespace


def test_het_recept_draagt_de_geojson_en_de_featureidkey():
    args = _args(["PV20", "PV26"])
    snippet = generate("create_choropleth_map", args, "Kaart 'Kaart' aangemaakt (2 provincies).")
    assert snippet is not None
    assert "provincie_2024.geojson" in snippet
    assert 'featureidkey="id"' in snippet and "geojson=geojson" in snippet
    assert "map_style" in snippet and "Blues" in snippet  # dezelfde opmaak als de app


@pytest.mark.parametrize(
    ("melding", "level", "url"),
    [
        ("Kaart 'K' aangemaakt (12 gemeenten).", "auto", "gemeente_2024"),
        ("Kaart 'K' aangemaakt (3 COROP-gebieden).", "auto", "coropgebied_2024"),
        ("Kaart 'K' aangemaakt (2 provincies).", "auto", "provincie_2024"),
        ("Kaart 'K' aangemaakt (2 provincies).", "gemeente", "gemeente_2024"),  # een expliciet niveau wint
    ],
)
def test_het_niveau_volgt_het_argument_en_anders_de_melding_van_de_app(melding, level, url):
    snippet = generate("create_choropleth_map", {**_args(["x"]), "level": level}, melding)
    assert snippet is not None and f"{url}.geojson" in snippet


@pytest.mark.parametrize(
    ("locaties", "level"),
    [
        (["PV20", "PV26"], "auto"),
        (["pv26", "PV22"], "auto"),
        (["Utrecht", "DRENTHE", "Friesland", "fryslân"], "auto"),
        (["'S-GRAVENHAGE", "S-GRAVENHAGE", "Amsterdam", "Hengelo (O.)"], "gemeente"),
        (["HENGELO", "Amsterdam"], "gemeente"),
        ([344, "363.0", "GM0518"], "gemeente"),
        (["CR01", "CR17"], "auto"),
        (["Amsterdam", "Atlantis", "BERGEN"], "gemeente"),
    ],
)
def test_het_recept_tekent_dezelfde_codes_als_de_app(locaties, level):
    args = _args(locaties, level)
    melding, fig_app = _app(args)
    namespace = _recept(args, melding)
    assert list(namespace["fig"].data[0].locations) == list(fig_app.data[0].locations)
    assert list(namespace["fig"].data[0].z) == list(fig_app.data[0].z)


def test_het_recept_noemt_wat_niet_op_de_kaart_staat(capsys):
    args = _args(["Amsterdam", "Atlantis"], "gemeente")
    melding, _ = _app(args)
    _recept(args, melding)
    uit = capsys.readouterr().out
    assert "Atlantis" in uit and "Amsterdam" not in uit


def test_het_recept_tekent_dezelfde_kleurenbalk_en_titel_als_de_app():
    """#640: de maatnaam uit de bron op de kleurenbalk en de titel met spatie, ook in het recept."""
    rijen = [{"LOC": "PV20", "MboStudenten_1": 1}, {"LOC": "PV26", "MboStudenten_1": 2}]
    meta = store.KeyMeta(
        bron="cbs", dataset="85353NED", afgeleid_van="cbs:85353NED", kolomtitels={"MboStudenten_1": "Mbo-studenten"}
    )
    store.put("cbs:85353NED:sel640", pd.DataFrame(rijen), meta)
    args = {
        "data_key": "cbs:85353NED:sel640",
        "location_col": "LOC",
        "value_col": "MboStudenten_1",
        "title": 'Mbo-studenten "2024" perprovincie',
        "level": "auto",
    }
    melding, fig_app = create_choropleth_map(
        data_key=args["data_key"], location_col="LOC", value_col="MboStudenten_1", title=args["title"]
    )
    assert fig_app is not None, melding
    fig = _recept(args, melding)["fig"]
    assert fig_app.layout.coloraxis.colorbar.title.text == "Mbo-studenten"
    assert fig.layout.coloraxis.colorbar.title.text == fig_app.layout.coloraxis.colorbar.title.text
    assert fig_app.layout.title.text == 'Mbo-studenten "2024" per provincie'
    assert fig.layout.title.text == fig_app.layout.title.text
    assert fig.data[0].hovertemplate == fig_app.data[0].hovertemplate


def test_zonder_titels_volgt_ook_het_recept_kolomlabel():
    args = {**_args(["PV20", "PV26"]), "value_col": "AANTAL_STUDENTEN"}
    args["data"] = [{"LOC": r["LOC"], "AANTAL_STUDENTEN": r["N"]} for r in args["data"]]
    melding, fig_app = _app(args)
    fig = _recept(args, melding)["fig"]
    assert fig_app.layout.coloraxis.colorbar.title.text == "Aantal studenten"
    assert fig.layout.coloraxis.colorbar.title.text == "Aantal studenten"
