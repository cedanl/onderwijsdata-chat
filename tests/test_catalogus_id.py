"""Eén catalogus-ID per record, gelijk aan het broncontract van onderwijsbronnen (#967).

`search_catalog("arbeidsmarkt ict")` gaf kandidaten met dataset_id "?": tools/catalog.py had een eigen lijst
ID-velden zonder `_roa_id` en `_sbb_id`, naast een andere in tools/scopeprofiel.py. Nu leest de chat één lijst
(`scopeprofiel.ID_VELDEN`), en deze test houdt die gelijk aan `<bron>.metadata(record)["id"]`.
"""

import json

import onderwijsbronnen
import pytest

from tools import catalog, scopeprofiel


@pytest.mark.parametrize("bron", onderwijsbronnen.BRONNEN)
def test_het_id_van_elk_record_is_dat_van_het_broncontract(bron):
    module = getattr(onderwijsbronnen, bron)
    records = onderwijsbronnen.catalogus()[bron]
    assert records
    assert [scopeprofiel.dataset_id(r) for r in records] == [module.metadata(r)["id"] for r in records]


def test_geen_record_van_de_chatcatalogus_heeft_vraagteken_als_id():
    zonder = [
        r.get("bron") for r in [*catalog._cbs_alles(), *catalog._rio_duo_alles()] if catalog._dataset_id(r) == "?"
    ]
    assert zonder == []


@pytest.mark.parametrize("vraag", ["arbeidsmarkt ict", "collegegeld 2026"])
def test_search_catalog_geeft_elke_kandidaat_een_id(vraag):
    kandidaten = json.loads(catalog.search_catalog(vraag))["kandidaten"]
    assert kandidaten
    assert "?" not in [k["dataset_id"] for k in kandidaten]


def test_roa_en_sbb_hebben_hun_eigen_id():
    ids = {catalog._dataset_id(r) for r in catalog._rio_duo_alles()}
    assert {"ais2030", "ais2028", "crebolijst", "kwalificatiedossiers-xml"} <= ids
