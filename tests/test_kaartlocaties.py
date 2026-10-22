"""create_choropleth_map: namen worden codes, en een kaart zonder treffers is een fout (#628)."""

from unittest.mock import patch

import pandas as pd
import plotly.graph_objects as go
import pytest

from tools import store
from tools.plot import create_choropleth_map

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
    "provincie": _geo(
        {"PV20": "Groningen", "PV21": "Fryslân", "PV22": "Drenthe", "PV24": "Flevoland", "PV26": "Utrecht"}
    ),
    "gemeente": _geo(
        {
            "GM0014": "Groningen",
            "GM0344": "Utrecht",
            "GM0363": "Amsterdam",
            "GM0384": "Delft",
            "GM0392": "Haarlem",
            "GM0518": "'s-Gravenhage",
            "GM0164": "Hengelo (O.)",
            "GM0893": "Bergen (L.)",
            "GM0373": "Bergen (NH.)",
        }
    ),
    "corop": _geo({"CR01": "Oost-Groningen", "CR17": "Utrecht"}),
}


@pytest.fixture(autouse=True)
def _geojson():
    with patch("tools.plot._load_geojson", side_effect=lambda niveau: _GEOJSON[niveau]):
        yield


def _kaart(locaties: list, level: str = "auto", kolom: str = "LOC") -> tuple[str, go.Figure | None]:
    store.put("test:kaart628", pd.DataFrame({kolom: locaties, "N": range(1, len(locaties) + 1)}))
    return create_choropleth_map(data_key="test:kaart628", location_col=kolom, value_col="N", title="T", level=level)


def _codes(fig: go.Figure) -> list[str]:
    return list(fig.data[0].locations)


def test_provincienamen_worden_provinciecodes():
    msg, fig = _kaart(["Utrecht", "DRENTHE", "Friesland", "fryslân"])
    assert fig is not None
    assert _codes(fig) == ["PV26", "PV22", "PV21", "PV21"]
    assert "4 provincies" in msg


def test_gemeentenamen_in_de_spelling_van_duo():
    msg, fig = _kaart(["'S-GRAVENHAGE", "ALKMAAR", "HENGELO (O)", "DELFT", "Amsterdam"])
    assert fig is not None
    assert _codes(fig) == ["GM0518", "GM0164", "GM0384", "GM0363"]
    assert "4 gemeenten" in msg
    assert "ALKMAAR" in msg and "niet op de kaart" in msg  # genoemd, niet stil weggelaten


def test_gemeentenaam_zonder_apostrof_en_met_punt():
    _, fig = _kaart(["S-GRAVENHAGE", "Hengelo (O.)"], level="gemeente")
    assert fig is not None and _codes(fig) == ["GM0518", "GM0164"]


def test_een_naam_zonder_toevoeging_past_bij_het_ene_gebied_dat_zo_heet():
    # DUO schrijft HENGELO, CBS Hengelo (O.): één gebied heet zo, dus is de keuze niet gegokt.
    _, fig = _kaart(["HENGELO", "Delft"], level="gemeente")
    assert fig is not None and _codes(fig) == ["GM0164", "GM0384"]


def test_een_naam_zonder_toevoeging_die_twee_gebieden_kan_zijn_wordt_niet_gegokt():
    msg, fig = _kaart(["BERGEN", "Delft"], level="gemeente")
    assert fig is not None and _codes(fig) == ["GM0384"]
    assert "BERGEN" in msg


def test_gemeentenummers_van_duo():
    _, fig = _kaart([344, "363.0", "GM0384"], level="gemeente")
    assert fig is not None and _codes(fig) == ["GM0344", "GM0363", "GM0384"]


def test_cbs_codes_blijven_werken_ook_in_kleine_letters():
    _, fig = _kaart(["PV20", "pv26"])
    assert fig is not None and _codes(fig) == ["PV20", "PV26"]
    _, fig = _kaart(["GM0344", "GM0363"])
    assert fig is not None and _codes(fig) == ["GM0344", "GM0363"]


def test_auto_kiest_het_niveau_waar_de_namen_passen():
    _, provincies = _kaart(["Drenthe", "Flevoland", "Utrecht"])
    assert provincies is not None and _codes(provincies)[0] == "PV22"
    _, gemeenten = _kaart(["Delft", "Haarlem", "Amsterdam"])
    assert gemeenten is not None and _codes(gemeenten)[0] == "GM0384"


def test_een_naam_die_provincie_en_gemeente_is_geeft_de_provincie():
    # Bij gelijke dekking wint het grootste gebied: de lijst Utrecht, Groningen is een lijst provincies.
    _, fig = _kaart(["Utrecht", "Groningen"])
    assert fig is not None and _codes(fig) == ["PV26", "PV20"]


def test_expliciet_niveau_dat_niet_past_wordt_geweigerd_met_reden():
    msg, fig = _kaart(["Drenthe", "Flevoland"], level="gemeente")
    assert fig is None
    assert "gemeente" in msg and "Drenthe" in msg


def test_geen_enkele_naam_op_de_kaart_geeft_een_fout_geen_lege_kaart():
    msg, fig = _kaart(["Atlantis", "Lemuria"])
    assert fig is None
    assert "Atlantis" in msg and "aangemaakt" not in msg


def test_een_onbekende_naam_in_een_mix_wordt_genoemd_en_de_rest_getekend():
    msg, fig = _kaart(["Drenthe", "Flevoland", "Atlantis"])
    assert fig is not None and _codes(fig) == ["PV22", "PV24"]
    assert "Atlantis" in msg and "1 van 3" in msg


def test_de_hoverlabel_toont_de_naam_en_de_data_van_de_kaart_houdt_de_namen():
    _, fig = _kaart(["Drenthe", "Utrecht"])
    assert fig is not None
    assert list(fig.data[0].hovertext) == ["Drenthe", "Utrecht"]
    assert [r["LOC"] for r in fig.layout.meta["data"]] == ["Drenthe", "Utrecht"]


def test_de_hoverlabel_toont_de_naam_uit_de_geojson_in_elke_spelling_van_de_data():
    # #659: het label noemt het gebied zoals de kaart het kent; de CSV houdt de spelling van de bron.
    _, fig = _kaart(["'S-GRAVENHAGE", "HENGELO", "GM0344", 363], level="gemeente")
    assert fig is not None
    assert list(fig.data[0].hovertext) == ["'s-Gravenhage", "Hengelo (O.)", "Utrecht", "Amsterdam"]
    assert [r["LOC"] for r in fig.layout.meta["data"]] == ["'S-GRAVENHAGE", "HENGELO", "GM0344", "363"]


def test_een_gebied_zonder_naam_in_de_geojson_houdt_de_waarde_uit_de_data():
    geojson = _geo({"PV20": "Groningen", "PV26": "Utrecht"})
    del geojson["features"][1]["properties"]["statnaam"]
    with patch("tools.plot._load_geojson", return_value=geojson):
        _, fig = _kaart(["Groningen", "PV26"], level="provincie")
    assert fig is not None
    assert list(fig.data[0].hovertext) == ["Groningen", "PV26"]
    assert list(fig.data[0].locations) == ["PV20", "PV26"]
