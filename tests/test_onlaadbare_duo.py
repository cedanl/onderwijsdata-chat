"""#408: DUO-datasets die vindbaar zijn maar niet als tabel te laden.

Een changelog heeft alleen een PDF; leerling_so_en_vso-v1 heeft een dode link als
eerste bestand, maar twee bruikbare. Het model moet dat zien zonder te gaan zoeken.
"""

import json
from unittest.mock import patch

import pandas as pd

from tools import fouten
from tools.catalog import dataset_details, search_catalog
from tools.duo import get_duo_data

_CHANGELOG = {
    "leverancier": "DUO",
    "_ckan_id": "ho_opleidingsoverzicht-changelog",
    "bron": "Changelog van HO Opleidingsoverzicht",
    "title": "changelog opleidingsoverzicht",
    "_resources": [{"naam": "PVL Ho Opleidingsoverzicht", "format": "PDF", "id": "a"}],
}
_SO_VSO = {
    "leverancier": "DUO",
    "_ckan_id": "leerling_so_en_vso-v1",
    "bron": "Leerlingen SO en VSO",
    "title": "leerlingen so vso opleidingsoverzicht",
    "_resources": [
        {"naam": "per bekostigingscategorie", "format": "CSV", "id": "b"},
        {"naam": "residentiële plaatsen", "format": "CSV", "id": "c"},
        {"naam": "naar uitstroomprofiel", "format": "CSV", "id": "d"},
    ],
}


def _catalogus(*entries):
    return patch("tools.catalog._rio_duo", return_value=list(entries))


def test_changelog_is_niet_opvraagbaar_in_zoekresultaat_en_details():
    with patch("tools.catalog._cbs", return_value=[]), _catalogus(_CHANGELOG, _SO_VSO):
        hits = {h["_ckan_id"]: h for h in json.loads(search_catalog("opleidingsoverzicht", source="duo"))}
        details = json.loads(dataset_details("ho_opleidingsoverzicht-changelog"))
    assert hits["ho_opleidingsoverzicht-changelog"]["opvraagbaar"] is False
    assert "documentatie" in hits["ho_opleidingsoverzicht-changelog"]["melding"]
    assert "opvraagbaar" not in hits["leerling_so_en_vso-v1"]
    assert details["opvraagbaar"] is False


def test_pdf_resource_wordt_niet_gedownload():
    with _catalogus(_CHANGELOG), patch("tools.duo._duo.load") as load:
        result = get_duo_data("ho_opleidingsoverzicht-changelog")
    load.assert_not_called()
    assert fouten.code(result) == "bron_weigert"
    assert "alleen documentatie" in result


def test_laadfout_noemt_de_andere_bestanden_van_de_dataset():
    fout = pd.errors.ParserError("Expected 1 fields in line 7, saw 2")
    with _catalogus(_SO_VSO), patch("tools.duo._duo.load", side_effect=fout), patch("tools.duo._duo.catalog") as cat:
        result = get_duo_data("leerling_so_en_vso-v1")
    assert fouten.code(result) == "bron_weigert"
    assert "1 = 'residentiële plaatsen'" in result
    assert "2 = 'naar uitstroomprofiel'" in result
    assert "0 = " not in result
    cat.assert_not_called()  # geen omweg naar andere datasets
