"""Voorbeelden in een kolomdefinitie zijn geen gesloten lijst (#430, CH-24).

De DUO-glossary noemt bij ONDERDEEL "(bijv. TECHNIEK, ECONOMIE, GEZONDHEIDSZORG)".
Las het model dat als de toegestane waarden, dan zag het in de data andere waarden
en concludeerde het een "metadata-conflict". De code markeert voorbeelden in de
tooluitvoer; een gesloten lijst ("zoals gepubliceerd: A, B of C") blijft ongemoeid.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from tools.definitie import VOORBEELDEN, met_voorbeeldstatus, noemt_voorbeelden


@pytest.mark.parametrize(
    "tekst",
    [
        "Studierichting op hoofdniveau (bijv. TECHNIEK, ECONOMIE, GEZONDHEIDSZORG).",
        "Diploma, bijvoorbeeld HAVO of VWO.",
        "Diploma, bv. HAVO of VWO.",
        "Leerwegcode zoals gepubliceerd, o.a. BBL, BOLVT en EX.",
        "Leerweg, onder andere BBL en BOL.",
        "Sector, zoals TECHNIEK en ZORG.",
    ],
)
def test_voorbeeldwoorden_maken_er_voorbeelden_van(tekst):
    assert noemt_voorbeelden(tekst)


@pytest.mark.parametrize(
    "tekst",
    [
        "Actuele naam van de onderwijsinstelling zoals geregistreerd in de Basisregistratie Instellingen.",
        "Vorm waarin het cohort wordt gegeven, zoals gepubliceerd: KLASSIKAAL, COACHING of KLASSIKAAL_EN_ONLINE.",
        "Opleidingsvorm hoger onderwijs: VT = voltijd, DT = deeltijd, DU = duaal.",
        "Aantal studenten.",
    ],
)
def test_zonder_voorbeeldwoord_of_met_zoals_als_vergelijking_blijft_het_een_definitie(tekst):
    assert not noemt_voorbeelden(tekst)
    assert met_voorbeeldstatus(tekst) == tekst


def test_de_formulering_zegt_dat_het_geen_volledige_lijst_is():
    tekst = met_voorbeeldstatus("Studierichting (bijv. TECHNIEK).")
    assert tekst.startswith("Studierichting (bijv. TECHNIEK).")
    assert VOORBEELDEN in tekst
    assert "voorbeelden, geen volledige lijst" in VOORBEELDEN


# ── De tooluitvoer naar het model ────────────────────────────────────────────


def test_get_duo_data_markeert_voorbeelden_naast_de_echte_waarden():
    from tools.duo import get_duo_data

    df = pd.DataFrame({"ONDERDEEL": ["ONDERWIJS", "TECHNIEK", "LANDBOUW"], "AANTAL": [3, 4, 5]})
    with patch("tools.duo._duo.load", return_value=df):
        result = json.loads(get_duo_data("p02ho1ejrs", 0))

    kolom = next(k for k in result["kolommen"] if k["kolom"] == "ONDERDEEL")
    assert "bijv. TECHNIEK" in kolom["definitie"]
    assert VOORBEELDEN in kolom["definitie"]
    assert kolom["waarden"] == ["LANDBOUW", "ONDERWIJS", "TECHNIEK"]


def test_get_duo_data_laat_een_gesloten_lijst_ongemoeid():
    from tools.duo import get_duo_data

    df = pd.DataFrame({"OPLEIDINGSVORM": ["KLASSIKAAL", "COACHING"], "AANTAL": [3, 4]})
    with patch("tools.duo._duo.load", return_value=df):
        result = json.loads(get_duo_data("mbo_opleidingsaanbod", 0))

    kolom = next(k for k in result["kolommen"] if k["kolom"] == "OPLEIDINGSVORM")
    assert VOORBEELDEN not in kolom["definitie"]


def test_dataset_details_markeert_voorbeelden_in_kolomdefinities():
    from tools import catalog

    entry = {
        "bron": "duo",
        "_kolomdefinities": {
            "ONDERDEEL": "Studierichting op hoofdniveau (bijv. TECHNIEK, ECONOMIE, GEZONDHEIDSZORG).",
            "INSTELLINGSNAAM_ACTUEEL": "Actuele naam zoals geregistreerd in de BRIN.",
        },
    }
    defs = json.loads(catalog._build_details(entry, "p02ho1ejrs"))["_kolomdefinities"]

    assert VOORBEELDEN in defs["ONDERDEEL"]
    assert defs["INSTELLINGSNAAM_ACTUEEL"] == "Actuele naam zoals geregistreerd in de BRIN."


def test_cbs_kolomdefinitie_markeert_voorbeelden():
    from tools.cbs import _column_definition

    col_defs = {"Onderwijssoort": {"description": "Soort onderwijs, zoals hbo en wo."}}
    assert VOORBEELDEN in _column_definition("Onderwijssoort", col_defs)
