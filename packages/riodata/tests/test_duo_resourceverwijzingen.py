"""Tests voor catalogus/ververs_duo_resourceverwijzingen.py: puur, zonder netwerk."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "catalogus"))

from ververs_duo_resourceverwijzingen import ververs_resources


def _r(naam: str, id_: str) -> dict:
    return {"naam": naam, "url": f"https://x/{id_}", "format": "CSV", "id": id_}


def test_resource_die_nog_bestaat_blijft_ongemoeid():
    snapshot = [_r("data", "a"), _r("controlebestand", "b")]
    nieuw, meldingen = ververs_resources(snapshot, [_r("data", "a"), _r("controlebestand", "b")])
    assert nieuw == snapshot
    assert meldingen == {"ververst": [], "vervallen": [], "nieuw": []}


def test_controlebestand_met_nieuw_id_krijgt_id_en_url_maar_houdt_naam_en_format():
    snapshot = [_r("data", "a"), _r("controlebestand", "oud")]
    nieuw, meldingen = ververs_resources(snapshot, [_r("data", "a"), _r("controlebestand", "nieuw")])
    assert nieuw[1] == {"naam": "controlebestand", "url": "https://x/nieuw", "format": "CSV", "id": "nieuw"}
    assert nieuw[0] == snapshot[0]
    assert meldingen["ververst"] == ["controlebestand"]


def test_volgorde_van_het_snapshot_blijft_behouden():
    snapshot = [_r("controlebestand", "oud"), _r("data", "a")]
    nieuw, _ = ververs_resources(snapshot, [_r("data", "a"), _r("controlebestand", "nieuw")])
    assert [r["naam"] for r in nieuw] == ["controlebestand", "data"]


def test_verdwenen_resource_wordt_gemeld_en_niet_verwijderd():
    snapshot = [_r("data", "a"), _r("weg", "w")]
    nieuw, meldingen = ververs_resources(snapshot, [_r("data", "a")])
    assert nieuw == snapshot
    assert meldingen["vervallen"] == ["weg"]


def test_nieuwe_resource_wordt_gemeld_en_niet_toegevoegd():
    snapshot = [_r("data", "a")]
    nieuw, meldingen = ververs_resources(snapshot, [_r("data", "a"), _r("extra", "e")])
    assert nieuw == snapshot
    assert meldingen["nieuw"] == ["extra"]


def test_dubbelzinnige_naam_wordt_niet_geraden():
    snapshot = [_r("controlebestand", "oud")]
    live = [_r("controlebestand", "n1"), _r("controlebestand", "n2")]
    nieuw, meldingen = ververs_resources(snapshot, live)
    assert nieuw == snapshot
    assert meldingen["vervallen"] == ["controlebestand"]
    assert meldingen["nieuw"] == ["controlebestand", "controlebestand"]


def test_een_nieuw_id_wordt_maar_aan_een_snapshot_resource_gekoppeld():
    snapshot = [_r("controlebestand", "oud1"), _r("controlebestand", "oud2")]
    nieuw, meldingen = ververs_resources(snapshot, [_r("controlebestand", "nieuw")])
    assert [r["id"] for r in nieuw] == ["nieuw", "oud2"]
    assert meldingen["ververst"] == ["controlebestand"]
    assert meldingen["vervallen"] == ["controlebestand"]
