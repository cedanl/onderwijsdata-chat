"""search_catalog toetst de po/vo-scope van de zoekterm ook als er treffers zijn (#1093).

Eerder gebeurde dat alleen als niets gevonden was: "basisonderwijs leerlingen" gaf mbo-tabellen zonder scope-melding,
ook aan een MCP-client. Echte catalogus, geen stub.
"""

import json

import pytest

import mcp_server
from tests.zoekuitkomst import envelop
from tools import ho_markers, scopeprofiel
from tools.catalog import search_catalog


@pytest.mark.parametrize(
    "zoekterm",
    [
        "basisschool",
        "eindexamen vwo cijfers",
        "basisonderwijs leerlingen",
        "leerlingen voortgezet onderwijs",
        "havo vwo eindexamen",
        "vo examens",
    ],
)
def test_een_zoekterm_over_po_of_vo_zonder_vervolgcontext_is_out_of_scope_ook_met_treffers(zoekterm):
    uitkomst = envelop(search_catalog(zoekterm))

    assert uitkomst["status"] == "out_of_scope"
    assert uitkomst["kandidaten"] == []
    assert uitkomst["melding"] == scopeprofiel.MELDING
    assert "alleen mbo, hbo en wo" in uitkomst["vervolgstap"]


@pytest.mark.parametrize("zoekterm", ["doorstroom havo hbo", "doorstroom vmbo mbo"])
def test_een_zoekterm_over_doorstroom_uit_het_vo_blijft_candidates_met_gelabelde_vo_context(zoekterm):
    uitkomst = envelop(search_catalog(zoekterm))

    assert uitkomst["status"] == "candidates"
    gelabeld = {k["dataset_id"] for k in uitkomst["kandidaten"] if k.get("context") == scopeprofiel.VO_CONTEXT_ETIKET}
    assert gelabeld, "geen vo-contexttabel met etiket bij een doorstroomvraag"
    assert gelabeld <= set(scopeprofiel.VO_CONTEXT)


def test_een_havo_zoekterm_bij_een_vraag_over_het_ho_blijft_een_zoekvraag():
    """Het model zoekt op "havo"; de vraag van de gebruiker gaat over de instroom in het hbo (#597)."""
    with ho_markers.beurtvraag("Hoeveel studenten in het hbo komen van de havo?"):
        uitkomst = envelop(search_catalog("havo"))

    assert uitkomst["status"] != "out_of_scope"


def test_dezelfde_zoekterm_bij_een_vraag_over_het_vo_is_out_of_scope():
    with ho_markers.beurtvraag("Hoeveel leerlingen zitten er op het vwo?"):
        assert envelop(search_catalog("havo"))["status"] == "out_of_scope"


@pytest.mark.parametrize("zoekterm", ["basisonderwijs leerlingen", "vo examens"])
def test_een_mcp_client_krijgt_out_of_scope_bij_een_po_of_vo_zoekterm(zoekterm):
    tekst, is_fout = mcp_server.voer_uit("search_catalog", {"query": zoekterm})

    assert not is_fout
    assert json.loads(tekst)["status"] == "out_of_scope"
