"""Dashboardlaag: geen stille terugval op alle clusters (#229), geen DUO -1 als getal (#228)."""

import inspect
import json
from unittest.mock import patch

import pandas as pd
import pytest

import data.dashboard as dashboard
from data import arbeidsmarkt

_CLUSTERS = {"Zorg en welzijn": 900, "ICT": 300, "Techniek": 200}


def _met_clusters(sectoren):
    with (
        patch.object(arbeidsmarkt, "uwv_stand", return_value=arbeidsmarkt.UwvStand(1400, "2023-05-16", _CLUSTERS)),
        patch.object(
            arbeidsmarkt,
            "SECTOR_CLUSTER_MAP",
            {"GEZONDHEIDSZORG": ["Zorg en welzijn"], "ONBEKEND": ["Bestaat niet"]},
        ),
    ):
        return dashboard._uwv_clusters_voor_sectoren("Utrecht", sectoren)


def test_sector_met_clustermatch_geeft_alleen_die_clusters():
    assert _met_clusters(("GEZONDHEIDSZORG",)) == {"Zorg en welzijn": 900}


def test_sector_zonder_clustermatch_geeft_geen_clusters():
    # Met alle clusters als terugval kreeg elke sector vacature-aandeel 0: "overaanbod".
    assert _met_clusters(("ONBEKEND",)) == {}


# --- #455: het dashboard telt een gedeeld cluster naar rato, net als de chat ---

_GEDEELD = {"Chauffeurs": 2000, "Programmeurs": 500, "Accountants": 300}
_DEELKAART = {"TECHNIEK": ["Chauffeurs", "Programmeurs"], "ECONOMIE": ["Chauffeurs", "Accountants"]}
_GPS = {"TECHNIEK": 50, "ECONOMIE": 50}


@pytest.fixture
def gedeelde_clusters():
    with (
        patch.object(arbeidsmarkt, "uwv_stand", return_value=arbeidsmarkt.UwvStand(2800, "2023-05-16", _GEDEELD)),
        patch.dict(arbeidsmarkt.SECTOR_CLUSTER_MAP, _DEELKAART, clear=True),
        patch.dict(arbeidsmarkt.SECTOR_INDELING, {"TECHNIEK": "hbo/wo", "ECONOMIE": "hbo/wo"}, clear=True),
    ):
        yield


def test_vacatures_per_sector_telt_een_gedeeld_cluster_naar_rato(gedeelde_clusters):
    per_sector = arbeidsmarkt.vacatures_per_sector("Utrecht", ("TECHNIEK", "ECONOMIE"))

    # Chauffeurs (2000) horen bij beide: elk de helft. Ongewogen was het 2500 en 2300 van 2800.
    assert per_sector == {"TECHNIEK": 1500, "ECONOMIE": 1300}
    assert sum(per_sector.values()) <= 2800


def test_vacatures_per_sector_zonder_uwv_rijen_is_leeg(gedeelde_clusters):
    with patch.object(arbeidsmarkt, "uwv_stand", return_value=None):
        assert arbeidsmarkt.vacatures_per_sector("Atlantis", ("TECHNIEK",)) == {}


def test_dashboard_vacatures_per_sector_zonder_uwv_is_leeg(gedeelde_clusters):
    with patch.object(arbeidsmarkt, "uwv_stand", side_effect=RuntimeError("UWV onbereikbaar")):
        assert dashboard._uwv_vacatures_per_sector("Utrecht", ("TECHNIEK",)) == {}


def test_match_scores_met_gewogen_vacatures():
    # Met de ongewogen 2500 en 2300 van 2800 kregen beide sectoren "schaarste".
    scores = dashboard._match_scores(_GPS, {"TECHNIEK": 1500, "ECONOMIE": 1300}, _DEELKAART)

    assert scores == {"TECHNIEK": "evenwicht", "ECONOMIE": "evenwicht"}


def test_match_scores_schaarste_en_overaanbod():
    scores = dashboard._match_scores({"TECHNIEK": 320, "ECONOMIE": 80}, {"TECHNIEK": 200, "ECONOMIE": 800}, _DEELKAART)

    assert scores == {"TECHNIEK": "overaanbod", "ECONOMIE": "schaarste"}
    assert dashboard._MATCH_DREMPEL == 1.2


def test_match_scores_sector_zonder_clusters_is_none():
    scm = {"TECHNIEK": ["Programmeurs"], "ONDERWIJS": []}

    scores = dashboard._match_scores({"TECHNIEK": 50, "ONDERWIJS": 50}, {"TECHNIEK": 500, "ONDERWIJS": 0}, scm)

    assert scores == {"TECHNIEK": "schaarste", "ONDERWIJS": None}


