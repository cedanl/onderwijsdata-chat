"""
Tests voor CBS-05: gevalideerd bouwartefact, manifest en package-consistentie.
"""
import json
import shutil
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "catalogus"))

import pytest
import bouw_artefact as ba
import onderwijsdata as od

ROOT = Path(__file__).parent.parent
PREPARED = ROOT / "data/02-prepared"
PACKAGE = ROOT / "src/onderwijsdata/data"


@pytest.fixture
def prep(tmp_path):
    """Kopie van de bouwbestanden die vrij gewijzigd mag worden."""
    dst = tmp_path / "prepared"
    dst.mkdir()
    for naam in ba.PACKAGE_BESTANDEN:
        shutil.copy(PREPARED / naam, dst / naam)
    return dst


def _wijzig(pad: Path, fn):
    data = json.loads(pad.read_text(encoding="utf-8"))
    fn(data)
    pad.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class TestValidatie:
    def test_echte_data_is_geldig(self):
        fouten, _ = ba.valideer(PREPARED)
        assert fouten == []

    def test_ontbrekend_bestand(self, prep):
        (prep / "cbs_tableinfo.json").unlink()
        assert any("cbs_tableinfo.json: ontbreekt" in f for f in ba.valideer(prep)[0])

    def test_ongeldige_json(self, prep):
        (prep / "cbs_datasets.json").write_text("{kapot", encoding="utf-8")
        assert any("ongeldige JSON" in f for f in ba.valideer(prep)[0])

    def test_leeg_bestand(self, prep):
        (prep / "cbs_datasets.json").write_text("[]", encoding="utf-8")
        assert any("leeg" in f for f in ba.valideer(prep)[0])

    def test_id_verschil_tussen_bestanden(self, prep):
        _wijzig(prep / "cbs_datasets_enriched.json", lambda d: d.pop())
        assert any("ID's wijken af" in f for f in ba.valideer(prep)[0])

    def test_dubbele_ids(self, prep):
        _wijzig(prep / "cbs_datasets.json", lambda d: d.append(dict(d[0])))
        assert any("dubbele" in f for f in ba.valideer(prep)[0])

    def test_enriched_die_bron_niet_volgt(self, prep):
        def stale(d):
            d[0]["_laatste_update"] = "1999-01-01"
        _wijzig(prep / "cbs_datasets_enriched.json", stale)
        assert any("_laatste_update volgt de bron niet" in f for f in ba.valideer(prep)[0])

    def test_nieuwe_periode_in_bron_zonder_verrijking_blokkeert(self, prep, tmp_path):
        # Herverificatie H2: alleen periode wijzigen in de AI-catalogus mocht ongemerkt 'vers' publiceren.
        _wijzig(prep / "cbs_datasets_ai.json",
                lambda d: next(r for r in d if r["_cbs_id"] == "85423NED").update({"periode": "2011/'12 - 2026/'27"}))
        assert any("85423NED: periode volgt de bron niet" in f for f in ba.valideer(prep)[0])
        with pytest.raises(ValueError):
            ba.publiceer(prep, tmp_path / "pkg", tmp_path / "docs")
        assert not (tmp_path / "pkg").exists()

    def test_gesynchroniseerde_bronlaag_met_oude_stempel_blokkeert(self, prep):
        def nieuwe_periode(d):
            next(r for r in d if r["_cbs_id"] == "85423NED").update({"periode": "2011/'12 - 2026/'27"})
        _wijzig(prep / "cbs_datasets_ai.json", nieuwe_periode)
        _wijzig(prep / "cbs_datasets_enriched.json", nieuwe_periode)
        assert any("85423NED: afleiding hoort niet bij de bron" in f for f in ba.valideer(prep)[0])

    def test_expliciet_verouderde_afleiding_is_waarschuwing(self, prep):
        def nieuwe_periode(d):
            next(r for r in d if r["_cbs_id"] == "85423NED").update({"periode": "2011/'12 - 2026/'27"})

        def markeer(d):
            nieuwe_periode(d)
            next(r for r in d if r["_cbs_id"] == "85423NED")["_verrijking"]["status"] = "verouderd"
        _wijzig(prep / "cbs_datasets_ai.json", nieuwe_periode)
        _wijzig(prep / "cbs_datasets_enriched.json", markeer)
        fouten, waarschuwingen = ba.valideer(prep)
        assert fouten == [] and any("1 enriched-records met verouderde afleiding" in w for w in waarschuwingen)

    def test_meetwaarde_zonder_details(self, prep):
        def kapot(d):
            rec = next(r for r in d if r.get("_meetwaarden"))
            rec["_meetwaarden_details"] = {}
        _wijzig(prep / "cbs_datasets_enriched.json", kapot)
        assert any("zonder details" in f for f in ba.valideer(prep)[0])

    def test_onvolledige_afleiding_is_waarschuwing_geen_fout(self):
        fouten, waarschuwingen = ba.valideer(PREPARED)
        assert fouten == [] and isinstance(waarschuwingen, list)


