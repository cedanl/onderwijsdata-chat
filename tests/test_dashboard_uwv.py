"""Dashboardlaag: geen stille terugval op alle clusters (#229), geen DUO -1 als getal (#228)."""

import inspect
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
    result = dashboard.load_dashboard_mbo("Grafisch Lyceum")
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
    dashboard._roa_prognose.cache_clear()
    with patch.object(arbeidsmarkt, "_roa", return_value=rijen):
        assert dashboard._roa_prognose("mbo") == {"Mbo4": {"ITA toekomstige arbeidsmarktsituatie in 2030": "redelijk"}}
    dashboard._roa_prognose.cache_clear()
