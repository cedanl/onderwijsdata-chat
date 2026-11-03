"""Tests voor skip- en schrijflogica van catalogus/verrijk_catalogus.py (zonder netwerk)."""
import json
import sys
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "catalogus"))

import verrijk_catalogus as vc  # noqa: E402
from riodata import _catalog  # noqa: E402
from riodata._catalog import STAMP, VERRIJKT_DUO  # noqa: E402


def _args(**kw) -> Namespace:
    return Namespace(no_skip_existing=False, limit=None, annotaties=False, **kw)


def _fake_enrich(aanroepen: list):
    def enrich(entry: dict, annotaties: bool = False) -> dict:
        aanroepen.append(entry["_ckan_id"])
        entry["_kolommen"] = {"A": "numeriek (bereik: 1-2)"}
        entry["_kolomtypes"] = {"A": "numeriek"}
        if annotaties:
            entry["samenvatting"] = "s"
        return entry

    return enrich


def _run(tmp_path, entries, args=None, enrich=None):
    out = tmp_path / "enriched.json"
    aanroepen: list = []
    vc.process_source(entries, enrich or _fake_enrich(aanroepen), out, args or _args(), "TEST", VERRIJKT_DUO)
    return json.loads(out.read_text(encoding="utf-8")), aanroepen


def test_verse_run_stempelt_verrijking(tmp_path):
    data, aanroepen = _run(tmp_path, [{"_ckan_id": "a", "bron": "A"}])
    assert aanroepen == ["a"]
    assert data[0][STAMP]["input_sha256"] == _catalog.input_hash({"_ckan_id": "a", "bron": "A"}, VERRIJKT_DUO)


def test_tweede_run_met_ongewijzigde_bron_slaat_over_en_is_idempotent(tmp_path):
    entries = [{"_ckan_id": "a", "bron": "A"}]
    eerste, _ = _run(tmp_path, entries)
    tweede, aanroepen = _run(tmp_path, entries)
    assert aanroepen == []
    assert tweede == eerste


def test_gewijzigde_bron_wordt_ondanks_kolomtypes_opnieuw_verrijkt(tmp_path):
    _run(tmp_path, [{"_ckan_id": "a", "bron": "A", "periode": "2020"}])
    data, aanroepen = _run(tmp_path, [{"_ckan_id": "a", "bron": "A", "periode": "2021"}])
    assert aanroepen == ["a"]
    assert data[0]["periode"] == "2021"


def test_verrijking_zonder_stempel_wordt_opnieuw_gemaakt(tmp_path):
    (tmp_path / "enriched.json").write_text(
        json.dumps([{"_ckan_id": "a", "_kolomtypes": {"A": "oud"}}]), encoding="utf-8"
    )
    data, aanroepen = _run(tmp_path, [{"_ckan_id": "a", "bron": "A"}])
    assert aanroepen == ["a"]
    assert data[0]["_kolomtypes"] == {"A": "numeriek"}


def test_no_skip_existing_forceert_migratie(tmp_path):
    entries = [{"_ckan_id": "a", "bron": "A"}]
    _run(tmp_path, entries)
    _, aanroepen = _run(tmp_path, entries, _args_force())
    assert aanroepen == ["a"]


def _args_force() -> Namespace:
    return Namespace(no_skip_existing=True, limit=None, annotaties=False)


def test_uitvoer_bevat_geen_verouderde_bronvelden(tmp_path):
    out = tmp_path / "enriched.json"
    out.write_text(
        json.dumps([{"_ckan_id": "a", "bron": "OUD", "_kolomtypes": {"A": "x"}}]), encoding="utf-8"
    )
    data, _ = _run(tmp_path, [{"_ckan_id": "a", "bron": "NIEUW"}])
    assert data[0]["bron"] == "NIEUW"


def test_annotaties_staan_standaard_uit(tmp_path):
    data, _ = _run(tmp_path, [{"_ckan_id": "a", "bron": "A"}])
    assert "samenvatting" not in data[0] and "niet_geschikt_voor" not in data[0]


def test_annotaties_met_vlag(tmp_path):
    data, _ = _run(tmp_path, [{"_ckan_id": "a", "bron": "A"}], Namespace(no_skip_existing=False, limit=None, annotaties=True))
    assert data[0]["samenvatting"] == "s"


