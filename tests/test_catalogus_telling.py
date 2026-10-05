"""Hoeveel datasets per bron: een telling uit code, niet uit zoekresultaten (#168).

Live-audit 4: gpt-oss weigerde terecht een DUO-totaal uit zoekresultaten af te leiden,
maar had geen tool die het door de app zelf getoonde getal (56) gaf. Een zoekopdracht
zonder treffers leidde tot "geen geschikte DUO-bron", terwijl het bestand er was.
"""

import json
from unittest.mock import patch

from tools import dispatch
from tools.catalog import search_catalog

_CBS = [{"_cbs_id": "a", "bron": "x"}, {"_cbs_id": "b", "bron": "y", "_archief": True}]
_RIO_DUO = [
    {"leverancier": "DUO", "_ckan_id": "p01hoinges", "bron": "Ingeschrevenen hoger onderwijs"},
    {"leverancier": "DUO", "_ckan_id": "p03hoinges", "bron": "Ingeschrevenen hbo"},
    {"leverancier": "RIO", "_rio_resource": "onderwijslocaties", "bron": "Onderwijslocaties"},
    {"leverancier": "SBB", "_ckan_id": "sbb", "bron": "Stages"},
]


def _catalogus():
    return patch("tools.catalog._cbs", return_value=_CBS), patch("tools.catalog._rio_duo", return_value=_RIO_DUO)


def test_dataset_counts_is_een_tool_met_de_telling_per_bron():
    cbs, rio_duo = _catalogus()
    with cbs, rio_duo:
        result, _ = dispatch("dataset_counts", {})
    telling = json.loads(result)

    assert telling["datasets_per_bron"] == {"CBS": 2, "DUO": 2, "RIO": 1}
    assert telling["cbs_gearchiveerd"] == 1


def test_een_zoekopdracht_zonder_treffers_zegt_niet_dat_de_bron_ontbreekt():
    cbs, rio_duo = _catalogus()
    with cbs, rio_duo:
        result = search_catalog("eindexamencijfers vmbo")

    assert "Geen resultaten" in result
    assert "zegt niet dat" in result
    assert "dataset_details" in result
    assert "bestaat niet" not in result
