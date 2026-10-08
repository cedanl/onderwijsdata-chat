"""Sector en regio van de profielinstelling komen uit de code, niet van het model (#448).

Het model kreeg alleen de instellingsnaam en koos zelf een provincie. De rijen hieronder
zijn de echte DUO-rijen van de drie testinstellingen (gecontroleerd tegen p01hoinges,
mbo-studenten-per-instelling, adressen_ho en adressen_mbo op 2026-10-08); de tests laden
ze zonder netwerk.
"""

import pandas as pd
import pytest

import data.instellingen as instellingen
from agent.models import build_system
from data.instellingen import instellingsprofiel
from prompts import build_persona_block

_ADRES_KOLOMMEN = ["INSTELLINGSCODE", "INSTELLINGSNAAM", "PLAATSNAAM", "PROVINCIE", "RPA-GEBIED NAAM"]

_DUO = {
    ("p01hoinges", 0): pd.DataFrame(
        {"INSTELLINGSCODE_ACTUEEL": ["25DW"], "INSTELLINGSNAAM_ACTUEEL": ["Hogeschool Utrecht"]}
    ),
    ("p01hoinges", 1): pd.DataFrame(
        {"INSTELLINGSCODE_ACTUEEL": ["21PC"], "INSTELLINGSNAAM_ACTUEEL": ["Rijksuniversiteit Groningen"]}
    ),
    ("mbo-studenten-per-instelling", 0): pd.DataFrame(
        {"INSTELLINGSCODE": ["25LH"], "INSTELLINGSNAAM": ["ROC Midden Nederland"]}
    ),
    ("adressen_ho", 1): pd.DataFrame(
        [
            ["25DW", "Hogeschool Utrecht", "UTRECHT", "Utrecht", "Utrecht-Midden"],
            ["21PC", "Rijksuniversiteit Groningen", "GRONINGEN", "Groningen", "Centraal-Groningen"],
        ],
        columns=_ADRES_KOLOMMEN,
    ),
    ("adressen_mbo", 1): pd.DataFrame(
        [["25LH", "Stichting ROC Midden Nederland", "UTRECHT", "Utrecht", "Utrecht-Midden"]],
        columns=_ADRES_KOLOMMEN,
    ),
}


def _leeg_cache():
    instellingen._cache = None
    instellingen._alias_lookup = None
    instellingen._ADRES_CACHE = None


@pytest.fixture(autouse=True)
def duo_zonder_netwerk(monkeypatch):
    monkeypatch.setattr(instellingen.duo, "load", lambda dataset, resource: _DUO[(dataset, resource)].copy())
    _leeg_cache()
    yield
    _leeg_cache()


@pytest.mark.parametrize(
    ("naam", "sector", "provincie", "arbeidsmarktregio", "code"),
    [
        ("ROC Midden Nederland", "mbo", "Utrecht", "Utrecht-Midden", "25LH"),
        ("Hogeschool Utrecht", "hbo", "Utrecht", "Utrecht-Midden", "25DW"),
        ("Rijksuniversiteit Groningen", "wo", "Groningen", "Centraal-Groningen", "21PC"),
    ],
)
def test_sector_provincie_en_arbeidsmarktregio(naam, sector, provincie, arbeidsmarktregio, code):
    assert instellingsprofiel(naam) == {
        "naam": naam,
        "sector": sector,
        "provincie": provincie,
        "arbeidsmarktregio": arbeidsmarktregio,
        "instellingscode": code,
    }


@pytest.mark.parametrize("invoer", ["ROC MN", "rocmn", "roc midden nederland", "  ROC Midden Nederland "])
def test_alias_en_hoofdletters_geven_dezelfde_instelling(invoer):
    profiel = instellingsprofiel(invoer)
    assert profiel is not None
    assert profiel["naam"] == "ROC Midden Nederland"


@pytest.mark.parametrize("invoer", ["Onbekende Hogeschool", "Hogeschool", "Utrecht", "", "   "])
def test_onbekend_is_onbekend_en_geen_gok(invoer):
    # Ook een deel van een naam ("Hogeschool", "Utrecht") geeft geen instelling: geen fuzzy match.
    assert instellingsprofiel(invoer) is None


def test_zonder_adres_blijft_de_regio_onbekend(monkeypatch):
    adressen = _DUO[("adressen_ho", 1)]
    monkeypatch.setitem(_DUO, ("adressen_ho", 1), adressen[adressen["INSTELLINGSCODE"] != "21PC"])
    profiel = instellingsprofiel("RUG")
    assert profiel is not None
    assert profiel["sector"] == "wo"
    assert profiel["provincie"] is None
    assert profiel["arbeidsmarktregio"] is None


# ─── In de modelcontext ──────────────────────────────────────────────────────


def test_prompt_noemt_sector_en_regio_naast_de_instelling():
    blok = build_persona_block({"instelling": "Hogeschool Utrecht"})
    assert "- Instelling: **Hogeschool Utrecht**" in blok
    assert "sector **hbo**" in blok
    assert "instellingscode 25DW" in blok
    assert "provincie **Utrecht**" in blok
    assert "arbeidsmarktregio **Utrecht-Midden**" in blok
    assert "'mijn regio'" in blok
    assert "noem dat niveau" in blok


def test_systeembericht_draagt_de_regio_via_een_alias():
    (system,) = build_system({"instelling": "HU"})
    assert "arbeidsmarktregio **Utrecht-Midden**" in system["content"][0]["text"]


@pytest.mark.parametrize(("instelling", "ho"), [("Hogeschool Utrecht", True), ("RUG", True), ("ROC MN", False)])
def test_vestigingskolommen_alleen_bij_hbo_en_wo(instelling, ho):
    blok = build_persona_block({"instelling": instelling})
    assert ("`PROVINCIENAAM`/`GEMEENTENAAM`" in blok) is ho


def test_onbekende_instelling_krijgt_geen_regioregel():
    blok = build_persona_block({"instelling": "Onbekende Hogeschool"})
    assert "- Instelling: **Onbekende Hogeschool**" in blok
    assert "provincie" not in blok
    assert "arbeidsmarktregio" not in blok
    assert "sector" not in blok


def test_zonder_adres_geen_regio_wel_sector(monkeypatch):
    adressen = _DUO[("adressen_ho", 1)]
    monkeypatch.setitem(_DUO, ("adressen_ho", 1), adressen[adressen["INSTELLINGSCODE"] != "21PC"])
    blok = build_persona_block({"instelling": "Rijksuniversiteit Groningen"})
    assert "sector **wo**" in blok
    assert "provincie" not in blok
    assert "'mijn regio'" not in blok
