"""
Tests voor CBS-03: versieerbaar datasetcontract. Offline, zonder LLM of API-key.
"""
import json
from pathlib import Path

import pytest

import onderwijsdata as od
from onderwijsdata import contract

FIXTURES = sorted((Path(__file__).parent / "fixtures" / "contract_v1").glob("*.json"))


@pytest.mark.parametrize("pad", FIXTURES, ids=lambda p: p.stem)
def test_fixture_levert_verwacht_record_en_valideert(pad):
    fx = json.loads(pad.read_text(encoding="utf-8"))
    record = contract._record(fx["bron"], fx.get("tableinfo"))
    # capabilities zijn package-niveau en groeien mee met nieuwe functies
    record.pop("capabilities"), fx["verwacht"].pop("capabilities")
    assert record == fx["verwacht"]
    assert contract.valideer_record(record) == []


def test_fixtures_aanwezig():
    namen = {p.stem for p in FIXTURES}
    assert {"ho_ingeschrevenen", "ho_eerstejaars"} <= namen


class TestScopeprofiel:
    def test_pure_ho_tabel_is_supported_voor_hbo_en_wo(self):
        assert contract._scopeprofiel(["HBO", "WO"]) == {"mbo": "unsupported", "hbo": "supported", "wo": "supported"}

    def test_allen_is_unknown_niet_supported(self):
        assert set(contract._scopeprofiel(["Allen"]).values()) == {"unknown"}

    def test_leeg_is_unknown(self):
        assert set(contract._scopeprofiel([]).values()) == {"unknown"}

    def test_alleen_po_vo_is_unsupported(self):
        assert set(contract._scopeprofiel(["PO", "VO"]).values()) == {"unsupported"}

    def test_gemengd_met_mbo_is_unknown_voor_mbo(self):
        assert contract._scopeprofiel(["VO", "MBO"]) == {"mbo": "unknown", "hbo": "unsupported", "wo": "unsupported"}


class TestGeografie:
    def test_geen_regiodimensie_is_landelijk_zonder_uitsplitsing(self):
        # Review F5: geen regionale uitsplitsing is iets anders dan geen landelijke cijfers.
        geo = contract._geografie({"_dimensies": ["Geslacht", "Perioden"], "_geo_niveau": []})
        assert geo["status"] == "supported" and geo["niveaus"] == ["landelijk"]
        assert geo["regionale_uitsplitsing"] is False

    def test_caribisch_nederland_is_niet_landelijk(self):
        geo = contract._geografie({"bron": "Caribisch NL; studenten mbo, niveau, sector, domein",
                                   "_dimensies": ["Niveau", "Perioden"], "_geo_niveau": []})
        assert geo["status"] == "unsupported" and geo["dekking"] == "Caribisch Nederland"

    def test_regiodimensie_zonder_niveaus_is_unknown_niet_leeg(self):
        geo = contract._geografie({"_dimensies": ["RegioS"], "_geo_niveau": []})
        assert geo["status"] == "unknown" and geo["niveaus"] is None

    def test_niveaus_supported(self):
        geo = contract._geografie({"_dimensies": ["RegioS"], "_geo_niveau": ["landelijk", "gemeente"]})
        assert geo["status"] == "supported" and geo["niveaus"] == ["landelijk", "gemeente"]

    def test_onbekende_dimensies_is_unknown(self):
        assert contract._geografie({})["status"] == "unknown"


class TestApi:
    def test_alle_records_valideren(self):
        records = od.catalog_records()
        assert len(records) == len(od.catalog())
        assert [(r["dataset_id"], f) for r in records for f in contract.valideer_record(r)] == []

    def test_sectorselectie_is_reproduceerbaar_en_bevat_alleen_supported(self):
        a = od.catalog_records(sector="mbo")
        b = od.catalog_records(sector="MBO")
        assert a == b and a
        assert all(r["scopeprofiel"]["mbo"] == "supported" for r in a)

    def test_onbekende_dekking_naar_reviewlijst_niet_in_selectie(self):
        review_ids = {r["dataset_id"] for r in od.scope_review()}
        for sector in contract.SECTOREN:
            assert review_ids.isdisjoint({r["dataset_id"] for r in od.catalog_records(sector=sector)})
        assert all("unknown" in r["scopeprofiel"].values() for r in od.scope_review())

    def test_onbekende_sector_geeft_fout(self):
        with pytest.raises(ValueError):
            od.catalog_records(sector="vo")

    def test_onbekende_schemaversie_geeft_fout(self):
        with pytest.raises(contract.OnbekendSchema):
            od.catalog_records(schema_version=2)

    @pytest.mark.parametrize("sleutel", ["cbs:85423NED", "85423NED", "85423ned", " CBS:85423ned "])
    def test_id_resolutie_exact_en_backward_compatible(self, sleutel):
        assert od.get_dataset(sleutel)["dataset_id"] == "cbs:85423NED"

    @pytest.mark.parametrize("sleutel", ["85423", "cbs:", "85423NEDX", "dup:85423NED"])
    def test_geen_fuzzy_match(self, sleutel):
        with pytest.raises(contract.DatasetNietGevonden):
            od.get_dataset(sleutel)

    def test_bestaande_catalog_ongewijzigd(self):
        rec = next(r for r in od.catalog() if r["_cbs_id"] == "85423NED")
        assert "bron" in rec and "_meetwaarden" in rec

    def test_manifest_is_compact_en_stabiel(self):
        m = od.catalog_manifest()
        assert m["aantal"] == len(od.catalog_records())
        assert m == od.catalog_manifest()
        assert m["aantal_per_sector"]["hbo"] > 0 and m["aantal_review"] > 0

    def test_resultaat_is_een_kopie(self):
        r = od.get_dataset("85423NED")
        r["titel"] = "gewijzigd"
        assert od.get_dataset("85423NED")["titel"] != "gewijzigd"


class TestValidatie:
    def test_onbekend_als_lege_lijst_wordt_afgekeurd(self):
        record = od.get_dataset("85423NED")
        record["geografie"] = {"status": "unknown", "niveaus": []}
        assert any("onbekend" in f for f in contract.valideer_record(record))

    def test_ontbrekende_status_wordt_afgekeurd(self):
        record = od.get_dataset("85423NED")
        record["populatie"] = {}
        assert contract.valideer_record(record)


def test_dimensies_op_verzoek_en_gecachet(monkeypatch):
    calls = []

    def definitions(cbs_id):
        return {"Geslacht": {"title": "Geslacht", "type": "Dimension"}}

    def dimension(cbs_id, key):
        calls.append(key)
        return {"T001038": "Totaal"}

    monkeypatch.setattr(contract, "_dimensie_cache", contract._dimensie_cache.__wrapped__)
    from onderwijsdata import client
    monkeypatch.setattr(client, "definitions", definitions)
    monkeypatch.setattr(client, "dimension", dimension)
    assert contract.dimensie_waarden("cbs:85423NED", "Geslacht") == {"T001038": "Totaal"}
    assert calls == ["Geslacht"]