@pytest.mark.parametrize("vacatures", [{}, {"TECHNIEK": 0, "ECONOMIE": 0}])
def test_match_scores_zonder_vacatures_is_alles_none(vacatures):
    assert dashboard._match_scores(_GPS, vacatures, _DEELKAART) == {"TECHNIEK": None, "ECONOMIE": None}
    assert dashboard._match_verhoudingen(_GPS, vacatures, _DEELKAART) == {"TECHNIEK": None, "ECONOMIE": None}


def test_match_verhouding_is_vacature_aandeel_gedeeld_door_diploma_aandeel():
    # #949: de lengte van de staaf. TECHNIEK 0,2 / 0,76 = 0,26 (overaanbod, onder 1 / 1,2); ECONOMIE 0,8 / 0,19 = 4,2
    # (schaarste, boven 1,2); ONDERWIJS heeft geen clusters en dus geen verhouding, net als geen label.
    gps = {"TECHNIEK": 320, "ECONOMIE": 80, "ONDERWIJS": 20}
    vacatures = {"TECHNIEK": 200, "ECONOMIE": 800}
    scm = {**_DEELKAART, "ONDERWIJS": []}

    verhouding = dashboard._match_verhoudingen(gps, vacatures, scm)
    scores = dashboard._match_scores(gps, vacatures, scm)

    assert verhouding == {"TECHNIEK": 0.26, "ECONOMIE": 4.2, "ONDERWIJS": None}
    assert scores == {"TECHNIEK": "overaanbod", "ECONOMIE": "schaarste", "ONDERWIJS": None}
    drempel = dashboard._MATCH_DREMPEL
    assert (techniek := verhouding["TECHNIEK"]) is not None and techniek < 1 / drempel
    assert (economie := verhouding["ECONOMIE"]) is not None and economie > drempel


def test_match_verhouding_zonder_gediplomeerden_in_een_sector_is_none():
    verhouding = dashboard._match_verhoudingen(
        {"TECHNIEK": 0, "ECONOMIE": 40}, {"TECHNIEK": 5, "ECONOMIE": 5}, _DEELKAART
    )

    assert verhouding == {"TECHNIEK": None, "ECONOMIE": 0.5}


# ─── #952: een kleine sector krijgt geen verhouding ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("n", "met_verhouding"), [(29, False), (30, True)])
def test_onder_de_drempel_geen_label_en_geen_verhouding_maar_een_reden(n, met_verhouding):
    # Tilburg University, Techniek: 52,15 bij 63 gediplomeerden; BUas 7,73 bij 13. Eén diploma meer of minder
    # verschoof de verhouding met tientallen procenten. De drempel geldt voor het gemiddelde per jaar.
    assert dashboard._MATCH_MIN_GEDIPLOMEERDEN == 30
    gps = {"TECHNIEK": n, "ECONOMIE": 600}
    vacatures = {"TECHNIEK": 900, "ECONOMIE": 100}

    verhouding = dashboard._match_verhoudingen(gps, vacatures, _DEELKAART)
    scores = dashboard._match_scores(gps, vacatures, _DEELKAART)
    weggelaten = dashboard._match_weggelaten(gps, vacatures, _DEELKAART)

    if met_verhouding:
        assert verhouding["TECHNIEK"] == round(0.9 / (n / (n + 600)), 2)
        assert scores["TECHNIEK"] == "schaarste"
        assert "TECHNIEK" not in weggelaten
    else:
        assert verhouding["TECHNIEK"] is None and scores["TECHNIEK"] is None
        assert weggelaten == {"TECHNIEK": dashboard._MATCH_TE_WEINIG}
        assert "30" in dashboard._MATCH_TE_WEINIG
    # De kleine sector telt mee in de totalen: de verhouding van de andere hangt niet van de drempel af.
    assert verhouding["ECONOMIE"] == round(0.1 / (600 / (n + 600)), 2)


def test_elke_sector_zonder_label_heeft_een_reden():
    gps = {"TECHNIEK": 100, "ECONOMIE": 10, "ONDERWIJS": 100}
    scm = {**_DEELKAART, "ONDERWIJS": []}

    assert dashboard._match_weggelaten(gps, {"TECHNIEK": 5, "ECONOMIE": 5}, scm) == {
        "ECONOMIE": dashboard._MATCH_TE_WEINIG,
        "ONDERWIJS": dashboard._MATCH_GEEN_CLUSTERS,
    }
    assert dashboard._match_weggelaten(gps, {}, scm) == dict.fromkeys(gps, dashboard._MATCH_GEEN_VACATURES)
    scores = dashboard._match_scores(gps, {"TECHNIEK": 5, "ECONOMIE": 5}, scm)
    assert {s for s, label in scores.items() if label is None} == {"ECONOMIE", "ONDERWIJS"}


