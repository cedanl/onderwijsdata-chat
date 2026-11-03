"""
Tests voor CBS-01: enriched volgt altijd de bronmetadata; afgeleide laag is
versie/inputhash-gebonden en idempotent.
"""
import sys
import os
import json
import filecmp
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "catalogus"))

import pytest
import verrijk_catalogus as vc

ROOT = Path(__file__).parent.parent


def _bron(**extra):
    return {
        "_cbs_id": "TEST01NED",
        "_laatste_update": "2026-01-01",
        "_archief": False,
        "_dimensies": ["Geslacht", "Perioden"],
        "_meetwaarden": ["Aantal_1"],
        "_meetwaarden_details": {"Aantal_1": {"title": "Aantal", "unit": "aantal"}},
        "_geo_niveau": [],
        "samenvatting": "AI-tekst",
        **extra,
    }


@pytest.fixture
def nep_cbs(monkeypatch):
    """Vervang de CBS-client door vaste data; geeft het aantal aanroepen terug."""
    calls = {"n": 0, "fail": set()}

    def dimension(dataset_id, dim):
        calls["n"] += 1
        if dim in calls["fail"]:
            raise RuntimeError("404")
        return {"A": "Totaal", "B": "Mannen"} if dim == "Geslacht" else {"2020": "2020", "2024": "2024"}

    def definitions(dataset_id):
        return {
            "Aantal_1": {"title": "Aantal", "unit": "aantal", "type": "Topic"},
            "Geslacht": {"type": "Dimension"},
            "Perioden": {"type": "TimeDimension"},
        }

    monkeypatch.setattr(vc.client, "dimension", dimension)
    monkeypatch.setattr(vc.client, "definitions", definitions)
    monkeypatch.setattr(vc.time, "sleep", lambda s: None)
    return calls


class TestBronvelden:
    def test_bronwijziging_verschijnt_ondanks_bestaande_kolommen(self, nep_cbs):
        bestaand = vc.enrich_entry(_bron())
        assert bestaand["_kolommen"]

        nieuw = _bron(_archief=True, samenvatting="Nieuwe AI-tekst")
        assert vc.is_actueel(bestaand, nieuw)  # afleiding blijft geldig...
        record = vc.ververs_bronvelden(bestaand, _bron(_laatste_update="2026-05-05", _archief=True,
                                                       samenvatting="Nieuwe AI-tekst"))
        assert record["_laatste_update"] == "2026-05-05"  # ...maar de bron wordt ververst
        assert record["_archief"] is True
        assert record["samenvatting"] == "Nieuwe AI-tekst"
        assert record["_kolommen"] == bestaand["_kolommen"]

    def test_verversen_is_idempotent(self, nep_cbs):
        bestaand = vc.enrich_entry(_bron())
        een = vc.ververs_bronvelden(bestaand, _bron())
        twee = vc.ververs_bronvelden(een, _bron())
        assert een == twee

    def test_ververs_zonder_api_calls(self, nep_cbs):
        bestaand = vc.enrich_entry(_bron())
        aantal = nep_cbs["n"]
        vc.ververs_bronvelden(bestaand, _bron(_laatste_update="2027-01-01"))
        assert nep_cbs["n"] == aantal


class TestInvalidatie:
    def test_alleen_annotaties_wijzigen_invalideert_niet(self, nep_cbs):
        bestaand = vc.enrich_entry(_bron())
        assert vc.is_actueel(bestaand, _bron(tags=["x"], samenvatting="andere AI-tekst", _archief=True))

    def test_nieuwe_bronperiode_bij_gelijk_schema_invalideert(self, nep_cbs):
        # CBS voegt een studiejaar toe zonder kolommen te wijzigen (review F3).
        bestaand = vc.enrich_entry(_bron(periode="2011/'12 - 2025/'26"))
        assert not vc.is_actueel(bestaand, _bron(periode="2011/'12 - 2026/'27"))

    def test_nieuwe_bronwijzigingsdatum_invalideert(self, nep_cbs):
        bestaand = vc.enrich_entry(_bron())
        assert not vc.is_actueel(bestaand, _bron(_laatste_update="2027-01-01"))

    def test_nieuwe_afleiding_volgt_nieuwe_periode(self, nep_cbs, monkeypatch):
        bestaand = vc.enrich_entry(_bron())
        assert bestaand["_periode_waarden"] == ["2020", "2024"]
        echte = vc.client.dimension
        monkeypatch.setattr(vc.client, "dimension",
                            lambda i, d: {"2020": "2020", "2025": "2025"} if d == "Perioden" else echte(i, d))
        nieuw = _bron(_laatste_update="2027-01-01")
        assert not vc.is_actueel(bestaand, nieuw)
        assert vc.enrich_entry(nieuw)["_periode_waarden"] == ["2020", "2025"]

    def test_gewijzigde_meetwaarden_invalideren(self, nep_cbs):
        bestaand = vc.enrich_entry(_bron())
        assert not vc.is_actueel(bestaand, _bron(_meetwaarden=["Aantal_1", "Extra_2"]))

    def test_gewijzigde_dimensies_invalideren(self, nep_cbs):
        bestaand = vc.enrich_entry(_bron())
        assert not vc.is_actueel(bestaand, _bron(_dimensies=["Geslacht", "Leeftijd", "Perioden"]))

    def test_nieuwe_verrijkingsversie_invalideert(self, nep_cbs, monkeypatch):
        bestaand = vc.enrich_entry(_bron())
        monkeypatch.setattr(vc, "VERRIJKING_VERSIE", vc.VERRIJKING_VERSIE + 1)
        assert not vc.is_actueel(bestaand, _bron())

    def test_record_zonder_stempel_is_verouderd(self):
        assert not vc.is_actueel({"_kolommen": {"a": 1}}, _bron())


