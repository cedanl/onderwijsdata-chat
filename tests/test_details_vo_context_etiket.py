"""dataset_details van een vo-contexttabel draagt het etiket van de zoektreffer (#1096).

docs/databronnen.md belooft dat vo-contexttabellen altijd met label verschijnen. Een direct dataset-ID laadt zonder
zoekpoort, en een MCP-client vraagt vaak meteen dataset_details: ook daar moet staan dat het om vo-leerlingen gaat.
Echte catalogus, geen stub.
"""

import json

import pytest

import mcp_server
from tests.zoekuitkomst import treffers
from tools import scopeprofiel
from tools.catalog import dataset_details, search_catalog


@pytest.mark.parametrize("dataset_id", sorted(scopeprofiel.VO_CONTEXT))
def test_dataset_details_van_een_vo_contexttabel_draagt_het_etiket_van_de_zoektreffer(dataset_id):
    details = json.loads(dataset_details(dataset_id))

    assert details["context"] == scopeprofiel.VO_CONTEXT_ETIKET


def test_het_etiket_staat_ook_bij_een_id_met_voorvoegsel_en_andere_hoofdletters():
    assert json.loads(dataset_details("cbs:85566ned"))["context"] == scopeprofiel.VO_CONTEXT_ETIKET


def test_het_etiket_in_details_is_hetzelfde_als_op_de_zoektreffer():
    treffer = next(k for k in treffers(search_catalog("doorstroom havo hbo")) if k["dataset_id"] == "85566NED")

    assert json.loads(dataset_details("85566NED"))["context"] == treffer["context"]


@pytest.mark.parametrize("dataset_id", ["85379NED", "85566NED"])
def test_een_mcp_client_ziet_het_etiket_bij_dataset_details(dataset_id):
    tekst, is_fout = mcp_server.voer_uit("dataset_details", {"dataset_id": dataset_id})

    assert not is_fout
    assert json.loads(tekst)["context"] == scopeprofiel.VO_CONTEXT_ETIKET


@pytest.mark.parametrize("dataset_id", ["85423NED", "85701NED", "gediplomeerde-mbo-studenten"])
def test_dataset_details_van_een_gewone_tabel_krijgt_geen_etiket(dataset_id):
    assert "context" not in json.loads(dataset_details(dataset_id))