def test_mislukte_fetch_wordt_niet_als_actueel_gestempeld(tmp_path):
    def leeg(entry, annotaties=False):
        return entry  # geen schema-informatie opgehaald

    data, _ = _run(tmp_path, [{"_ckan_id": "a", "bron": "A"}], enrich=leeg)
    assert STAMP not in data[0]


def test_bestaande_verrijking_blijft_bij_mislukte_fetch(tmp_path):
    entries = [{"_ckan_id": "a", "bron": "A"}]
    eerste, _ = _run(tmp_path, entries)
    entries[0]["periode"] = "2031"

    def leeg(entry, annotaties=False):
        return entry

    data, _ = _run(tmp_path, entries, enrich=leeg)
    assert data[0]["_kolomtypes"] == {"A": "numeriek"}
    assert data[0][STAMP] == eerste[0][STAMP]  # oude stempel: blijft zichtbaar verouderd


# ── Review F1: bronstoring, deelresultaten en vervangen van de afgeleide laag ──

def _echt_basisrecord(ckan_id="p01hoinges"):
    from importlib.resources import files
    base = json.loads(files("riodata.data").joinpath("duo_resources.json").read_text(encoding="utf-8"))
    return next(r for r in base if r["_ckan_id"] == ckan_id)


def test_bronstoring_wordt_niet_als_actueel_gestempeld_met_echt_basisrecord(tmp_path, monkeypatch):
    """Route 2: duo.resources() faalt; het oude basisschema mag niet als vers schema tellen."""
    from riodata import duo

    def stuk(dataset_id):
        raise RuntimeError("CKAN down")

    monkeypatch.setattr(duo, "resources", stuk)
    entry = _echt_basisrecord()
    assert "_kolommen" in entry
    data, _ = _run(tmp_path, [entry], enrich=vc.enrich_duo_entry)
    assert STAMP not in data[0] and "_kolommen" not in data[0]
    assert _catalog.verrijking_status(entry, data[0], VERRIJKT_DUO) != "actueel"


def test_deelresultaat_van_resources_wordt_niet_gestempeld(tmp_path, monkeypatch):
    import pandas as pd
    from riodata import duo

    monkeypatch.setattr(duo, "resources", lambda d: [{"naam": "r1"}, {"naam": "r2"}])

    def laad(dataset_id, idx, **kw):
        if idx == 1:
            raise RuntimeError("download mislukt")
        return pd.DataFrame({"A": [1, 2]})

    monkeypatch.setattr(duo, "load", laad)
    data, _ = _run(tmp_path, [{"_ckan_id": "a", "bron": "A"}], enrich=vc.enrich_duo_entry)
    assert STAMP not in data[0] and "_kolommen" not in data[0]


def test_vervangt_afgeleide_laag_in_plaats_van_oude_sleutels_bij_te_mengen(tmp_path):
    entries = [{"_ckan_id": "a", "bron": "A", "periode": "2020"}]

    def eerste(entry, annotaties=False):
        entry.update({"_kolommen": {"OLD": "x"}, "_kolomtypes": {"OLD": "tekst"}, "_kolomdefinities": {"OLD": "definitie"}})
        return entry

    _run(tmp_path, entries, enrich=eerste)
    entries[0]["periode"] = "2021"

    def tweede(entry, annotaties=False):
        entry.update({"_kolommen": {"NEW": "x"}, "_kolomtypes": {"NEW": "tekst"}})   # geen definities
        return entry

    data, _ = _run(tmp_path, entries, enrich=tweede)
    assert data[0]["_kolommen"] == {"NEW": "x"}
    assert "_kolomdefinities" not in data[0]                  # oude definitie niet onder nieuwe stempel
    assert data[0][STAMP]["input_sha256"] == _catalog.input_hash(entries[0], VERRIJKT_DUO)


def test_lezer_krijgt_geen_afgeleide_velden_uit_de_basis_mee(tmp_path):
    gezien = {}

    def spion(entry, annotaties=False):
        gezien.update(entry)
        entry["_kolomtypes"] = {"A": "numeriek"}
        return entry

    _run(tmp_path, [{"_ckan_id": "a", "_kolommen": {"oud": 1}, "_kolomtypes": {"oud": "x"}}], enrich=spion)
    assert "_kolommen" not in gezien and "_kolomtypes" not in gezien
