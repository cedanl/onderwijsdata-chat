"""Arbeidsmarkt-tools: echte bronwaarden, peildatum uit de data, dezelfde scopepoort (#441, #435).

CH-37: get_roa_benchmark gaf vaste, in de code geschreven waarden ("~80%") als ROA-cijfers door,
en beide tools liepen buiten de scopepoort. CH-23: ze haalden private functies uit
data/dashboard.py, terwijl dashboards overal uit staan. #449: get_uwv_vacatures telde clusters
die bij twee sectoren horen dubbel en zei niet dat UWV geen opleidingsniveau kent. #450:
get_roa_benchmark gooide de regionale prognoses weg en kende de mastersectoren niet.
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
        "PEILDATUM": ["16-05-2023"] * 4,
        "PROVINCIE": ["Utrecht", "Utrecht", "Utrecht", "Gelderland"],
        "GEMEENTE": ["Utrecht", "Amersfoort", "Utrecht", "Arnhem"],
        "BEROEPENCLUSTER": ["Zorg en welzijn", "ICT", "ICT", "ICT"],
        "AANTAL": [900, 200, 100, 50],
    }
)


def _roa_rij(regio, niveau, onderwerp, perc=None, aantal=None, typering=None, thema=arbeidsmarkt._ROA_SIS):
    return {
        "regionaam": regio,
        "thema": thema,
        "aggregatieniveau": arbeidsmarkt._ROA_SECTOR if " - " in niveau else arbeidsmarkt._ROA_NIVEAU,
        "detailniveau": niveau,
        "onderwerp": onderwerp,
        "perc": perc,
        "aantal": aantal,
        "typering": typering,
        "versie": "v20251218",
    }


_ITA = "ITA toekomstige arbeidsmarktsituatie in 2030"
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
        # Regionaal heeft ROA alleen de prognose, geen schoolverlatersinformatie.
        _roa_rij("Midden-Utrecht", "Mbo4", _ITA, typering="goed", thema=arbeidsmarkt._ROA_PROGNOSE),
        _roa_rij("provincie Utrecht", "Mbo4", _ITA, typering="redelijk", thema=arbeidsmarkt._ROA_PROGNOSE),
        _roa_rij("Nederland", "Mbo4 - techniek en ict", _ITA, typering="slecht", thema=arbeidsmarkt._ROA_PROGNOSE),
        _roa_rij("Nederland", "Master - techniek en ict", "werkloosheid", perc="4"),
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


def test_roa_zonder_regio_is_landelijk_zonder_terugval(bronnen):
    uit = json.loads(get_roa_benchmark())

    assert uit["regio"] == "Nederland"
    assert "terugval" not in uit and "regiotype" not in uit


def test_roa_bestaande_arbeidsmarktregio(bronnen):
    uit = json.loads(get_roa_benchmark(regio="midden-utrecht"))

    assert (uit["regio"], uit["regiotype"]) == ("Midden-Utrecht", "arbeidsmarktregio")
    assert uit["prognose_tot_2030"] == {"Mbo4": {_ITA: {"typering": "goed"}}}
    # Schoolverlatersinformatie is er alleen landelijk: dat staat erbij, het wordt niet stil vervangen.
    assert uit["schoolverlaters_sis_2024"]["Mbo4"] == {"werkloosheid": {"perc": 3}}
    assert uit["herkomst"] == {"schoolverlaters_sis_2024": "Nederland", "prognose_tot_2030": "Midden-Utrecht"}
    assert "Midden-Utrecht" in uit["terugval"] and "landelijk" in uit["terugval"]


def test_roa_provincie_op_haar_eigen_naam(bronnen):
    uit = json.loads(get_roa_benchmark(regio="Utrecht"))

    assert (uit["regio"], uit["regiotype"]) == ("provincie Utrecht", "provincie")
    assert uit["prognose_tot_2030"] == {"Mbo4": {_ITA: {"typering": "redelijk"}}}


def test_roa_regio_zonder_cijfers_voor_de_sector_valt_terug_op_landelijk(bronnen):
    with patch.object(arbeidsmarkt, "roa_sectoren", return_value=["Mbo4 - techniek en ict"]):
        uit = json.loads(get_roa_benchmark("Mbo4 - techniek en ict", regio="Midden-Utrecht"))

    assert uit["prognose_tot_2030"] == {"Mbo4 - techniek en ict": {_ITA: {"typering": "slecht"}}}
    assert uit["herkomst"]["prognose_tot_2030"] == "Nederland"


@pytest.mark.parametrize("regio", ["Atlantis", "Utrech", "Midden Utrecht"])
def test_roa_onbekende_regio_noemt_de_geldige_en_raadt_niet(bronnen, regio):
    uit = get_roa_benchmark(regio=regio)

    with pytest.raises(json.JSONDecodeError):
        json.loads(uit)
    assert "Midden-Utrecht" in uit and "provincie Utrecht" in uit


def test_roa_kent_de_mastersectoren(bronnen):
    """ROA noemt het niveau 'Master, doctor' maar de sectoren 'Master - …'; die vielen buiten de lijst."""
    assert "Master - techniek en ict" in arbeidsmarkt.roa_sectoren()

    uit = json.loads(get_roa_benchmark("Master - techniek en ict"))

    assert uit["schoolverlaters_sis_2024"] == {"Master - techniek en ict": {"werkloosheid": {"perc": 4}}}


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


# --- #449: geen dubbeltelling, geen niveau dat er niet is, uitsplitsing naar gemeente ---

_DEELKAART = {
    "TECHNIEK": ["Chauffeurs", "Programmeurs"],
    "ECONOMIE": ["Chauffeurs", "Accountants"],
    "Transport en logistiek": ["Chauffeurs"],
}
_DEELINDELING = {"TECHNIEK": "hbo/wo", "ECONOMIE": "hbo/wo", "Transport en logistiek": "mbo"}


@pytest.fixture
def gedeelde_clusters():
    uwv = pd.DataFrame(
        {
            "PEILDATUM": ["16-05-2023"] * 4,
            "PROVINCIE": ["Utrecht"] * 4,
            "GEMEENTE": ["Utrecht"] * 4,
            "BEROEPENCLUSTER": ["Chauffeurs", "Programmeurs", "Accountants", "Kappers"],
            "AANTAL": [2000, 500, 300, 100],
        }
    )
    with (
        patch.object(arbeidsmarkt, "_uwv", return_value=uwv),
        patch.dict(arbeidsmarkt.SECTOR_CLUSTER_MAP, _DEELKAART, clear=True),
        patch.dict(arbeidsmarkt.SECTOR_INDELING, _DEELINDELING, clear=True),
        patch("tools.arbeidsmarkt.scope_blokkade", return_value=None),
    ):
        yield


def test_uwv_cluster_in_twee_sectoren_telt_niet_dubbel(gedeelde_clusters):
    techniek = json.loads(get_uwv_vacatures("Utrecht", "TECHNIEK"))
    economie = json.loads(get_uwv_vacatures("Utrecht", "ECONOMIE"))

    # Chauffeurs (2000) horen bij TECHNIEK én ECONOMIE: elk de helft, niet elk 2000.
    assert techniek["vacatures_sector"] == 1000 + 500
    assert economie["vacatures_sector"] == 1000 + 300
    assert techniek["vacatures_sector"] + economie["vacatures_sector"] <= techniek["totaal_vacatures"]
    # De ruwe clustergetallen blijven staan; het resultaat zegt met wie een cluster gedeeld is en hoe er geteld is.
    assert techniek["clusters"] == {"Chauffeurs": 2000, "Programmeurs": 500}
    assert techniek["gedeelde_clusters"] == {"Chauffeurs": ["ECONOMIE"]}
    assert "naar rato" in techniek["telling_sector"]


def test_uwv_mbo_en_hbo_wo_zijn_aparte_indelingen(gedeelde_clusters):
    """Mbo- en hbo/wo-sectoren delen elk dezelfde vacatures in; daartussen wordt niet gewogen."""
    uit = json.loads(get_uwv_vacatures("Utrecht", "Transport en logistiek"))

    assert uit["vacatures_sector"] == 2000
    assert "gedeelde_clusters" not in uit


def test_uwv_sectoren_van_een_indeling_tellen_nooit_op_tot_meer_dan_het_totaal():
    """Met de echte mapping: per indeling samen hooguit het totaal, ook met oneven aantallen."""
    kaart = arbeidsmarkt.SECTOR_CLUSTER_MAP
    clusters = sorted({c for cs in kaart.values() for c in cs})
    uwv = pd.DataFrame(
        {
            "PEILDATUM": "16-05-2023",
            "PROVINCIE": "Utrecht",
            "GEMEENTE": "Utrecht",
            "BEROEPENCLUSTER": [*clusters, "Niet in de mapping"],
            "AANTAL": [7 + i % 5 for i in range(len(clusters))] + [11],
        }
    )
    with (
        patch.object(arbeidsmarkt, "_uwv", return_value=uwv),
        patch("tools.arbeidsmarkt.scope_blokkade", return_value=None),
    ):
        per_sector = {s: json.loads(get_uwv_vacatures("Utrecht", s)) for s in kaart}

    totaal = int(uwv["AANTAL"].sum())
    for indeling in set(arbeidsmarkt.SECTOR_INDELING.values()):
        som = sum(u["vacatures_sector"] for s, u in per_sector.items() if arbeidsmarkt.SECTOR_INDELING[s] == indeling)
        assert som <= totaal, indeling


def test_elke_sector_in_de_mapping_hoort_bij_precies_een_indeling():
    """Zonder indeling weegt een sector niet mee met de sectoren die hetzelfde cluster hebben."""
    ruw = json.loads(arbeidsmarkt.SECTOR_CLUSTER_PATH.read_text())
    toegewezen = [s for sectoren in ruw["_indelingen"].values() for s in sectoren]

    assert sorted(toegewezen) == sorted(arbeidsmarkt.SECTOR_CLUSTER_MAP)


@pytest.mark.parametrize("args", [("Utrecht",), ("Utrecht", "GEZONDHEIDSZORG")])
def test_uwv_zegt_dat_het_opleidingsniveau_onbekend_is(bronnen, args):
    """De niveaukolommen zijn bij vacatures leeg: chauffeursbanen zijn geen hbo-vraag."""
    with patch.dict(arbeidsmarkt.SECTOR_CLUSTER_MAP, {"GEZONDHEIDSZORG": ["Zorg en welzijn"]}, clear=True):
        uit = json.loads(get_uwv_vacatures(*args))

    assert uit["opleidingsniveau"].startswith("onbekend")


def test_uwv_per_gemeente(bronnen):
    uit = json.loads(get_uwv_vacatures("Utrecht", gemeente="utrecht"))

    assert uit["gemeente"] == "utrecht"
    assert uit["totaal_vacatures"] == 1000
    assert uit["clusters"] == {"Zorg en welzijn": 900, "ICT": 100}


@pytest.mark.parametrize("gemeente", ["Atlantis", "Arnhem"])
def test_uwv_onbekende_gemeente_noemt_de_gemeenten_van_de_provincie(bronnen, gemeente):
    uit = get_uwv_vacatures("Utrecht", gemeente=gemeente)

    assert "Amersfoort" in uit and "Utrecht" in uit
    assert "Arnhem" not in uit.replace(f"'{gemeente}'", "")


@pytest.mark.parametrize(
    ("tool", "args"),
    [(get_uwv_vacatures, ("Utrecht",)), (get_roa_benchmark, ()), (get_roa_benchmark, (None, "Utrecht"))],
)
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
