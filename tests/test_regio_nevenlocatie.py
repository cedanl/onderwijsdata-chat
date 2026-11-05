"""Een regiovergelijking van mbo-instellingen mist wie alleen een nevenlocatie in de regio heeft (#744).

Het bewijs staat in DUO's eigen bestanden, hier als bevroren rijen (`scripts/duo_testfixtures.py`). Zone.college
(31JC) heeft zijn hoofdvestiging in Lochem; Graafschap College (24ZZ) in Doetinchem. Zone.college is dus geen
vestiging van het Graafschap College, maar `mbo_opleidingsaanbod` kent de plaats per onderwijslocatie en noemt
Zone.college met 22 opleidingen in Doetinchem. Studentaantallen en instellingsadressen bestaan alleen per BRIN, met
de plaats van de hoofdvestiging: wie de regio daarop kiest, laat Zone.college weg. Het aanbod kent geen BRIN, wel de
aanbieder; RIO koppelt die aan de instelling, en een filter op de regio neemt zo ook de instellingen met een locatie
daar mee (`tools/regiolocaties.py`, `tests/test_regiolocaties.py`). Hier: het bewijs, en wat het model te lezen krijgt.
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


def test_het_aanbod_kent_geen_brin_maar_wel_de_aanbieder(aanbod):
    """Daarom loopt de koppeling aan de studentaantallen via de aanbieders per instelling in RIO."""
    assert "INSTELLINGSCODE" not in aanbod.columns
    assert "BRIN" not in " ".join(aanbod.columns)
    assert set(aanbod.loc[aanbod["NAAM"] == "Zone.college mbo", "ONDERWIJSAANBIEDERID"]) == {"100A932"}


# --- Wat het model te lezen krijgt -------------------------------------------------------------------------------


def test_de_provinciekolom_zegt_dat_een_nevenlocatie_er_niet_onder_valt():
    definitie = column_definitions([instellingsprovincie.KOLOM], "mbo-studenten-per-instelling")[
        instellingsprovincie.KOLOM
    ]

    assert "hoofdvestiging" in definitie
    assert "onderwijslocatie in dat gebied" in definitie
    assert "niet per locatie" in definitie


def test_het_instellingsprofiel_van_een_mbo_instelling_zegt_wat_de_app_doet(duo_fixtures):
    blok = build_persona_block({"instelling": "ROC Midden Nederland"})

    assert "hoofdvestiging" in blok
    assert "onderwijslocatie in dat gebied" in blok
    assert "vaste regel" in blok


@pytest.mark.parametrize("instelling", ["Hogeschool Utrecht", "Rijksuniversiteit Groningen"])
def test_hbo_en_wo_krijgen_de_mbo_regel_niet(duo_fixtures, instelling):
    blok = build_persona_block({"instelling": instelling})

    assert "onderwijslocatie" not in blok


def test_zonder_regio_geen_locatieregel(duo_fixtures, monkeypatch):
    monkeypatch.setattr(instellingen, "_build_adres_lookup", lambda: ({}, []))

    blok = build_persona_block({"instelling": "ROC Midden Nederland"})

    assert "onderwijslocatie" not in blok


def test_de_systeemprompt_laat_de_regiokeuze_aan_de_code():
    assert "**Regio en nevenlocaties (mbo):**" in SYSTEM_PROMPT
    regel = next(r for r in SYSTEM_PROMPT.splitlines() if r.startswith("**Regio en nevenlocaties (mbo):**"))

    assert "`PLAATSNAAM INSTELLING`" in regel
    assert "`PROVINCIE INSTELLING`" in regel
    assert "vaste regel" in regel
    assert "mbo_opleidingsaanbod" not in regel
