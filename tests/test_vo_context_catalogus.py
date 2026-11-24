"""De catalogusrecords van de vo-contextbronnen beloven niet meer dan de bron heeft (#1055).

85380NED en 85379NED lopen vanaf 2011/'12, 85380NED en 85382NED hebben landsdeel, provincie en de vier grootste
gemeenten maar geen gemeenteniveau, en DUO `voprognoses` loopt van 2024 tot 2043 zonder po-tekst.
"""

import json
import re
from importlib.resources import files
from pathlib import Path

import onderwijsbronnen
import pytest
from onderwijsbronnen import cbs

from tests.zoekuitkomst import treffers
from tools.catalog import geodekking, search_catalog

_CBS_BESTANDEN = ("cbs_datasets.json", "cbs_datasets_ai.json", "cbs_datasets_enriched.json")
_AI_BESTANDEN = ("cbs_datasets_ai.json", "cbs_datasets_enriched.json")
_REGIOTABELLEN = ("85380NED", "85382NED")
_GEMEENTE = re.compile(r"\bgemeente\b", re.IGNORECASE)
_PO = re.compile(r"primair onderwijs|basisonderwijs", re.IGNORECASE)


def _cbs_record(bestand: str, cbs_id: str) -> dict:
    records = json.loads(files("onderwijsbronnen.cbs.data").joinpath(bestand).read_text(encoding="utf-8"))
    return next(r for r in records if r.get("_cbs_id") == cbs_id)


def _voprognoses() -> dict:
    return next(r for r in onderwijsbronnen.catalog("duo") if r.get("_ckan_id") == "voprognoses")


@pytest.mark.parametrize("bestand", _CBS_BESTANDEN)
@pytest.mark.parametrize("cbs_id", ["85380NED", "85379NED"])
def test_vo_leerlingen_lopen_vanaf_2011(cbs_id, bestand):
    assert _cbs_record(bestand, cbs_id)["periode"] == "2011/'12-2025/'26"


@pytest.mark.parametrize("bestand", _CBS_BESTANDEN)
@pytest.mark.parametrize("cbs_id", _REGIOTABELLEN)
def test_regiotabellen_hebben_geen_gemeenteniveau(cbs_id, bestand):
    niveaus = _cbs_record(bestand, cbs_id)["_geo_niveau"]
    assert "gemeente" not in niveaus
    assert {"landelijk", "provincie", "landsdeel"} <= set(niveaus)


@pytest.mark.parametrize("bestand", _AI_BESTANDEN)
@pytest.mark.parametrize("cbs_id", _REGIOTABELLEN)
@pytest.mark.parametrize("veld", ["doel", "samenvatting"])
def test_regiotekst_noemt_landsdeel_provincie_en_g4_zonder_gemeentebelofte(cbs_id, bestand, veld):
    tekst = _cbs_record(bestand, cbs_id)[veld]
    for woord in ("landsdeel", "provincie", "vier grootste gemeenten"):
        assert woord in tekst, (cbs_id, veld, woord)
    assert not _GEMEENTE.search(tekst)
    assert "capaciteitsplanning" not in tekst


@pytest.mark.parametrize("bestand", _AI_BESTANDEN)
@pytest.mark.parametrize("cbs_id", _REGIOTABELLEN)
def test_regiotabellen_vragen_niet_naar_mijn_regio(cbs_id, bestand):
    vragen = _cbs_record(bestand, cbs_id)["voorbeeldvragen"]
    assert not any("mijn regio" in v for v in vragen)


@pytest.mark.parametrize("bestand", _AI_BESTANDEN)
def test_vo_leerlingen_hebben_de_ho_instroomvraag(bestand):
    vraag = "Hoeveel havo 4/5- en vwo 4-6-leerlingen zijn er, als voorspeller voor de ho-instroom?"
    assert vraag in _cbs_record(bestand, "85380NED")["voorbeeldvragen"]


@pytest.mark.parametrize("cbs_id", _REGIOTABELLEN)
def test_geodekking_gemeente_is_nee(cbs_id):
    record = next(r for r in cbs.catalog() if r.get("_cbs_id") == cbs_id)
    assert geodekking(record, "gemeente") == "nee"
    assert geodekking(record, "provincie") == "ja"


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel havo-leerlingen per gemeente stromen door naar het hbo?",
        "Hoeveel havo-geslaagden per gemeente, als toekomstige hbo-studenten?",
    ],
)
def test_zoeken_op_gemeenteniveau_geeft_de_regiotabellen_niet(vraag):
    gevonden = {t["dataset_id"] for t in treffers(search_catalog(vraag, source="cbs", geo_niveau="gemeente"))}
    assert not gevonden & set(_REGIOTABELLEN)


def test_zoeken_op_provincieniveau_geeft_de_regiotabellen_wel():
    vraag = "Hoeveel havo-geslaagden per provincie, als toekomstige hbo-studenten?"
    gevonden = {t["dataset_id"] for t in treffers(search_catalog(vraag, source="cbs", geo_niveau="provincie"))}
    assert "85382NED" in gevonden


def test_voprognoses_loopt_van_2024_tot_2043():
    assert _voprognoses()["periode"] == "2024-2043"


@pytest.mark.parametrize("veld", ["beschrijving", "doel", "samenvatting"])
def test_voprognoses_heeft_geen_po_tekst(veld):
    assert not _PO.search(str(_voprognoses().get(veld) or ""))


def test_voprognoses_voorbeeldvragen_gaan_over_het_vo():
    vragen = _voprognoses()["voorbeeldvragen"]
    assert vragen
    assert not any(_PO.search(v) or "mbo" in v for v in vragen)


def test_voprognoses_beschrijving_noemt_eenheid_en_geen_leerjaar():
    beschrijving = _voprognoses()["beschrijving"]
    for woord in ("instelling", "onderwijsniveau", "vmbo", "havo", "vwo", "pro", "brj", "jaar", "geen leerjaar"):
        assert woord in beschrijving, woord


@pytest.mark.parametrize("bestand", ["duo_resources.json", "duo_resources_enriched.json"])
def test_voprognoses_bronvelden_gelijk_in_beide_bestanden(bestand):
    records = json.loads(files("onderwijsbronnen.duo.data").joinpath(bestand).read_text(encoding="utf-8"))
    record = next(r for r in records if r.get("_ckan_id") == "voprognoses")
    samengevoegd = _voprognoses()
    for veld in ("periode", "beschrijving", "doel", "voorbeeldvragen"):
        assert record[veld] == samengevoegd[veld], veld


_DOCS_VO_CONTEXT = re.compile(r"^\| `(?P<id>\w+NED)` \(CBS\) \|.*\| (?P<periode>[^|]+?) \|$", re.MULTILINE)


def test_databronnen_noemt_de_periode_van_de_catalogus_voor_elke_cbs_vo_contexttabel():
    """De tabel "Vo-context voor vervolgonderwijs" in docs/databronnen.md loopt niet achter op de catalogus (#1070)."""
    docs = (Path(__file__).parent.parent / "docs" / "databronnen.md").read_text(encoding="utf-8")
    rijen = {m["id"]: m["periode"] for m in _DOCS_VO_CONTEXT.finditer(docs)}
    assert len(rijen) == 9
    assert rijen == {cbs_id: _cbs_record("cbs_datasets_ai.json", cbs_id)["periode"] for cbs_id in rijen}
