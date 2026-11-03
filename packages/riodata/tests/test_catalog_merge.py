"""Tests voor het samenvoegen van bronmetadata en verrijking (riodata._catalog)."""
import json
from importlib.resources import files

import pytest

import riodata
from riodata import _catalog
from riodata._catalog import STAMP, STATUS, VERRIJKT_DUO, VERRIJKT_RIO, merge, stamp


def _basis(**extra) -> dict:
    return {"_ckan_id": "ds1", "bron": "Dataset 1", "periode": "2021-2025", **extra}


def _verrijkt(base: dict, **extra) -> dict:
    return {"_ckan_id": base["_ckan_id"], "_kolomtypes": {"A": "numeriek"}, STAMP: stamp(base, VERRIJKT_DUO), **extra}


class TestBronvelden:
    def test_bronupdate_komt_door_ondanks_bestaande_kolomtypes(self):
        oud = _basis()
        verrijking = _verrijkt(oud, periode="1999-2000")  # verouderde kopie in het enriched-bestand
        nieuw = _basis(periode="2022-2026")
        (rec,) = merge([nieuw], [{**verrijking, "periode": "1999-2000"}], VERRIJKT_DUO)
        assert rec["periode"] == "2022-2026"

    def test_nieuw_contractveld_in_basis_verschijnt(self):
        base = _basis(_teldefinitie={"teleenheid": "personen"})
        (rec,) = merge([base], [_verrijkt(_basis())], VERRIJKT_DUO)
        assert rec["_teldefinitie"] == {"teleenheid": "personen"}

    def test_afgeleide_velden_komen_uit_verrijking(self):
        base = _basis(_kolommen={"A": ["1", "2"]})
        verrijking = _verrijkt(base, _kolommen={"A": "numeriek (bereik: 1-2)"})
        (rec,) = merge([base], [verrijking], VERRIJKT_DUO)
        assert rec["_kolommen"] == {"A": "numeriek (bereik: 1-2)"}
        assert rec["_kolomtypes"] == {"A": "numeriek"}

    def test_record_zonder_verrijking_blijft_zoals_basis(self):
        (rec,) = merge([_basis()], [], VERRIJKT_DUO)
        assert rec == _basis()
        assert STATUS not in rec

    def test_verwijderd_uit_basis_verdwijnt_ook_met_verrijking(self):
        assert merge([], [_verrijkt(_basis())], VERRIJKT_DUO) == []

    def test_volgorde_volgt_basis(self):
        a, b = {"_ckan_id": "a"}, {"_ckan_id": "b"}
        assert [r["_ckan_id"] for r in merge([b, a], [a, b], VERRIJKT_DUO)] == ["b", "a"]

    def test_geen_verzonnen_velden(self):
        (rec,) = merge([_basis()], [_verrijkt(_basis())], VERRIJKT_DUO)
        assert "samenvatting" not in rec and "niet_geschikt_voor" not in rec

    def test_rio_annotaties_uit_verrijking(self):
        base = {"_rio_resource": "r1", "tags": ["a"], "voorbeeldvragen": ["oud?"]}
        verrijking = {"_rio_resource": "r1", "tags": ["a", "b"], "voorbeeldvragen": ["nieuw?"]}
        (rec,) = merge([base], [verrijking], VERRIJKT_RIO)
        assert rec["tags"] == ["a", "b"] and rec["voorbeeldvragen"] == ["nieuw?"]

    def test_idempotent(self):
        base = [_basis(_kolommen={"A": ["1"]})]
        enr = [_verrijkt(base[0], _kolommen={"A": "x"})]
        eerste = merge(base, enr, VERRIJKT_DUO)
        assert merge(base, enr, VERRIJKT_DUO) == eerste


class TestInvalidatie:
    def test_actueel_bij_passende_stempel(self):
        base = _basis()
        (rec,) = merge([base], [_verrijkt(base)], VERRIJKT_DUO)
        assert rec[STATUS] == "actueel"

    def test_gewijzigde_bron_maakt_verrijking_verouderd_en_laat_afgeleide_velden_weg(self):
        oud = _basis()
        verrijking = _verrijkt(oud, _kolommen={"A": "x"})
        (rec,) = merge([_basis(periode="2030")], [verrijking], VERRIJKT_DUO)
        assert rec[STATUS] == "verouderd"
        assert "_kolomtypes" not in rec and "_kolommen" not in rec

    def test_schemaversie_wijziging_invalideert(self, monkeypatch):
        base = _basis()
        verrijking = _verrijkt(base)
        monkeypatch.setattr(_catalog, "SCHEMA_VERSIE", _catalog.SCHEMA_VERSIE + 1)
        (rec,) = merge([base], [verrijking], VERRIJKT_DUO)
        assert rec[STATUS] == "verouderd"

    def test_verrijking_zonder_stempel_blijft_gelden_als_ongecontroleerd(self):
        base = _basis()
        (rec,) = merge([base], [{"_ckan_id": "ds1", "_kolomtypes": {"A": "numeriek"}}], VERRIJKT_DUO)
        assert rec[STATUS] == "ongecontroleerd"
        assert rec["_kolomtypes"] == {"A": "numeriek"}

    def test_verrijking_zelf_beinvloedt_de_hash_niet(self):
        base = _basis()
        assert _catalog.input_hash(base, VERRIJKT_DUO) == _catalog.input_hash(
            {**base, "_kolomtypes": {"A": "x"}, "samenvatting": "s"}, VERRIJKT_DUO
        )


