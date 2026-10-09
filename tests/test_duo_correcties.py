"""Correcties op DUO-kolombeschrijvingen die in de bron fout of leeg zijn (#451).

Een test per gecorrigeerde kolom, plus de naden: get_duo_data (column_definitions),
dataset_details (`_kolomdefinities`) en search_catalog. De correcties zijn op 2026-10-08
nagegaan tegen de data en de DUO-documentatie; het bewijs staat in tools/duo_correcties.py.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest
from riodata import duo as _duo

from tools import duo_correcties
from tools.catalog import _rio_duo, dataset_details, search_catalog
from tools.duo import column_definitions, get_duo_data

_HO = ["p01hoinges", "p02ho1ejrs", "p03hoinschr", "p04hogdipl"]
_INSTROOM_MBO = "instromende-mbo-studenten"


def _definitie(dataset: str, kolom: str) -> str:
    return column_definitions([kolom], dataset)[kolom]


# --- p04hogdipl: het behaalde ho-diploma, niet de vooropleiding ---


def test_diplomajaar_is_het_jaar_van_het_ho_diploma():
    definitie = _definitie("p04hogdipl", "DIPLOMAJAAR")

    assert "vooropleidingsdiploma is behaald" not in definitie
    assert "hoger-onderwijsdiploma" in definitie


def test_diplomajaar_zegt_dat_het_soort_jaar_niet_vaststaat():
    """CH-41 (#464): DIPLOMAJAAR 2023 werd live opnieuw als studiejaar 2023/24 gelezen."""
    definitie = _definitie("p04hogdipl", "DIPLOMAJAAR")

    assert "kalenderjaar of een studiejaar" in definitie
    assert "diplomajaar 2023" in definitie


def test_soort_diploma_is_het_behaalde_ho_diploma():
    definitie = _definitie("p04hogdipl", "SOORT_DIPLOMA")

    assert "Type vooropleidingsdiploma" not in definitie
    for waarde in ("hbo associate degree", "hbo bachelor", "hbo master", "wo bachelor", "wo master", "wo postmaster"):
        assert waarde in definitie


# --- hbo/wo: de plaats is de vestiging, niet de woonplaats ---


@pytest.mark.parametrize("dataset", _HO)
@pytest.mark.parametrize("kolom", ["PROVINCIENAAM", "GEMEENTENAAM", "GEMEENTENUMMER"])
def test_ho_plaatskolommen_zijn_de_vestiging(dataset, kolom):
    definitie = _definitie(dataset, kolom)

    assert "vestiging" in definitie
    assert "niet de woonplaats" in definitie


def test_elders_blijft_de_plaats_de_upstreamdefinitie():
    """Een vestigingscorrectie hoort bij de ho-bestanden, niet bij elke kolom met die naam."""
    assert (
        _definitie("adressen_mbo", "GEMEENTENAAM")
        == _duo.column_definitions(["GEMEENTENAAM"], "adressen_mbo")["GEMEENTENAAM"]
    )


# --- instromende mbo-studenten: totaal is geen instroom ---


def test_totaal_mbo_is_alle_ingeschrevenen_geen_instroom():
    definitie = _definitie(_INSTROOM_MBO, "TOTAAL MBO")

    assert "ingeschreven" in definitie
    assert "geen instroom" in definitie


def test_instroom_mbo_is_nieuw_in_het_mbo():
    definitie = _definitie(_INSTROOM_MBO, "INSTROOM MBO")

    assert "nieuw in het mbo" in definitie
    assert "J/N" in definitie  # het bestand 'met soorten instroom' heeft een indicator


def test_instroom_opleiding_is_nieuw_in_de_opleiding():
    definitie = _definitie(_INSTROOM_MBO, "INSTROOM OPLEIDING")

    assert "nieuw in de beroepsopleiding" in definitie
    assert "INSTROOM MBO" in definitie  # wie nieuw is in het mbo, is ook nieuw in de opleiding


# --- de overlay zelf ---


def test_een_correctie_gaat_voor_op_riodata():
    upstream = _duo.column_definitions(["DIPLOMAJAAR"], "p04hogdipl")["DIPLOMAJAAR"]

    assert _definitie("p04hogdipl", "DIPLOMAJAAR") != upstream


def test_alleen_kolommen_die_er_zijn():
    assert set(column_definitions(["DIPLOMAJAAR"], "p04hogdipl")) == {"DIPLOMAJAAR"}


@pytest.mark.parametrize("dataset", sorted(duo_correcties.KOLOMCORRECTIES))
def test_elke_correctie_hoort_bij_een_kolom_uit_de_catalogus(dataset):
    """Hernoemt DUO een kolom, dan valt een correctie stil weg; dit maakt dat zichtbaar."""
    record = next(e for e in _rio_duo() if e.get("_ckan_id") == dataset)
    kolommen = {k for per_bestand in record["_kolommen"].values() for k in per_bestand}

    assert set(duo_correcties.KOLOMCORRECTIES[dataset]) <= kolommen


def test_get_duo_data_geeft_de_correctie_door():
    df = pd.DataFrame({"DIPLOMAJAAR": [2024], "SOORT_DIPLOMA": ["hbo bachelor"], "AANTAL_GEDIPLOMEERDEN": [10]})
    with patch("tools.duo._duo.load", return_value=df):
        result = json.loads(get_duo_data("p04hogdipl", 0))

    kolom = next(k for k in result["kolommen"] if k["kolom"] == "SOORT_DIPLOMA")
    assert kolom["definitie"].startswith("Het behaalde hoger-onderwijsdiploma")


# --- catalogus: details en zoeken ---


def test_dataset_details_geeft_de_gecorrigeerde_kolomdefinities():
    defs = json.loads(dataset_details("p04hogdipl"))["_kolomdefinities"]

    assert "hoger-onderwijsdiploma" in defs["DIPLOMAJAAR"]
    assert "vestiging" in defs["PROVINCIENAAM"]


def test_dataset_details_vult_de_lege_mbo_kolommen():
    defs = json.loads(dataset_details(_INSTROOM_MBO))["_kolomdefinities"]

    assert {"TOTAAL MBO", "INSTROOM MBO", "INSTROOM OPLEIDING"} <= set(defs)


def test_dataset_details_zegt_dat_de_ho_plaats_geen_herkomst_is():
    details = json.loads(dataset_details("p01hoinges"))

    assert "vestiging" in details["niet_geschikt_voor"]


def test_zoeken_naar_woonplaats_ho_meldt_de_vestiging():
    hits = json.loads(search_catalog("woonplaats studenten hoger onderwijs"))
    ho = [h for h in hits if h.get("_ckan_id") in _HO]

    assert ho, "de ho-bestanden horen nog gevonden te worden, met de melding erbij"
    for hit in ho:
        assert "vestiging" in hit["niet_geschikt_voor"]
        assert not any("wonen" in v for v in hit.get("voorbeeldvragen", []))


def test_herkomstvoorbeeldvraag_wordt_een_vestigingsvraag():
    """'In welke provincie wonen de meeste ingeschrevenen?' maakte p01/p02 een treffer voor 'wonen'."""
    record = duo_correcties.catalogusrecord(
        {
            "_ckan_id": "p01hoinges",
            "voorbeeldvragen": ["Wat is de M/V-verhouding?", "In welke provincie wonen de meeste ingeschrevenen?"],
        }
    )

    assert record["voorbeeldvragen"] == [
        "Wat is de M/V-verhouding?",
        "In welke provincie liggen de vestigingen met de meeste ingeschrevenen?",
    ]


@pytest.mark.parametrize("dataset", _HO)
def test_geen_ho_voorbeeldvraag_noemt_wonen(dataset):
    """Tegen de gepinde catalogus: herformuleert riodata de vraag, dan valt dat hier op."""
    record = next(e for e in _rio_duo() if e.get("_ckan_id") == dataset)

    assert not any("wonen" in v or "woonplaats" in v for v in record.get("voorbeeldvragen", []))


def test_een_record_zonder_correctie_blijft_gelijk():
    record = {"_ckan_id": "mbo-studenten-per-instelling", "voorbeeldvragen": ["Waar wonen ze?"]}

    assert duo_correcties.catalogusrecord(record) is record
