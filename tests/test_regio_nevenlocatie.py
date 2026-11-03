"""Een regiovergelijking van mbo-instellingen mist wie alleen een nevenlocatie in de regio heeft (#744).

Het bewijs staat in DUO's eigen bestanden, hier als bevroren rijen (`scripts/duo_testfixtures.py`). Zone.college
(31JC) heeft zijn hoofdvestiging in Lochem; Graafschap College (24ZZ) in Doetinchem. Zone.college is dus geen
vestiging van het Graafschap College, maar `mbo_opleidingsaanbod` kent de plaats per onderwijslocatie en noemt
Zone.college met 22 opleidingen in Doetinchem. Studentaantallen en instellingsadressen bestaan alleen per BRIN, met
de plaats van de hoofdvestiging: wie de regio daarop kiest, laat Zone.college weg. De code kan die twee bestanden
niet koppelen (het aanbod kent geen BRIN, zie #728); wat ze wel doet is het model zeggen wat het adres is en waar de
locaties staan, en laten melden dat de aantallen per instelling zijn.
"""

import pytest

import data.instellingen as instellingen
from data.instellingen import get_adres_lookup
from prompts import SYSTEM_PROMPT, build_persona_block
from tools import instellingsprovincie
from tools.duo import column_definitions

ZONE = "31JC"
GRAAFSCHAP = "24ZZ"
DOETINCHEM = "Doetinchem"


@pytest.fixture
def aanbod(duo_fixtures):
    from riodata import duo

    return duo.load("mbo_opleidingsaanbod", 0)


def _aanbieders_in(aanbod, plaats: str) -> set[str]:
    rijen = aanbod[aanbod["PLAATSNAAM"].astype(str).str.upper() == plaats.upper()]
    return set(rijen["NAAM"].astype(str))


def test_op_het_adres_van_de_hoofdvestiging_valt_zone_college_buiten_doetinchem(duo_fixtures):
    adressen = get_adres_lookup()

    in_doetinchem = {code for code, adres in adressen.items() if adres["plaatsnaam"] == DOETINCHEM.upper()}

    assert adressen[ZONE]["plaatsnaam"] == "LOCHEM"
    assert GRAAFSCHAP in in_doetinchem
    assert ZONE not in in_doetinchem


def test_via_de_onderwijslocaties_staat_zone_college_wel_in_doetinchem(aanbod):
    zone = aanbod[(aanbod["NAAM"] == "Zone.college mbo") & (aanbod["PLAATSNAAM"] == DOETINCHEM)]

    assert "Zone.college mbo" in _aanbieders_in(aanbod, DOETINCHEM)
    assert len(zone) == 22
    assert zone["AANGEBODEN_OPLEIDINGCODE"].nunique() == 22


def test_het_aanbod_kent_geen_brin(aanbod):
    """Daarom koppelt de code het aanbod niet aan de studentaantallen: die sleutel hoort bij #728."""
    assert "INSTELLINGSCODE" not in aanbod.columns
    assert "BRIN" not in " ".join(aanbod.columns)


# --- Wat het model te lezen krijgt -------------------------------------------------------------------------------


def test_de_provinciekolom_zegt_dat_een_nevenlocatie_er_niet_onder_valt():
    definitie = column_definitions([instellingsprovincie.KOLOM], "mbo-studenten-per-instelling")[
        instellingsprovincie.KOLOM
    ]

    assert "nevenlocatie" in definitie
    assert "mbo_opleidingsaanbod" in definitie
    assert "niet per locatie" in definitie


def test_het_instellingsprofiel_van_een_mbo_instelling_wijst_naar_de_locaties(duo_fixtures):
    blok = build_persona_block({"instelling": "ROC Midden Nederland"})

    assert "hoofdvestiging" in blok
    assert "mbo_opleidingsaanbod" in blok
    assert "PLAATSNAAM" in blok
    assert "niet per locatie" in blok


@pytest.mark.parametrize("instelling", ["Hogeschool Utrecht", "Rijksuniversiteit Groningen"])
def test_hbo_en_wo_krijgen_de_mbo_regel_niet(duo_fixtures, instelling):
    blok = build_persona_block({"instelling": instelling})

    assert "mbo_opleidingsaanbod" not in blok


def test_zonder_regio_geen_locatieregel(duo_fixtures, monkeypatch):
    monkeypatch.setattr(instellingen, "_build_adres_lookup", lambda: {})

    blok = build_persona_block({"instelling": "ROC Midden Nederland"})

    assert "mbo_opleidingsaanbod" not in blok


def test_de_systeemprompt_kiest_de_regio_van_mbo_instellingen_via_de_locaties():
    assert "**Regio en nevenlocaties (mbo):**" in SYSTEM_PROMPT
    regel = next(r for r in SYSTEM_PROMPT.splitlines() if r.startswith("**Regio en nevenlocaties (mbo):**"))

    assert "mbo_opleidingsaanbod" in regel
    assert "PLAATSNAAM" in regel
    assert "niet per locatie" in regel
