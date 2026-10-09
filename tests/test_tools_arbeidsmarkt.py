"""Arbeidsmarkt-tools: echte bronwaarden, peildatum uit de data, dezelfde scopepoort (#441, #435).

CH-37: get_roa_benchmark gaf vaste, in de code geschreven waarden ("~80%") als ROA-cijfers door,
en beide tools liepen buiten de scopepoort. CH-23: ze haalden private functies uit
data/dashboard.py, terwijl dashboards overal uit staan. #449: get_uwv_vacatures telde clusters
die bij twee sectoren horen dubbel en zei niet dat UWV geen opleidingsniveau kent. #450:
get_roa_benchmark gooide de regionale prognoses weg en kende de mastersectoren niet. #460: met
een sector las het model onze clustertoewijzing en weging als werk van UWV.
"""

import ast
import json
import re
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

    assert uit["gewogen_aandeel"]["vacatures_sector"] == 900
    assert uit["uwv_broncijfer"]["clusters"] == {"Zorg en welzijn": 900}
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
    uit = json.loads(get_uwv_vacatures("Utrecht", "TECHNIEK"))
    techniek = uit["gewogen_aandeel"]
    economie = json.loads(get_uwv_vacatures("Utrecht", "ECONOMIE"))["gewogen_aandeel"]

    # Chauffeurs (2000) horen bij TECHNIEK én ECONOMIE: elk de helft, niet elk 2000.
    assert techniek["vacatures_sector"] == 1000 + 500
    assert economie["vacatures_sector"] == 1000 + 300
    assert techniek["vacatures_sector"] + economie["vacatures_sector"] <= uit["totaal_vacatures"]
    # De ruwe clustergetallen blijven staan; het resultaat zegt met wie een cluster gedeeld is en hoe er geteld is.
    assert uit["uwv_broncijfer"]["clusters"] == {"Chauffeurs": 2000, "Programmeurs": 500}
    assert techniek["gedeelde_clusters"] == {"Chauffeurs": ["ECONOMIE"]}
    assert "naar rato" in techniek["telling_sector"]


def test_uwv_mbo_en_hbo_wo_zijn_aparte_indelingen(gedeelde_clusters):
    """Mbo- en hbo/wo-sectoren delen elk dezelfde vacatures in; daartussen wordt niet gewogen."""
    uit = json.loads(get_uwv_vacatures("Utrecht", "Transport en logistiek"))["gewogen_aandeel"]

    assert uit["vacatures_sector"] == 2000
    assert "gedeelde_clusters" not in uit
    assert "naar rato" not in uit["telling_sector"]


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
        som = sum(
            u["gewogen_aandeel"]["vacatures_sector"]
            for s, u in per_sector.items()
            if arbeidsmarkt.SECTOR_INDELING[s] == indeling
        )
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


# --- #460: UWV-cijfer, onze clustertoewijzing en onze weging staan apart ---

_MANIFEST = {"herkomst": "LLM-classificatie, niet van UWV", "mapping_versie": "2026-08-17", "model": "claude-x"}
# Een ontkenning mag UWV noemen; elke andere vermelding schrijft de toewijzing of weging aan UWV toe.
_ONTKENNING = re.compile(r"niet van UWV|geen UWV-cijfer")


def _strings(blok) -> list[str]:
    if isinstance(blok, dict):
        return [s for k, v in blok.items() for s in (k, *_strings(v))]
    if isinstance(blok, list):
        return [s for v in blok for s in _strings(v)]
    return [blok] if isinstance(blok, str) else []


@pytest.fixture
def manifest():
    with patch.dict(arbeidsmarkt.SECTOR_MANIFEST, _MANIFEST, clear=True):
        yield


def test_uwv_sector_scheidt_broncijfer_classificatie_en_weging(gedeelde_clusters, manifest):
    uit = json.loads(get_uwv_vacatures("Utrecht", "TECHNIEK"))

    assert uit["uwv_broncijfer"]["clusters"] == {"Chauffeurs": 2000, "Programmeurs": 500}
    assert "ongewogen" in uit["uwv_broncijfer"]["toelichting"].lower()
    assert uit["lokale_classificatie"] == {
        "sector": "TECHNIEK",
        "clusters": ["Chauffeurs", "Programmeurs"],
        "toewijzing": uit["lokale_classificatie"]["toewijzing"],
        **_MANIFEST,
    }
    assert uit["gewogen_aandeel"]["vacatures_sector"] == 1500
    assert uit["gewogen_aandeel"]["gedeelde_clusters"] == {"Chauffeurs": ["ECONOMIE"]}
    assert "geen UWV-cijfer" in uit["gewogen_aandeel"]["telling_sector"]
    # Geen gewogen getal en geen sector meer op het hoogste niveau, naast de UWV-bron.
    assert not {"vacatures_sector", "sector", "clusters", "telling_sector", "gedeelde_clusters"} & set(uit)
    assert uit["totaal_vacatures"] == 2900


