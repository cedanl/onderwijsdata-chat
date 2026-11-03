"""Scopebesluit RIO-05: Inspectie-items (PO/SO/VO) zijn buiten het mbo/hbo/wo-profiel."""
import riodata
from riodata import scope


def test_inspectie_items_zijn_buiten_scope():
    records = riodata.catalog("inspectie")
    assert {r["_inspectie_id"] for r in records} == {"oordelen", "schorsingen"}
    for r in records:
        assert scope.scope_status(r) == "buiten_scope" and scope.buiten_scope(r)
        assert r["_scope"]["reden"] and "RIO-05" in r["_scope"]["besluit"]
        assert set(r["onderwijstype"]) == {"PO", "SO", "VO"}


def test_onbekend_is_geen_toelating_en_geen_uitsluiting():
    r = {"bron": "x"}
    assert scope.scope_status(r) == "onbekend" and not scope.buiten_scope(r)


def test_andere_bronnen_zijn_niet_gelabeld():
    for bron in ("rio", "duo", "roa", "uwv", "sbb"):
        assert all("_scope" not in r for r in riodata.catalog(bron)), bron


def test_bestaande_inspectie_api_en_velden_ongewijzigd():
    r = riodata.catalog("inspectie")[0]
    assert r["bron"] == "Oordelen per school" and r["_inspectie_id"] == "oordelen"
