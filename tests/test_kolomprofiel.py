"""Per kolom bereik, unieke waarden en -1-cellen, vóór het model filtert (#362).

De catalogus kent per kolom een steekproef: voor p01hoinges "STUDIEJAAR: bereik
2021-2021" en vier provincies, terwijl het bestand 2021-2025 en twaalf provincies
dekt. Het model las dat als volledige dekking. Q2 uit de harness-vergelijking brak
op -1-cellen die het model niet zag aankomen (410 zonder, 425 met uitsluiting).
"""

import json
from unittest.mock import patch

import pandas as pd

from tools import kolomprofiel
from tools.catalog import dataset_details
from tools.duo import get_duo_data

_DATA = pd.DataFrame(
    {
        "STUDIEJAAR": [2021, 2022, 2025, 2025],
        "GESLACHT": ["man", "vrouw", "man", "onbekend"],
        "INSTELLINGSCODE_ACTUEEL": [f"{i:02d}XX" for i in range(4)],
        "AANTAL_INGESCHREVENEN": [-1, 120, 4147, -1],
    }
)
_KEY = "duo:p01hoinges:0"


def test_bereik_voor_getallen_en_waarden_voor_categorieen():
    df = pd.DataFrame({"JAAR": [2025, 2021], "VORM": ["VT", "DT"], "FRACTIE": [0.5, 2.0]})
    assert kolomprofiel.profiel(df, {}) == {
        "JAAR": {"bereik": [2021, 2025]},
        "VORM": {"uniek": 2, "waarden": ["DT", "VT"]},
        "FRACTIE": {"bereik": [0.5, 2]},
    }


def test_veel_unieke_waarden_geeft_alleen_het_aantal():
    df = pd.DataFrame({"CODE": [f"{i:02d}XX" for i in range(kolomprofiel.MAX_WAARDEN + 1)]})
    assert kolomprofiel.profiel(df, {}) == {"CODE": {"uniek": kolomprofiel.MAX_WAARDEN + 1}}


def _laad() -> dict:
    with (
        patch("tools.duo._duo.load", return_value=_DATA.copy()),
        patch("tools.duo._duo.column_definitions", return_value={}),
        patch("tools.duo._duo.resources", return_value=[]),
    ):
        return json.loads(get_duo_data("p01hoinges", 0))


def test_get_duo_data_geeft_het_profiel_zonder_min1_in_het_bereik():
    kolommen = {k["kolom"]: k for k in _laad()["kolommen"]}

    aantal = kolommen["AANTAL_INGESCHREVENEN"]
    assert aantal["bereik"] == [120, 4147]
    assert aantal["min1_cellen"] == 2
    assert kolommen["STUDIEJAAR"]["bereik"] == [2021, 2025]
    assert kolommen["GESLACHT"]["waarden"] == ["man", "onbekend", "vrouw"]
    # Naast een bereik of volledige lijst zijn voorbeelden dubbel; anders blijven ze een voorbeeld.
    assert "voorbeelden" not in kolommen["GESLACHT"]
    assert "voorbeelden" not in kolommen["STUDIEJAAR"]
    assert kolommen["INSTELLINGSCODE_ACTUEEL"]["uniek"] == 4


def _duo_entry() -> dict:
    return {
        "leverancier": "DUO",
        "_ckan_id": "p01hoinges",
        "bron": "Ingeschrevenen hoger onderwijs",
        "_resources": [{"naam": "geslacht hbo"}, {"naam": "geslacht wo"}],
        "_kolommen": {"geslacht hbo": {"STUDIEJAAR": "numeriek (bereik: 2021-2021)"}},
        "_notes_provenance": {"metadata_modified": "2026-07-10T11:37:18.868886"},
    }


def _details() -> dict:
    with patch("tools.catalog._cbs", return_value=[]), patch("tools.catalog._rio_duo", return_value=[_duo_entry()]):
        return json.loads(dataset_details("p01hoinges"))


def test_catalogusvoorbeelden_heten_steekproef():
    details = _details()
    assert "steekproef" in details["kolommen_steekproef"]
    assert "get_duo_data" in details["kolommen_steekproef"]
    assert details["catalogus_bron_gewijzigd"] == "2026-07-10"
    assert "kolomprofiel" not in details


def test_een_geladen_resource_krijgt_zijn_profiel_in_dataset_details():
    _laad()
    profielen = _details()["kolomprofiel"]

    assert list(profielen) == ["0"]
    assert profielen["0"]["AANTAL_INGESCHREVENEN"] == {"bereik": [120, 4147], "min1_cellen": 2}


def test_cbs_details_krijgen_geen_duo_velden():
    entry = {"_cbs_id": "85423NED", "bron": "HO", "_kolommen": {"x": {"Perioden": ["2021JJ00"]}}}
    with patch("tools.catalog._cbs", return_value=[entry]), patch("tools.catalog._rio_duo", return_value=[]):
        details = json.loads(dataset_details("85423NED"))
    assert "kolommen_steekproef" not in details


def test_profiel_blijft_compact_bij_een_echt_bestand():
    """Tokenbudget: twaalf kolommen zoals p01hoinges, met 36 instellingen en 43 gemeenten."""
    n = 4964
    df = pd.DataFrame(
        {
            "STUDIEJAAR": [2021 + i % 5 for i in range(n)],
            "PROVINCIENAAM": [f"Provincie {i % 12}" for i in range(n)],
            "GEMEENTENUMMER": [i % 43 for i in range(n)],
            "GEMEENTENAAM": [f"Gemeente {i % 43}" for i in range(n)],
            "INSTELLINGSCODE_ACTUEEL": [f"{i % 36:02d}XX" for i in range(n)],
            "INSTELLINGSNAAM_ACTUEEL": [f"Hogeschool {i % 36}" for i in range(n)],
            "ONDERDEEL": [f"Onderdeel {i % 8}" for i in range(n)],
            "GESLACHT": [("man", "vrouw", "onbekend")[i % 3] for i in range(n)],
            "AANTAL_INGESCHREVENEN": [i % 1314 for i in range(n)],
        }
    )
    tekst = json.dumps(kolomprofiel.profiel(df, {"AANTAL_INGESCHREVENEN": 321}), ensure_ascii=False)
    assert len(tekst) < 800
