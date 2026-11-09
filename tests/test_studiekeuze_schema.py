"""Het schema van de Studiekeuzedatabase in search_catalog en dataset_details (#978).

SKDB-audit 09-11 (S4): op een schemavraag zei de chat dat zij het schema niet kon raadplegen, terwijl de export 45
tabelbeschrijvingen en 639 kolomdefinities heeft; search_catalog vond "tracks", "studieadvies" en "skdb" niet. De
tabelnamen staan in de code (zoeken zonder download), de omschrijvingen, kolommen en types komen uit de export.
"""

import json

import pytest
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

from core import config
from tools import catalog, skdb_schema, studiekeuze
from tools.schemas import TOOL_GET_STUDIEKEUZE

_CACHES = (catalog._rio_duo_alles, catalog._rio_duo, catalog.catalogus_digest, studiekeuze._export)


def _leeg() -> None:
    for cache in _CACHES:
        cache.cache_clear()


@pytest.fixture
def opgehaald(monkeypatch):
    """De sleutel aan en de proefexport als export van vandaag; telt de downloads."""
    keer: list[int] = []

    def haal_op(*a, **k):
        keer.append(1)
        return proefbestand.standaard()

    monkeypatch.setattr(skdb, "haal_op", haal_op)
    monkeypatch.setattr(config, "STUDIEKEUZEDATABASE_API_KEY", "proefsleutel")
    _leeg()
    yield keer
    monkeypatch.undo()
    _leeg()


def _kandidaten(vraag: str) -> list[dict]:
    return json.loads(catalog.search_catalog(vraag))["kandidaten"]


def _skdb(vraag: str) -> dict | None:
    return next((k for k in _kandidaten(vraag) if k["dataset_id"] == "studiekeuzedatabase"), None)


def _tabellen(vraag: str) -> list[str]:
    hit = _skdb(vraag)
    assert hit is not None, vraag
    return hit["tabellen"]


# --- zoeken -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("vraag", "tabel"), [("tracks", "tracks"), ("studieadvies", "studieadvies")])
def test_een_tabelnaam_vindt_de_studiekeuzedatabase_met_die_tabel(opgehaald, vraag, tabel):
    hit = _skdb(vraag)
    assert hit is not None
    [regel] = hit["tabellen"]
    assert regel.startswith(f"{tabel}: ") and "pakket" in regel
    assert opgehaald == []  # zoeken haalt de export niet op


def test_een_tabel_met_een_weergave_noemt_die_weergave(opgehaald):
    [regel] = _tabellen("lotingopleidingendecentraleselecties")
    assert TOOL_GET_STUDIEKEUZE in regel and "numerus_fixus" in regel


def test_een_tabel_waarvoor_een_andere_bron_leidend_is_zegt_dat(opgehaald):
    wettelijk, niet_wettelijk = sorted(_tabellen("collegegelden"))
    assert wettelijk.startswith("collegegelden: ") and "niet in de chat" in wettelijk and "wettekst" in wettelijk
    # Het instellingscollegegeld (HOVI) heeft geen andere bron: alleen in het pakket.
    assert niet_wettelijk.startswith("nietwettelijkecollegegelden: ") and "pakket" in niet_wettelijk


def test_skdb_vindt_de_studiekeuzedatabase_bovenaan_met_de_weg_naar_het_schema(opgehaald):
    [hit, *_] = _kandidaten("skdb")
    assert hit["dataset_id"] == "studiekeuzedatabase"
    assert "dataset_details('skdb:studiekeuzedatabase')" in hit["schema"]
    assert "tabellen" not in hit  # geen tabel geraakt: geen lijst van 45


def test_zonder_sleutel_vindt_een_tabelnaam_niets_van_de_studiekeuzedatabase(monkeypatch):
    monkeypatch.setattr(config, "STUDIEKEUZEDATABASE_API_KEY", "")
    _leeg()
    try:
        assert _skdb("tracks") is None
    finally:
        monkeypatch.undo()
        _leeg()


# --- dataset_details ----------------------------------------------------------------------------------------------


def test_details_van_de_bron_tonen_het_schema_uit_de_export(opgehaald):
    details = json.loads(catalog.dataset_details("skdb:studiekeuzedatabase"))
    assert (details["status"], details["via_tool"]) == ("via_tool", TOOL_GET_STUDIEKEUZE)
    schema = details["schema"]
    assert schema["editie"]["versie"] == "26.6"
    assert "geen 0" in schema["null"]
    tabellen = {t["tabel"]: t for t in schema["tabellen"]}
    assert tabellen["tracks"]["omschrijving"] == "Proef: een track"
    assert tabellen["tracks"]["kan"] == "pakket"
    assert tabellen["opleidingvormen"]["kan"].startswith("weergave")
    assert tabellen["collegegelden"]["kan"].startswith("andere_bron")
    assert set(schema["kan"]) == {"weergave", "pakket", "andere_bron"}
    assert "skdb:studiekeuzedatabase/<tabel>" in details["vervolgstap"]
    assert skdb.VERPLICHTE_ZIN in details["bronregel"]
    assert opgehaald == [1]