class TestPubliceren:
    def test_succes_kopieert_exact_en_schrijft_manifest(self, prep, tmp_path):
        pkg, docs = tmp_path / "pkg", tmp_path / "docs"
        m = ba.publiceer(prep, pkg, docs)
        for naam in ba.PACKAGE_BESTANDEN:
            assert (pkg / naam).read_bytes() == (prep / naam).read_bytes()
        assert (pkg / ba.MANIFEST).read_bytes() == (prep / ba.MANIFEST).read_bytes()
        assert (docs / "data.json").read_bytes() == (prep / "cbs_datasets_ai.json").read_bytes()
        assert json.loads((docs / "catalogus_manifest.json").read_text())["catalogusrevisie"] == m["catalogusrevisie"]

    def test_mislukte_refresh_behoudt_laatst_goede_artefact(self, prep, tmp_path):
        pkg = tmp_path / "pkg"
        ba.publiceer(prep, pkg)
        voor = {p.name: p.read_bytes() for p in pkg.iterdir()}

        _wijzig(prep / "cbs_datasets_enriched.json", lambda d: d.pop())
        with pytest.raises(ValueError, match="laatst-goede"):
            ba.publiceer(prep, pkg)
        assert {p.name: p.read_bytes() for p in pkg.iterdir()} == voor

    def test_geen_tmp_bestanden_achter(self, prep, tmp_path):
        ba.publiceer(prep, tmp_path / "pkg")
        assert not list((tmp_path / "pkg").glob("*.tmp"))

    def test_deterministisch(self, prep, tmp_path):
        een = ba.publiceer(prep, tmp_path / "a")
        twee = ba.publiceer(prep, tmp_path / "b")
        assert een == twee
        assert (tmp_path / "a" / ba.MANIFEST).read_bytes() == (tmp_path / "b" / ba.MANIFEST).read_bytes()

    def test_revisie_verandert_bij_inhoudswijziging(self, prep, tmp_path):
        een = ba.publiceer(prep, tmp_path / "a")["catalogusrevisie"]
        _wijzig(prep / "cbs_datasets.json", lambda d: d[0].update({"periode": "gewijzigd"}))
        twee = ba.publiceer(prep, tmp_path / "b")["catalogusrevisie"]
        assert een != twee


class TestManifestInhoud:
    @pytest.fixture
    def manifest(self):
        return json.loads((PREPARED / ba.MANIFEST).read_text(encoding="utf-8"))

    def test_verplichte_velden(self, manifest):
        assert {"schema_version", "generator", "catalogusrevisie", "bestanden", "aantallen",
                "datadekking", "bronwijziging", "laatste_succesvolle_controle",
                "metadataherkomst", "waarschuwingen"} <= set(manifest)

    def test_aantallen_breed_en_per_scopeprofiel(self, manifest):
        a = manifest["aantallen"]
        assert a["breed"] == len(od.catalog()) and set(a["per_scopeprofiel"]) == {"mbo", "hbo", "wo", "review"}

    def test_dekking_bronwijziging_en_controle_zijn_aparte_velden(self, manifest):
        assert "gearchiveerd" in manifest["datadekking"]
        assert "laatste_update_max" in manifest["bronwijziging"]
        assert isinstance(manifest["laatste_succesvolle_controle"], str)

    def test_geen_commit_en_geen_bouwtijdstip(self, manifest):
        platte_tekst = json.dumps(manifest).lower()
        assert "commit" not in platte_tekst and "built_at" not in platte_tekst and "bouwtijd" not in platte_tekst