@pytest.mark.parametrize("sector", ["TECHNIEK", "Transport en logistiek"])
def test_uwv_sector_schrijft_toewijzing_en_weging_niet_aan_uwv_toe(gedeelde_clusters, sector):
    """'UWV deelt clusters toe' (#460): UWV staat alleen bij de ruwe aantallen, of in een ontkenning."""
    uit = json.loads(get_uwv_vacatures("Utrecht", sector))
    lokaal = _strings(uit["lokale_classificatie"]) + _strings(uit["gewogen_aandeel"])

    assert [s for s in lokaal if "UWV" in _ONTKENNING.sub("", s)] == []
    assert "LLM" in uit["lokale_classificatie"]["herkomst"]
    assert "niet van UWV" in uit["lokale_classificatie"]["herkomst"]
    assert "UWV" in uit["uwv_broncijfer"]["toelichting"]


def test_uwv_sector_zonder_manifest_noemt_versie_en_model_onbekend(gedeelde_clusters, tmp_path):
    bestand = tmp_path / "sector_cluster_mapping.json"
    bestand.write_text('{"TECHNIEK": ["Chauffeurs"]}')
    with patch.dict(arbeidsmarkt.SECTOR_MANIFEST, arbeidsmarkt.sector_mapping_manifest(bestand), clear=True):
        classificatie = json.loads(get_uwv_vacatures("Utrecht", "TECHNIEK"))["lokale_classificatie"]

    assert classificatie["mapping_versie"] == classificatie["model"] == "onbekend"
    assert "niet van UWV" in classificatie["herkomst"]


def test_uwv_sector_toont_de_grootste_clusters_in_beide_lagen(bronnen):
    clusters = [f"Cluster {i:02}" for i in range(20)]
    uwv = pd.DataFrame(
        {
            "PEILDATUM": "16-05-2023",
            "PROVINCIE": "Utrecht",
            "GEMEENTE": "Utrecht",
            "BEROEPENCLUSTER": clusters,
            "AANTAL": [100 - i for i in range(20)],
        }
    )
    with (
        patch.object(arbeidsmarkt, "_uwv", return_value=uwv),
        patch.dict(arbeidsmarkt.SECTOR_CLUSTER_MAP, {"TECHNIEK": clusters}, clear=True),
    ):
        uit = json.loads(get_uwv_vacatures("Utrecht", "TECHNIEK"))

    assert uit["lokale_classificatie"]["clusters"] == list(uit["uwv_broncijfer"]["clusters"]) == clusters[:15]
    assert "15 grootste van 20" in uit["uwv_broncijfer"]["clusters_getoond"]
    assert uit["gewogen_aandeel"]["vacatures_sector"] == sum(range(81, 101))


def test_uwv_sectorresultaat_houdt_zijn_meetwaarden(gedeelde_clusters):
    """De citaties lezen de geneste lagen: totaal, sectorgetal en clusters blijven meetwaarden."""
    from agent.meetwaarden import meetwaarden

    waarden = {(w.maat, max(w.cijfers)) for w in meetwaarden(get_uwv_vacatures("Utrecht", "TECHNIEK"))}

    assert waarden == {
        ("Vacatures", "2900"),
        ("Vacatures in de sector, lokaal gewogen", "1500"),
        ("Vacatures", "2000"),
        ("Vacatures", "500"),
    }


def test_uwv_zonder_sector_heeft_geen_classificatielagen(bronnen):
    uit = json.loads(get_uwv_vacatures("Utrecht"))

    assert uit["clusters"] == {"Zorg en welzijn": 900, "ICT": 300}
    assert not {"uwv_broncijfer", "lokale_classificatie", "gewogen_aandeel", "vacatures_sector"} & set(uit)


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