def test_arbeidsmarktmatch_geeft_de_gewogen_telling_per_sector(gedeelde_clusters):
    gevonden = {
        "type": "ho",
        "provincie": "Utrecht",
        "arbeidsmarktregio": "Midden-Utrecht",
        "laatste_jaar": 2024,
        "gediplomeerden_per_sector": _GPS,
    }
    with (
        patch.object(dashboard, "resolve_alias", side_effect=lambda naam: naam),
        patch.object(dashboard, "_arbeidsmarktmatch_ho", return_value=gevonden),
        patch.object(dashboard, "_roa_schoolverlaters", return_value={}),
    ):
        uit = dashboard.load_dashboard_arbeidsmarktmatch("Hogeschool Utrecht")

    assert uit["vacatures_per_sector"] == {"TECHNIEK": 1500, "ECONOMIE": 1300}
    assert uit["match_score"] == {"TECHNIEK": "evenwicht", "ECONOMIE": "evenwicht"}
    # Additief: de ongewogen clusters en de mapping blijven in het antwoord.
    assert uit["vacatures_per_cluster"] == _GEDEELD
    assert uit["sector_cluster_mapping"] == _DEELKAART


# --- #228: het dashboard telt DUO -1 niet als getal mee, net als de chat ---


@pytest.fixture
def mbo_met_sentinels():
    ruw = pd.DataFrame(
        [
            {
                "JAAR": 2024,
                "INSTELLINGSNAAM": "Grafisch Lyceum",
                "INSTELLINGSCODE": "1",
                "BBL": 300,
                "BOLDT": -1,
                "BOLVT": 2079,
                "EX": -1,
            },
            {
                "JAAR": 2025,
                "INSTELLINGSNAAM": "Grafisch Lyceum",
                "INSTELLINGSCODE": "1",
                "BBL": 310,
                "BOLDT": 0,
                "BOLVT": 2100,
                "EX": 0,
            },
        ]
    )
    _leeg_laadcaches()
    with patch.object(dashboard.duo, "load", return_value=ruw):
        yield
    # Anders houdt een gecachte loader de nepdata vast voor de tests die echte data laden.
    _leeg_laadcaches()


def _leeg_laadcaches():
    for functie in vars(dashboard).values():
        if hasattr(functie, "cache_clear"):
            functie.cache_clear()


def test_mbo_dashboard_sluit_minus_een_uit(mbo_met_sentinels):
    # Audit ronde 2, D1: Grafisch Lyceum Utrecht 2024 toonde 2377 (= 2379 − 2).
    # De lading van het mbo-bestand en de reeks van het regiodashboard; dit nepbestand is alleen mbo, dus niet de hele lader.
    df = dashboard._load_mbo_studenten()
    result = dashboard._mbo_kern(df[df["INSTELLINGSNAAM"] == "Grafisch Lyceum"])
    assert result["ingeschrevenen"] == {2024: 2379, 2025: 2410}


def test_dashboard_laadt_duo_alleen_via_de_maskerende_helper():
    # Elke nieuwe duo.load in het dashboard zou het -1-gat opnieuw openen.
    bron = inspect.getsource(dashboard)
    assert bron.count("duo.load(") == 1, "laad DUO-data in data/dashboard.py via _duo_load"


# --- #313: de sector-clustermapping draagt haar peildatum ---


def test_mapping_bestand_heeft_een_manifest():
    import json
    from datetime import date
    from pathlib import Path

    ruw = json.loads((Path(arbeidsmarkt.__file__).parent / "sector_cluster_mapping.json").read_text())
    manifest = ruw["_manifest"]
    date.fromisoformat(manifest["bijgewerkt"])
    assert "UWV" in manifest["bron"]


def test_manifest_is_geen_sector(tmp_path):
    bestand = tmp_path / "sector_cluster_mapping.json"
    bestand.write_text('{"_manifest": {"bijgewerkt": "2026-08-17"}, "TECHNIEK": ["ICT"]}')
    assert arbeidsmarkt.load_sector_cluster_map(bestand) == {"TECHNIEK": ["ICT"]}


# --- #460: de mapping zegt dat ze van een taalmodel komt, niet van UWV ---


def test_mapping_bestand_zegt_dat_de_indeling_niet_van_uwv_is():
    ruw = json.loads(arbeidsmarkt.SECTOR_CLUSTER_PATH.read_text())

    assert ruw["_manifest"]["herkomst"] == arbeidsmarkt.MAPPING_HERKOMST
    assert "LLM" in arbeidsmarkt.MAPPING_HERKOMST and "niet van UWV" in arbeidsmarkt.MAPPING_HERKOMST
    assert ruw["_manifest"]["model"]