class TestNietGeschiktVoor:
    def test_alleen_landelijk_geeft_beperking(self, nep_cbs):
        rec = vc.enrich_entry(_bron(_geo_niveau=["landelijk"]))
        assert "landelijke totalen" in rec["niet_geschikt_voor"]

    def test_onbekende_dekking_geeft_geen_beperking(self, nep_cbs):
        assert "niet_geschikt_voor" not in vc.enrich_entry(_bron(_geo_niveau=[]))

    def test_oud_of_archief_geeft_geen_beperking(self, nep_cbs):
        rec = vc.enrich_entry(_bron(_archief=True, _geo_niveau=["landelijk", "gemeente"]))
        assert "niet_geschikt_voor" not in rec

    def test_oude_waarde_blokkeert_herberekening_niet(self, nep_cbs):
        rec = vc.enrich_entry(_bron(_geo_niveau=["gemeente"], niet_geschikt_voor="verouderd"))
        assert "niet_geschikt_voor" not in rec


class TestDimensieSleutels:
    def test_titel_wordt_via_dataproperties_naar_key_vertaald(self, monkeypatch):
        # 85354NED: titel "Geboorteland (ouders)", officiële key GeboortelandOuders (review F6).
        aangeroepen = []
        monkeypatch.setattr(vc.client, "definitions", lambda i: {
            "GeboortelandOuders": {"title": "Geboorteland (ouders)", "type": "Dimension"},
            "Perioden": {"title": "Perioden", "type": "TimeDimension"},
        })
        monkeypatch.setattr(vc.client, "dimension", lambda i, d: aangeroepen.append(d) or {"X": "x"})
        monkeypatch.setattr(vc.time, "sleep", lambda s: None)
        rec = vc.enrich_entry(_bron(_dimensies=["Geboorteland (ouders)", "Perioden"]))
        assert aangeroepen == ["GeboortelandOuders", "Perioden"]
        assert rec["_dimensie_sleutels"] == {"Geboorteland (ouders)": "GeboortelandOuders", "Perioden": "Perioden"}
        assert "_verrijking" in rec

    def test_dimensie_onbekend_in_dataproperties_is_schemafout(self, nep_cbs):
        rec = vc.enrich_entry(_bron(_dimensies=["Bestaat niet", "Perioden"]))
        assert "_verrijking" not in rec


class TestFouten:
    def test_mislukte_refresh_behoudt_laatst_goede_afleiding_als_verouderd(self, nep_cbs):
        bestaand = vc.enrich_entry(_bron())
        rec = vc.behoud_verouderd(bestaand, _bron(_laatste_update="2027-01-01"))
        assert rec["_laatste_update"] == "2027-01-01"
        assert rec["_kolommen"] == bestaand["_kolommen"]
        assert rec["_verrijking"]["status"] == vc.VEROUDERD
        assert not vc.is_actueel(rec, _bron(_laatste_update="2027-01-01"))

    def test_gedeeltelijke_refresh_krijgt_geen_stempel(self, nep_cbs):
        nep_cbs["fail"].add("Geslacht")
        assert "_verrijking" not in vc.enrich_entry(_bron())

    def test_volledige_refresh_krijgt_stempel(self, nep_cbs):
        assert "_verrijking" in vc.enrich_entry(_bron())


class TestGeleverdeData:
    """De wheel levert dezelfde bestanden als het bouwartefact in data/02-prepared."""

    @pytest.mark.parametrize("naam", [
        "cbs_datasets.json", "cbs_datasets_ai.json", "cbs_datasets_enriched.json",
    ])
    def test_wheel_data_gelijk_aan_bouwartefact(self, naam):
        assert filecmp.cmp(
            ROOT / "data/02-prepared" / naam,
            ROOT / "src/onderwijsdata/data" / naam,
            shallow=False,
        )

    def test_enriched_volgt_bronmetadata_van_ai_catalogus(self):
        ai = {e["_cbs_id"]: e for e in json.loads((ROOT / "data/02-prepared/cbs_datasets_ai.json").read_text())}
        enriched = json.loads((ROOT / "data/02-prepared/cbs_datasets_enriched.json").read_text())
        assert {e["_cbs_id"] for e in enriched} == set(ai)
        afwijkend = [
            (e["_cbs_id"], veld)
            for e in enriched
            for veld in ("_laatste_update", "_archief", "_meetwaarden", "_dimensies")
            if e.get(veld) != ai[e["_cbs_id"]].get(veld)
        ]
        assert afwijkend == []

    def test_geen_beperking_zonder_gecontroleerde_regel(self):
        enriched = json.loads((ROOT / "data/02-prepared/cbs_datasets_enriched.json").read_text())
        for e in enriched:
            if e.get("niet_geschikt_voor"):
                assert e["_geo_niveau"] == ["landelijk"], e["_cbs_id"]
