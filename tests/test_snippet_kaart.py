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


@pytest.mark.parametrize(
    ("locaties", "level"),
    [
        (["PV20", "PV26"], "auto"),
        (["Utrecht", "DRENTHE", "Friesland"], "auto"),
        (["'S-GRAVENHAGE", "HENGELO", 344], "gemeente"),
    ],
)
def test_het_recept_toont_bij_een_tik_dezelfde_naam_als_de_app(locaties, level):
    # #659: het label noemt de gebiedsnaam uit de GeoJSON, ook als de data CBS-codes heeft.
    args = _args(locaties, level)
    melding, fig_app = _app(args)
    fig = _recept(args, melding)["fig"]
    assert list(fig.data[0].hovertext) == list(fig_app.data[0].hovertext)
    assert not any(str(tekst).startswith(("PV", "GM", "CR")) for tekst in fig.data[0].hovertext)


def test_het_recept_zet_de_naam_niet_de_code_in_het_label():
    args = _args(["PV20", "PV26"])
    snippet = generate("create_choropleth_map", args, "Kaart 'Kaart' aangemaakt (2 provincies).")
    assert snippet is not None
    assert 'hover_name="kaartnaam"' in snippet and "hover_name='LOC'" not in snippet
    assert 'df["kaartnaam"] = df["kaartcode"].map(' in snippet


def test_het_recept_noemt_wat_niet_op_de_kaart_staat(capsys):
    args = _args(["Amsterdam", "Atlantis"], "gemeente")
    melding, _ = _app(args)
    _recept(args, melding)
    uit = capsys.readouterr().out
    assert "Atlantis" in uit and "Amsterdam" not in uit


def test_de_kaartopties_tonen_heel_nederland_in_een_standaardfiguur():
    """Met centrum 52,3 en zoom 6 viel Limburg onderaan buiten de kaart (#642); app en recept delen KAART_OPTIES."""
    import math
    from pathlib import Path
    from typing import cast

    from tools.plot import KAART_OPTIES

    fixture = Path(__file__).parent / "e2e" / "fixtures" / "kaart-provincies.json"
    punten: list[tuple[float, float]] = []

    def loop(c: list) -> None:
        if isinstance(c[0], (int, float)):
            punten.append((float(c[0]), float(c[1])))
        else:
            for d in c:
                loop(d)

    for f in json.loads(fixture.read_text())["data"][0]["geojson"]["features"]:
        loop(f["geometry"]["coordinates"])

    def mx(lon: float) -> float:
        return (lon + 180) / 360

    def my(lat: float) -> float:
        return (1 - math.log(math.tan(math.pi / 4 + lat * math.pi / 360)) / math.pi) / 2

    centrum = cast(dict[str, float], KAART_OPTIES["center"])
    schaal = 512 * 2 ** cast(float, KAART_OPTIES["zoom"])
    cx, cy = mx(centrum["lon"]), my(centrum["lat"])
    # Plotly-standaard 700 x 450, min de kleurenbalk (100) en de titelmarge (60).
    breedte, hoogte = 600, 390
    assert max(abs(mx(lon) - cx) for lon, _ in punten) * schaal <= breedte / 2
    assert max(abs(my(lat) - cy) for _, lat in punten) * schaal <= hoogte / 2


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
    # Ook de getallen zoals de app ze toont (#655): Nederlandse scheidingstekens, geen "k" op de kleurenbalk.
    assert fig.layout.separators == fig_app.layout.separators == ",."
    assert fig.layout.coloraxis.colorbar.tickformat == fig_app.layout.coloraxis.colorbar.tickformat == ","


def test_zonder_titels_volgt_ook_het_recept_kolomlabel():
    args = {**_args(["PV20", "PV26"]), "value_col": "AANTAL_STUDENTEN"}
    args["data"] = [{"LOC": r["LOC"], "AANTAL_STUDENTEN": r["N"]} for r in args["data"]]
    melding, fig_app = _app(args)
    fig = _recept(args, melding)["fig"]
    assert fig_app.layout.coloraxis.colorbar.title.text == "Aantal studenten"
    assert fig.layout.coloraxis.colorbar.title.text == "Aantal studenten"


def test_een_aanhalingsteken_in_de_kolomnaam_breekt_het_recept_niet(capsys):
    """#640-review: de kolomnamen staan als Python-literal in het recept, ook met een `"` erin."""
    gewoon = _args(["Amsterdam", "Atlantis", "Utrecht"], "gemeente")
    rijen = [{'Regio "Noord"': r["LOC"], 'Waarde "x"': r["N"]} for r in gewoon["data"]]
    args = {**gewoon, "data": rijen, "location_col": 'Regio "Noord"', "value_col": 'Waarde "x"'}
    melding, fig_app = _app(args)
    recept = generate("create_choropleth_map", args, melding)
    assert recept is not None
    compile(recept, "<recept>", "exec")

    fig = _recept(args, melding)["fig"]
    niet_op_kaart = capsys.readouterr().out
    fig_gewoon = _recept(gewoon, _app(gewoon)[0])["fig"]

    assert list(fig.data[0].locations) == list(fig_app.data[0].locations) == list(fig_gewoon.data[0].locations)
    assert list(fig.data[0].z) == list(fig_app.data[0].z) == list(fig_gewoon.data[0].z)
    assert niet_op_kaart == capsys.readouterr().out == "Niet op de kaart: ['Atlantis']\n"
