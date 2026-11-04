"""De catalogussites van de bronpakketten (#887): bestanden in packages/<pakket>/docs en de route op de Pages-site."""

import re
from pathlib import Path

import yaml

from scripts import catalogussite

ROOT = Path(__file__).resolve().parent.parent


def _pakket(tmp_path: Path) -> Path:
    pakket = tmp_path / "pakket"
    (pakket / "voorbeelden/output/mbo_zij_instroom").mkdir(parents=True)
    (pakket / "voorbeelden/manifest.json").write_text("[]")
    (pakket / "voorbeelden/output/trend.png").write_bytes(b"png")
    (pakket / "voorbeelden/output/trend_INTERPRETATIE.md").write_text("trend")
    (pakket / "voorbeelden/output/mbo_zij_instroom/INTERPRETATIE.md").write_text("zij")
    (pakket / "voorbeelden/output/mbo_zij_instroom/zij.png").write_bytes(b"png")
    (pakket / "voorbeelden/output/notities.txt").write_text("niet naar de site")
    return pakket


def test_voorbeelden_komen_plat_in_docs_met_de_mapnaam_voor_een_kale_interpretatie(tmp_path):
    pakket = _pakket(tmp_path)
    catalogussite.kopieer_voorbeelden(pakket)
    docs = pakket / "docs"
    assert (docs / "voorbeelden.json").read_text() == "[]"
    assert sorted(p.name for p in (docs / "voorbeelden").iterdir()) == [
        "mbo_zij_instroom_INTERPRETATIE.md",
        "trend.png",
        "trend_INTERPRETATIE.md",
        "zij.png",
    ]
    assert (docs / "voorbeelden/mbo_zij_instroom_INTERPRETATIE.md").read_text() == "zij"


def test_kopieren_is_aanvullend_zoals_in_de_oude_workflow(tmp_path):
    pakket = _pakket(tmp_path)
    (pakket / "docs/voorbeelden").mkdir(parents=True)
    (pakket / "docs/voorbeelden/oud.png").write_bytes(b"oud")
    catalogussite.kopieer_voorbeelden(pakket)
    assert (pakket / "docs/voorbeelden/oud.png").exists()


def test_riodata_krijgt_ook_de_roa_en_uwv_catalogus():
    assert catalogussite.EXTRA_BESTANDEN["riodata"] == {
        "src/riodata/data/roa_resources.json": "roa_data.json",
        "src/riodata/data/uwv_resources.json": "uwv_data.json",
    }
    for naam, extra in catalogussite.EXTRA_BESTANDEN.items():
        for bron in extra:
            assert (ROOT / "packages" / naam / bron).is_file()


def test_de_vastgelegde_sites_kloppen_met_de_bronbestanden(tmp_path):
    """Wat het script schrijft, staat al zo in packages/*/docs: de eerste geplande run geeft geen lege MR."""
    for naam in catalogussite.EXTRA_BESTANDEN:
        bron = ROOT / "packages" / naam
        docs = bron / "docs"
        assert (docs / "voorbeelden.json").read_bytes() == (bron / "voorbeelden/manifest.json").read_bytes()
        for b, doel in catalogussite.EXTRA_BESTANDEN[naam].items():
            assert (docs / doel).read_bytes() == (bron / b).read_bytes()


# --- de route op de Pages-site van de mirror ----------------------------------------------


def _docs_workflow() -> list[dict]:
    return yaml.safe_load((ROOT / ".github/workflows/docs.yml").read_text())["jobs"]["build"]["steps"]


def test_de_pages_site_van_de_mirror_publiceert_beide_catalogi_onder_catalogus():
    stappen = _docs_workflow()
    namen = [s.get("name", "") for s in stappen]
    bouw = namen.index("Build docs")
    upload = namen.index("Upload Pages artifact")
    catalogus = next(i for i, s in enumerate(stappen) if "site/catalogus" in s.get("run", ""))
    assert bouw < catalogus < upload
    run = stappen[catalogus]["run"]
    assert "cp -r packages/onderwijsdata/docs site/catalogus/cbs" in run
    assert "cp -r packages/riodata/docs site/catalogus/rio" in run


def test_de_catalogussites_laden_alles_relatief_zodat_ze_onder_een_submap_werken():
    for naam in ("onderwijsdata", "riodata"):
        html = (ROOT / "packages" / naam / "docs/index.html").read_text(encoding="utf-8")
        paden = re.findall(r"fetch\(\s*[`'\"]([^`'\"]+)", html)
        assert paden, naam
        assert all(not p.startswith(("/", "http")) for p in paden), (naam, paden)
