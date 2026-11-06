"""Hoe search_catalog de Studiekeuzedatabase vindt, met de sleutel aan (#957, afspraken #878).

Gemeten op de !862-branch: "aantal studenten Hogeschool Utrecht" gaf de Studiekeuzedatabase als eerste kandidaat,
terwijl DUO voor aantallen leidend is; "studenttevredenheid opleiding" vond haar pas als twaalfde, na de
RIO-registers. Het catalogusrecord noemde "studenten" in de beschrijving, het doel, een voorbeeldvraag en een tag, en
"studenttevredenheid" alleen in de tags.
"""

import json

import pytest

from core import config
from tools import catalog

_SKDB = "studiekeuzedatabase"


@pytest.fixture
def met_sleutel(monkeypatch):
    monkeypatch.setattr(config, "STUDIEKEUZEDATABASE_API_KEY", "proefsleutel")
    gecachet = (catalog._rio_duo_alles, catalog._rio_duo, catalog.catalogus_digest)
    for functie in gecachet:
        functie.cache_clear()
    yield
    monkeypatch.undo()
    for functie in gecachet:
        functie.cache_clear()


def _ids(vraag: str) -> list[str]:
    return [k["dataset_id"] for k in json.loads(catalog.search_catalog(vraag))["kandidaten"]]


def test_een_vraag_naar_aantallen_studenten_gaat_niet_naar_de_studiekeuzedatabase(met_sleutel):
    ids = _ids("aantal studenten Hogeschool Utrecht")
    # Een hogeschool in een voorbeeldvraag mag meetellen, maar niet boven de DUO- en CBS-tellingen uit.
    assert ids and _SKDB not in ids[:8]


@pytest.mark.parametrize("vraag", ["studenttevredenheid opleiding", "studenttevredenheid"])
def test_studenttevredenheid_vindt_de_studiekeuzedatabase_bovenaan(met_sleutel, vraag):
    # Bij "opleiding" scoren de RIO-registers op dat ene woord even hoog; de dataset-ID beslist dan (#344).
    assert _SKDB in _ids(vraag)[:5]


def test_het_record_noemt_studenten_nergens_als_zoekbaar_woord(met_sleutel):
    """Een losse "studenten" in een doorzoekbaar veld maakt elke aantallenvraag een treffer (prefixmatch)."""
    [record] = [r for r in catalog._rio_duo_alles() if r.get("_skdb_id") == _SKDB]
    assert catalog._score(record, [("studenten", 1.0)]) == 0
    assert catalog._score(record, [("studenttevredenheid", 1.0)]) > 0