class TestGecommitteerdeData:
    """Bewaakt dat de echte catalogus gelijk blijft voor wat consumenten (de chat) al lezen."""

    def _enriched(self, bestand: str) -> dict:
        data = json.loads(files("riodata.data").joinpath(bestand).read_text(encoding="utf-8"))
        return {_catalog.record_id(e): e for e in data}

    @pytest.mark.parametrize(
        "source,bestand",
        [("duo", "duo_resources_enriched.json"), ("rio", "rio_resources_enriched.json")],
    )
    def test_bestaande_enriched_waarden_blijven_identiek(self, source, bestand):
        enriched = self._enriched(bestand)
        for rec in riodata.catalog(source=source):
            for k, v in enriched[_catalog.record_id(rec)].items():
                if k in (STAMP, STATUS):
                    continue
                assert rec.get(k) == v, f"{_catalog.record_id(rec)}.{k} is veranderd"

    @pytest.mark.parametrize("source,aantal", [("duo", 56), ("rio", 14)])
    def test_aantallen_blijven_gelijk(self, source, aantal):
        assert len(riodata.catalog(source=source)) == aantal

    def test_basisvelden_die_niet_in_enriched_staan_zijn_beschikbaar(self):
        base = json.loads(files("riodata.data").joinpath("duo_resources.json").read_text(encoding="utf-8"))
        cat = {r["_ckan_id"]: r for r in riodata.catalog(source="duo")}
        for b in base:
            for k, v in b.items():
                if k == "_zoekkaart":  # krijgt bij het laden een afgeleid 'tijd'-deel uit _tijd
                    assert {kk: cat[b["_ckan_id"]][k][kk] for kk in v} == v
                elif k not in VERRIJKT_DUO:
                    assert cat[b["_ckan_id"]][k] == v

    def test_catalogus_is_deterministisch(self):
        assert riodata.catalog(source="all") == riodata.catalog(source="all")


class TestVerouderdMetBasisSchema:
    """Review F1 route 1: de echte basisrecords bevatten zelf _kolommen/_kolomtypes."""

    def _echt_basisrecord(self, ckan_id="p01hoinges"):
        base = json.loads(files("riodata.data").joinpath("duo_resources.json").read_text(encoding="utf-8"))
        return next(r for r in base if r["_ckan_id"] == ckan_id)

    def test_verouderd_laat_geen_oude_afgeleide_velden_uit_de_basis_staan(self):
        base = self._echt_basisrecord()
        assert "_kolommen" in base                                    # de echte vorm: schema zit al in de basis
        oude_verrijking = {**base, STAMP: stamp(base, VERRIJKT_DUO), "_kolommen": {"oud": 1}, "_kolomtypes": {"oud": "x"}}
        gewijzigd = {**base, "periode": "2030-2031"}
        (rec,) = merge([gewijzigd], [oude_verrijking], VERRIJKT_DUO)
        assert rec[STATUS] == "verouderd"
        for veld in _catalog.AFGELEID:
            assert veld not in rec, veld
        assert rec["periode"] == "2030-2031"          # bronvelden blijven

    def test_zonder_verrijking_blijft_het_basisschema_staan(self):
        base = self._echt_basisrecord()
        (rec,) = merge([base], [], VERRIJKT_DUO)
        assert rec["_kolommen"] == base["_kolommen"] and STATUS not in rec

    def test_annotaties_uit_de_basis_blijven_bij_verouderd(self):
        base = {"_rio_resource": "r", "tags": ["a"], "_kolomtypes": {"x": "tekst"}}
        oud = {"_rio_resource": "r", "tags": ["b"], STAMP: stamp({**base, "bron": "oud"}, VERRIJKT_RIO)}
        (rec,) = merge([base], [oud], VERRIJKT_RIO)
        assert rec[STATUS] == "verouderd" and rec["tags"] == ["a"] and "_kolomtypes" not in rec