def test_details_van_een_tabel(opgehaald):
    details = json.loads(catalog.dataset_details("skdb:studiekeuzedatabase/opleidingen"))
    assert details["tabel"] == "opleidingen"
    assert details["dataset_id"] == "skdb:studiekeuzedatabase/opleidingen"
    assert details["korrel"] == ["opleidingSkdb"]
    assert details["kolommen"]["opleidingCode"] == "number: Proef: opleidingCode"
    # De sleutels naar andere bronnen komen uit de connectoren van relatie (één lijst, #958).
    assert {"kolom": "instellingCode", "sleutel": "instellingscode"} in details["sleutels"]
    assert {"kolom": "opleidingCode", "sleutel": "erkende_opleiding"} in details["sleutels"]
    assert {"tabel": "instellingen", "via": ["instellingSkdb"]} in details["relaties"]
    assert "get_studiekeuze" in details["kan"] and "toelating" in details["kan"]
    assert skdb.VERPLICHTE_ZIN in details["bronregel"]


def test_een_tabel_alleen_in_het_pakket_noemt_hoe_je_haar_leest(opgehaald):
    details = json.loads(catalog.dataset_details("studiekeuzedatabase/tracks"))
    assert "skdb.load('tracks')" in details["kan"]
    assert details["relaties"][0] == {"tabel": "vestigingen", "via": ["instellingSkdb", "vestigingSkdb"]}


def test_een_kolom_met_een_leidende_andere_bron(opgehaald):
    details = json.loads(catalog.dataset_details("skdb:studiekeuzedatabase/opleidingvormen"))
    assert details["kolommen"]["eersteJaarAantal"].startswith("number; andere bron leidend: DUO")
    assert details["jaarkolommen"] == ["enqueteJaar"]


def test_een_onbekende_tabel(opgehaald):
    tekst = catalog.dataset_details("skdb:studiekeuzedatabase/bestaatniet")
    assert "bestaatniet" in tekst and "skdb:studiekeuzedatabase" in tekst


def test_zonder_export_noemen_de_details_de_tabellen_met_wat_er_kan(opgehaald, monkeypatch):
    def kapot(*a, **k):
        raise skdb.SkdbFout("De Studiekeuzedatabase gaf HTTP 503 op de export.")

    monkeypatch.setattr(skdb, "haal_op", kapot)
    studiekeuze._export.cache_clear()
    details = json.loads(catalog.dataset_details("skdb:studiekeuzedatabase"))
    assert "HTTP 503" in details["schema"]["melding"]
    tabellen = {t["tabel"]: t for t in details["schema"]["tabellen"]}
    assert len(tabellen) == 45 and tabellen["tracks"] == {"tabel": "tracks", "kan": "pakket"}
    tabel = json.loads(catalog.dataset_details("skdb:studiekeuzedatabase/tracks"))
    assert "HTTP 503" in tabel["melding"] and "skdb.load('tracks')" in tabel["kan"]


def test_een_grote_tabel_past_binnen_het_detailbudget(opgehaald, monkeypatch):
    kolommen = [
        {"Tabel": "vestigingen", "Kolom": f"kolom{i}", "Type": "number", "Omschrijving": "x" * 400} for i in range(80)
    ]
    tabellen = {**proefbestand.TABELLEN, "exportkolommen": [*proefbestand.EXPORTKOLOMMEN, *kolommen]}
    inhoud = proefbestand.zip_bytes(tabellen)
    monkeypatch.setattr(skdb, "haal_op", lambda *a, **k: (inhoud, skdb.herkomst(inhoud, proefbestand.BESTAND)))
    studiekeuze._export.cache_clear()
    tekst = catalog.dataset_details("skdb:studiekeuzedatabase/vestigingen")
    assert len(tekst) <= skdb_schema.DETAILS_BUDGET
    details = json.loads(tekst)
    assert len(details["kolommen"]) == 84  # elke kolom blijft staan, de omschrijvingen worden korter of vallen weg
    assert "kolomdetail_weggelaten" in details


def test_zonder_sleutel_is_een_tabel_onbekend(monkeypatch):
    monkeypatch.setattr(config, "STUDIEKEUZEDATABASE_API_KEY", "")
    _leeg()
    try:
        assert "niet gevonden" in catalog.dataset_details("skdb:studiekeuzedatabase/tracks")
    finally:
        monkeypatch.undo()
        _leeg()
