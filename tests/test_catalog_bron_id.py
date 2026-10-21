"""Eén bron-ID en drie statussen (#356): genamespaced ID's wijzen naar het catalogusrecord; zoekhits en details zeggen
wat de chat ermee kan. Met de echte, gepinde catalogus waar het om spelling gaat; met nep-records waar het om status gaat."""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from tests.zoekuitkomst import treffers
from tools import catalog
from tools.canoniek import zonder_bronprefix
from tools.catalog import bron_id, dataset_details, scope_blokkade, search_catalog, status
from tools.duo import get_duo_data

# --- het ID ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spelling", "verwacht"),
    [
        ("duo:p01hoinges", "p01hoinges"),
        ("DUO/P01HOINGES", "p01hoinges"),
        (" duo: p01hoinges ", "p01hoinges"),
        ("rio:erkenningen", "erkenningen"),
        ("cbs:85423NED", "85423NED"),
        ("cbs_85423ned", "85423NED"),
        ("p01hoinges", "p01hoinges"),
        ("duo:bestaat-niet", "bestaat-niet"),
        ("x:p01hoinges", "x:p01hoinges"),
    ],
)
def test_bron_id_brengt_elke_spelling_terug_tot_de_catalogusspelling(spelling, verwacht):
    assert bron_id(spelling) == verwacht


def test_zonder_bronprefix_laat_een_duo_slug_met_duo_erin_met_rust():
    assert zonder_bronprefix("duo_adressen") == "duo_adressen"
    assert zonder_bronprefix("duo-adressen") == "duo-adressen"
    assert zonder_bronprefix("cbs_85423ned") == "85423ned"


def test_details_en_scopegrens_zien_door_het_voorvoegsel_heen():
    assert dataset_details("duo:p01hoinges") == dataset_details("p01hoinges")
    assert "niet gevonden" not in dataset_details("DUO/P01HOINGES")
    assert dataset_details("rio:aangeboden-opleidingen") == dataset_details("aangeboden-opleidingen")
    assert scope_blokkade("duo:p01hoinges") is None and scope_blokkade("rio:aangeboden-opleidingen") is None
    assert "staat niet in de catalogus" in (scope_blokkade("duo:bestaat-niet") or "")


def test_get_duo_data_laadt_onder_het_kale_id():
    df = pd.DataFrame({"STUDIEJAAR": [2024], "INSTELLINGSCODE_ACTUEEL": ["25DW"], "AANTAL_INGESCHREVENEN": [1]})
    with patch("tools.duo._duo.load", return_value=df):
        uit = json.loads(get_duo_data("DUO:p01hoinges", 3))
    assert uit["data_key"] == "duo:p01hoinges:3"


# --- de status --------------------------------------------------------------------------------------

_TABEL = {"naam": "data", "format": "CSV"}
_PDF = {"naam": "changelog", "format": "PDF"}


@pytest.mark.parametrize(
    ("entry", "verwacht"),
    [
        ({"_cbs_id": "85423NED"}, "opvraagbaar"),
        ({"leverancier": "DUO", "_ckan_id": "x", "_resources": [_TABEL, _PDF]}, "opvraagbaar"),
        ({"leverancier": "DUO", "_ckan_id": "x", "_resources": [_PDF]}, "alleen_documentatie"),
        ({"leverancier": "RIO", "_rio_resource": "erkenningen"}, "opvraagbaar"),
        ({"leverancier": "ROA", "_roa_id": "ais2030"}, "via_tool"),
        ({"leverancier": "UWV", "_ckan_id": "uwv-open-match-data"}, "via_tool"),
        ({"leverancier": "ROA", "_roa_id": "ais2028"}, "alleen_catalogus"),
    ],
)
def test_drie_statussen_op_een_plek_beslist(entry, verwacht):
    assert status(entry) == verwacht


_RIO_DUO = [
    {"leverancier": "RIO", "_rio_resource": "erkenningen", "bron": "RIO erkenningen", "title": "data erkenningen"},
    {"leverancier": "DUO", "_ckan_id": "duo-tabel", "bron": "DUO tabel", "title": "data tabel", "_resources": [_TABEL]},
    {"leverancier": "ROA", "_roa_id": "ais2028", "bron": "ROA oud", "title": "data prognose"},
]


def _hits(query: str, **kw) -> list[dict]:
    with patch("tools.catalog._cbs", return_value=[]), patch("tools.catalog._rio_duo", return_value=_RIO_DUO):
        uit = treffers(search_catalog(query, **kw))
    return [h for h in uit if "bron" in h]  # zonder de hintregels


def test_zoekhits_dragen_de_status_en_source_betekent_wat_hij_zegt():
    alles = {h["bron"]: h["status"] for h in _hits("data")}
    assert alles == {"RIO erkenningen": "opvraagbaar", "DUO tabel": "opvraagbaar", "ROA oud": "alleen_catalogus"}
    assert {h["bron"] for h in _hits("data", source="rio")} == {"RIO erkenningen"}
    assert {h["bron"] for h in _hits("data", source="duo")} == {"DUO tabel"}
    assert {h["bron"] for h in _hits("data", source="riodata")} == set(alles)
    roa = next(h for h in _hits("data") if h["bron"] == "ROA oud")
    assert roa["opvraagbaar"] is False and "geen datatool" in roa["melding"]


def test_detailrecord_draagt_dezelfde_status():
    assert json.loads(dataset_details("p01hoinges"))["status"] == catalog.STATUS_OPVRAAGBAAR
    with patch("tools.catalog._cbs", return_value=[]), patch("tools.catalog._rio_duo", return_value=_RIO_DUO):
        assert json.loads(dataset_details("ais2028"))["status"] == catalog.STATUS_ALLEEN_CATALOGUS
