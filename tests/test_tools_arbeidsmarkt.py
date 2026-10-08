"""Arbeidsmarkt-tools: echte bronwaarden, peildatum uit de data, dezelfde scopepoort (#441, #435).

CH-37: get_roa_benchmark gaf vaste, in de code geschreven waarden ("~80%") als ROA-cijfers door,
en beide tools liepen buiten de scopepoort. CH-23: ze haalden private functies uit
data/dashboard.py, terwijl dashboards overal uit staan.
"""

import ast
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from data import arbeidsmarkt
from tools.arbeidsmarkt import get_roa_benchmark, get_uwv_vacatures

_UWV = pd.DataFrame(
    {
        "PEILDATUM": ["16-05-2023"] * 3,
        "PROVINCIE": ["Utrecht", "Utrecht", "Gelderland"],
        "BEROEPENCLUSTER": ["Zorg en welzijn", "ICT", "ICT"],
        "AANTAL": [900, 300, 50],
    }
)


def _roa_rij(regio, niveau, onderwerp, perc=None, aantal=None, typering=None, thema=arbeidsmarkt._ROA_SIS):
    return {
        "regionaam": regio,
        "thema": thema,
        "aggregatieniveau": arbeidsmarkt._ROA_NIVEAU,
        "detailniveau": niveau,
        "onderwerp": onderwerp,
        "perc": perc,
        "aantal": aantal,
        "typering": typering,
        "versie": "v20251218",
    }


_ROA = pd.DataFrame(
    [
        _roa_rij("Nederland", "Mbo4", "werkloosheid", perc="3"),
        _roa_rij("Nederland", "Bachelor", "vast dienstverband", perc="77"),
        _roa_rij("Nederland", "Vmbo-g/t", "werkloosheid", perc="9"),  # buiten het profiel
        _roa_rij(
            "Groningen",
            "Mbo4",
            "ITA toekomstige arbeidsmarktsituatie in 2030",
            typering="slecht",
            thema=arbeidsmarkt._ROA_PROGNOSE,
        ),
        _roa_rij(
            "Nederland",
            "Mbo4",
            "ITA toekomstige arbeidsmarktsituatie in 2030",
            typering="redelijk",
            thema=arbeidsmarkt._ROA_PROGNOSE,
        ),
    ]
)


@pytest.fixture
def bronnen():
    with (
        patch.object(arbeidsmarkt, "_uwv", return_value=_UWV),
        patch.object(arbeidsmarkt, "_roa", return_value=_ROA),
        patch("tools.arbeidsmarkt.scope_blokkade", return_value=None),
    ):
        yield


def test_roa_geeft_alleen_bronwaarden_landelijk_en_binnen_het_profiel(bronnen):
    uit = json.loads(get_roa_benchmark())

    assert uit["versie"] == "v20251218"
    assert uit["schoolverlaters_sis_2024"] == {
        "Mbo4": {"werkloosheid": {"perc": 3}},
        "Bachelor": {"vast dienstverband": {"perc": 77}},
    }
    # Landelijk: de regionale typering (Groningen) wint niet.
    assert uit["prognose_tot_2030"] == {
        "Mbo4": {"ITA toekomstige arbeidsmarktsituatie in 2030": {"typering": "redelijk"}}
    }
    assert "~" not in json.dumps(uit)


def test_roa_onbekende_sector_noemt_de_geldige(bronnen):
    with patch.object(arbeidsmarkt, "roa_sectoren", return_value=["Mbo4 - techniek en ict"]):
        uit = get_roa_benchmark("ICT")

    assert "Mbo4 - techniek en ict" in uit


def test_uwv_peildatum_komt_uit_de_data(bronnen):
    uit = json.loads(get_uwv_vacatures("Utrecht"))

    assert uit["peildatum"] == "2023-05-16"
    assert uit["totaal_vacatures"] == 1200
    assert uit["clusters"] == {"Zorg en welzijn": 900, "ICT": 300}


def test_uwv_sector_filtert_via_de_mapping(bronnen):
    with patch.dict(arbeidsmarkt.SECTOR_CLUSTER_MAP, {"GEZONDHEIDSZORG": ["Zorg en welzijn"]}, clear=True):
        uit = json.loads(get_uwv_vacatures("Utrecht", "GEZONDHEIDSZORG"))
        onbekend = get_uwv_vacatures("Utrecht", "Zorg")

    assert uit["vacatures_sector"] == 900 and uit["clusters"] == {"Zorg en welzijn": 900}
    assert "GEZONDHEIDSZORG" in onbekend


def test_uwv_onbekende_provincie_noemt_de_geldige(bronnen):
    assert "Gelderland" in get_uwv_vacatures("Atlantis")


@pytest.mark.parametrize(("tool", "args"), [(get_uwv_vacatures, ("Utrecht",)), (get_roa_benchmark, ())])
def test_buiten_de_scopepoort_wordt_niets_geladen(tool, args):
    """Dezelfde fail-closed poort als CBS/DUO/RIO (CH-37): zonder scopebesluit geen data."""
    blokkade = json.dumps({"buiten_scope": True})
    with (
        patch("tools.arbeidsmarkt.scope_blokkade", return_value=blokkade),
        patch.object(arbeidsmarkt, "_uwv") as uwv,
        patch.object(arbeidsmarkt, "_roa") as roa,
    ):
        assert tool(*args) == blokkade

    uwv.assert_not_called()
    roa.assert_not_called()


def test_de_tools_hangen_niet_aan_de_dashboardlaag():
    """CH-23: de chattools importeerden private functies uit data/dashboard.py."""
    bron = Path(__file__).parent.parent / "tools" / "arbeidsmarkt.py"
    imports = {n.module for n in ast.walk(ast.parse(bron.read_text())) if isinstance(n, ast.ImportFrom) and n.module}
    assert "data.dashboard" not in imports


def test_uwv_en_roa_ais2030_zijn_binnen_het_scopeprofiel():
    from tools.catalog import scope_blokkade

    assert scope_blokkade("uwv-open-match-data") is None
    assert scope_blokkade("ais2030") is None
