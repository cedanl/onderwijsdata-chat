"""De catalogussites van het bronpakket (#887, #910): bestanden in packages/onderwijsbronnen/docs/<site> en de route op
de Pages-site."""

import re
from pathlib import Path

import yaml

from scripts import catalogussite

ROOT = Path(__file__).resolve().parent.parent


def _voorbeelden(tmp_path: Path) -> Path:
    bron = tmp_path / "voorbeelden" / "cbs"
    (bron / "output/mbo_zij_instroom").mkdir(parents=True)
    (bron / "manifest.json").write_text("[]")
    (bron / "output/trend.png").write_bytes(b"png")
    (bron / "output/trend_INTERPRETATIE.md").write_text("trend")
    (bron / "output/mbo_zij_instroom/INTERPRETATIE.md").write_text("zij")
    (bron / "output/mbo_zij_instroom/zij.png").write_bytes(b"png")
    (bron / "output/notities.txt").write_text("niet naar de site")
    return bron


def test_voorbeelden_komen_plat_in_docs_met_de_mapnaam_voor_een_kale_interpretatie(tmp_path):
    docs = tmp_path / "docs" / "cbs"
    catalogussite.kopieer_voorbeelden(_voorbeelden(tmp_path), docs)
    assert (docs / "voorbeelden.json").read_text() == "[]"
    assert sorted(p.name for p in (docs / "voorbeelden").iterdir()) == [
        "mbo_zij_instroom_INTERPRETATIE.md",
        "trend.png",
        "trend_INTERPRETATIE.md",
        "zij.png",
    ]
    assert (docs / "voorbeelden/mbo_zij_instroom_INTERPRETATIE.md").read_text() == "zij"


def test_kopieren_is_aanvullend_zoals_in_de_oude_workflow(tmp_path):
    docs = tmp_path / "docs" / "cbs"
    (docs / "voorbeelden").mkdir(parents=True)
    (docs / "voorbeelden/oud.png").write_bytes(b"oud")
    catalogussite.kopieer_voorbeelden(_voorbeelden(tmp_path), docs)
    assert (docs / "voorbeelden/oud.png").exists()


def test_de_rio_site_krijgt_ook_de_roa_en_uwv_catalogus():
    assert catalogussite.EXTRA_BESTANDEN["rio"] == {
        "src/onderwijsbronnen/roa/data/roa_resources.json": "roa_data.json",
        "src/onderwijsbronnen/uwv/data/uwv_resources.json": "uwv_data.json",
    }
    for extra in catalogussite.EXTRA_BESTANDEN.values():
        for bron in extra:
            assert (catalogussite.PAKKET / bron).is_file()


def test_de_vastgelegde_sites_kloppen_met_de_bronbestanden(tmp_path):
    """Wat het script schrijft, staat al zo in docs/<site>: de eerste geplande run geeft geen lege MR."""
    pakket = catalogussite.PAKKET
    for site, extra in catalogussite.EXTRA_BESTANDEN.items():
        docs = pakket / "docs" / site
        assert (docs / "voorbeelden.json").read_bytes() == (
            pakket / "voorbeelden" / site / "manifest.json"
        ).read_bytes()
        for b, doel in extra.items():
            assert (docs / doel).read_bytes() == (pakket / b).read_bytes()


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
    assert "cp -r packages/onderwijsbronnen/docs/cbs site/catalogus/cbs" in run
    assert "cp -r packages/onderwijsbronnen/docs/rio site/catalogus/rio" in run


def test_de_catalogussites_laden_alles_relatief_zodat_ze_onder_een_submap_werken():
    for naam in ("cbs", "rio"):
        html = (catalogussite.PAKKET / "docs" / naam / "index.html").read_text(encoding="utf-8")
        paden = re.findall(r"fetch\(\s*[`'\"]([^`'\"]+)", html)
        assert paden, naam
        assert all(not p.startswith(("/", "http")) for p in paden), (naam, paden)