class TestGeleverdPackage:
    def test_geleverde_bestanden_zijn_het_gevalideerde_bouwartefact(self):
        for naam in (*ba.PACKAGE_BESTANDEN, ba.MANIFEST):
            assert (PACKAGE / naam).read_bytes() == (PREPARED / naam).read_bytes(), naam

    def test_chat_ziet_offline_welke_catalogus_hij_gebruikt(self):
        m = od.catalog_manifest()
        assert m["consistent"] is True
        assert m["catalogusrevisie"] == m["bouw"]["catalogusrevisie"]
        assert m["bouw"]["bestanden"]["cbs_datasets_enriched.json"]["records"] == m["aantal"]

    def test_inconsistent_als_bestand_afwijkt(self, monkeypatch):
        from onderwijsdata import contract
        monkeypatch.setattr(contract, "_geleverde_hashes", lambda: {"cbs_datasets.json": "x"})
        assert contract.catalog_manifest()["consistent"] is False

    def test_zonder_manifest_geen_revisie_en_niet_consistent(self, monkeypatch):
        from onderwijsdata import contract
        monkeypatch.setattr(contract, "_bouwmanifest", lambda: None)
        m = contract.catalog_manifest()
        assert m["catalogusrevisie"] is None and m["consistent"] is False

    def test_broncheck_in_record_uit_tableinfo(self):
        assert od.get_dataset("85423NED")["herkomst"]["broncheck"]


class TestRefreshketen:
    """Review F2: de wekelijkse wijzigingsroute moet de artefacten consistent houden."""

    @staticmethod
    def _wekelijkse_bronupdate(prep: Path) -> None:
        # Wat scripts/update_laatste_update.py doet: alleen de AI-catalogus wijzigt.
        _wijzig(prep / "cbs_datasets_ai.json",
                lambda d: next(r for r in d if r["_cbs_id"] == "85423NED").update({"_laatste_update": "2027-01-01"}))

    def test_alleen_bronupdate_zonder_keten_is_inconsistent(self, prep):
        self._wekelijkse_bronupdate(prep)
        assert any("_laatste_update volgt de bron niet" in f for f in ba.valideer(prep)[0])

    def test_complete_keten_met_bronuitval_blijft_publiceerbaar(self, prep, tmp_path, monkeypatch):
        import verrijk_catalogus as vc

        def onbereikbaar(*_a, **_k):
            raise RuntimeError("CBS onbereikbaar")

        monkeypatch.setattr(vc.client, "definitions", onbereikbaar)
        monkeypatch.setattr(vc.client, "dimension", onbereikbaar)
        monkeypatch.setattr(vc.time, "sleep", lambda s: None)
        self._wekelijkse_bronupdate(prep)
        monkeypatch.setattr(sys, "argv", ["verrijk_catalogus.py", "--input", str(prep / "cbs_datasets_ai.json"),
                                          "--output", str(prep / "cbs_datasets_enriched.json")])
        vc.main()

        rec = next(r for r in json.loads((prep / "cbs_datasets_enriched.json").read_text())
                   if r["_cbs_id"] == "85423NED")
        assert rec["_laatste_update"] == "2027-01-01"
        assert rec["_verrijking"]["status"] == "verouderd" and rec["_kolommen"]

        fouten, waarschuwingen = ba.valideer(prep)
        assert fouten == [] and any("verouderde afleiding" in w for w in waarschuwingen)
        m = ba.publiceer(prep, tmp_path / "pkg", tmp_path / "docs")
        assert m["versheid"]["afleiding_verouderd"] == 1
        for naam, b in m["bestanden"].items():
            assert ba._sha(tmp_path / "pkg" / naam) == b["sha256"]

    def test_wekelijkse_workflow_doorloopt_de_hele_keten(self):
        wf = (ROOT / ".github/workflows/update-laatste-update.yml").read_text()
        stappen = ["scripts/update_laatste_update.py", "catalogus/verrijk_catalogus.py",
                   "catalogus/verrijk_tableinfo.py", "catalogus/bouw_artefact.py", "pytest", "git commit"]
        posities = [wf.index(s) for s in stappen]
        assert posities == sorted(posities)
        assert "src/onderwijsdata/data/" in wf and "docs/catalogus_manifest.json" in wf

    def test_siteworkflow_publiceert_via_bouwartefact(self):
        wf = (ROOT / ".github/workflows/update-catalogus.yml").read_text()
        assert "catalogus/bouw_artefact.py" in wf and "data/02-prepared/**" in wf
        assert "cp data/02-prepared" not in wf


class TestVersheid:
    def test_manifest_meldt_oudste_controle_en_verouderd(self):
        v = json.loads((PREPARED / ba.MANIFEST).read_text(encoding="utf-8"))["versheid"]
        assert {"oudste_controle", "perioden_verouderd", "perioden_onbekend",
                "afleiding_onvolledig", "afleiding_verouderd"} <= set(v)

    def test_verouderde_perioden_geven_waarschuwing(self, prep):
        _wijzig(prep / "cbs_tableinfo.json", lambda d: d[0]["perioden"].update({"status": "verouderd"}))
        fouten, waarschuwingen = ba.valideer(prep)
        assert fouten == [] and any("perioden: 1 verouderd" in w for w in waarschuwingen)