def test_sector_mapping_manifest_geeft_herkomst_versie_en_model(tmp_path):
    bestand = tmp_path / "sector_cluster_mapping.json"
    manifest = {"bijgewerkt": "2026-08-17", "herkomst": "LLM-classificatie, niet van UWV", "model": "claude-x"}
    bestand.write_text(json.dumps({"_manifest": manifest, "TECHNIEK": ["ICT"]}))

    assert arbeidsmarkt.sector_mapping_manifest(bestand) == {
        "herkomst": "LLM-classificatie, niet van UWV",
        "mapping_versie": "2026-08-17",
        "model": "claude-x",
    }


def test_refresh_script_schrijft_herkomst_en_model_in_het_manifest(tmp_path):
    from core.config import MODEL
    from scripts.refresh_sector_mapping import manifest

    geschreven = manifest(["prompt"])
    bestand = tmp_path / "sector_cluster_mapping.json"
    bestand.write_text(json.dumps({"_manifest": geschreven, "TECHNIEK": ["ICT"]}))

    assert arbeidsmarkt.sector_mapping_manifest(bestand) == {
        "herkomst": arbeidsmarkt.MAPPING_HERKOMST,
        "mapping_versie": geschreven["bijgewerkt"],
        "model": MODEL,
    }


@pytest.mark.parametrize("inhoud", ['{"TECHNIEK": ["ICT"]}', '{"_manifest": {}}', '{"_manifest": "kapot"}', "{kapot"])
def test_sector_mapping_manifest_zonder_velden_is_onbekend(tmp_path, inhoud):
    """Een ontbrekend veld is geen exceptie; de herkomst blijft dan wat het refresh-script schrijft."""
    bestand = tmp_path / "sector_cluster_mapping.json"
    bestand.write_text(inhoud)

    assert arbeidsmarkt.sector_mapping_manifest(bestand) == {
        "herkomst": arbeidsmarkt.MAPPING_HERKOMST,
        "mapping_versie": "onbekend",
        "model": "onbekend",
    }


def test_roa_prognose_in_het_dashboard_is_landelijk():
    """Per niveau staan er 48 regio's; zonder filter won de typering van de laatst gelezen regio (#441)."""
    rijen = pd.DataFrame(
        [
            {
                "regionaam": r,
                "thema": arbeidsmarkt._ROA_PROGNOSE,
                "aggregatieniveau": arbeidsmarkt._ROA_NIVEAU,
                "detailniveau": "Mbo4",
                "onderwerp": "ITA toekomstige arbeidsmarktsituatie in 2030",
                "perc": None,
                "aantal": None,
                "typering": t,
                "versie": "v1",
            }
            for r, t in (("Nederland", "redelijk"), ("Groningen", "slecht"))
        ]
    )
    with patch.object(arbeidsmarkt, "_roa", return_value=rijen):
        assert dashboard._roa_prognose("mbo") == {"Mbo4": {"ITA toekomstige arbeidsmarktsituatie in 2030": "redelijk"}}


def test_roa_prognose_geeft_de_baanopeningen_en_de_instroom_als_aantal():
    # #951: ROA geeft de baanopeningen en de instroom van schoolverlaters als aantal, zonder typering; het dashboard
    # las alleen typeringen en toonde die twee overal als "—".
    def rij(onderwerp, aantal=None, typering=None):
        return {
            "regionaam": "Nederland",
            "thema": arbeidsmarkt._ROA_PROGNOSE,
            "aggregatieniveau": arbeidsmarkt._ROA_NIVEAU,
            "detailniveau": "Mbo4",
            "onderwerp": onderwerp,
            "perc": None,
            "aantal": aantal,
            "typering": typering,
            "versie": "v1",
        }

    rijen = pd.DataFrame(
        [
            rij("ITA toekomstige arbeidsmarktsituatie in 2030", typering="redelijk"),
            rij("verwachte baanopeningen tot 2030", aantal=325800.0),
            rij("verwachte instroom van schoolverlaters tot 2030", aantal=358700.0),
        ]
    )
    with patch.object(arbeidsmarkt, "_roa", return_value=rijen):
        assert dashboard._roa_prognose("mbo") == {
            "Mbo4": {
                "ITA toekomstige arbeidsmarktsituatie in 2030": "redelijk",
                "verwachte baanopeningen tot 2030": 325800,
                "verwachte instroom van schoolverlaters tot 2030": 358700,
            }
        }
