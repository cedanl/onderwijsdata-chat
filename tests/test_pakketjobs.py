"""De geplande pakketjobs in .gitlab-ci.yml (#887): de GitHub Actions van de oude pakketrepo's, nu in GitLab.

Een geplande pipeline bouwt en rolt niets uit; elke taak draait alleen in een schema of een handmatige run met haar
eigen variabele. Wat de Actions op main pushten, gaat via scripts/pakketbot.py als MR; bevindingen als issue.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
JOBS = {
    "cbs:laatste-update": "$LAATSTE_UPDATE",
    "catalogus:site": "$CATALOGUS_SITE",
    "cbs:discovery": "$BRONCONTROLE",
    "rio:broncontrole": "$BRONCONTROLE",
}


@pytest.fixture(scope="module")
def ci() -> dict:
    return yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text())


def _script(job: dict) -> str:
    return "\n".join(job["script"])


@pytest.mark.parametrize(("naam", "variabele"), JOBS.items())
def test_elke_pakketjob_draait_alleen_gepland_of_met_de_hand_met_zijn_variabele(ci, naam, variabele):
    voorwaarden = [r["if"] for r in ci[naam]["rules"]]
    assert len(voorwaarden) == 2
    for voorwaarde in voorwaarden:
        assert f'{variabele} == "1"' in voorwaarde
        assert '$CI_PIPELINE_SOURCE == "schedule"' in voorwaarde or '$CI_PIPELINE_SOURCE == "web"' in voorwaarde


@pytest.mark.parametrize("naam", JOBS)
def test_elke_pakketjob_controleert_eerst_het_token(ci, naam):
    assert ci[naam]["script"][0] == "uv run python scripts/pakketbot.py controleer"


def test_het_token_staat_nergens_in_de_yaml_behalve_als_naam():
    tekst = (ROOT / ".gitlab-ci.yml").read_text()
    assert "PAKKETBOT_TOKEN" in tekst
    assert "$PAKKETBOT_TOKEN" not in tekst and "${PAKKETBOT_TOKEN}" not in tekst


def test_de_mr_jobs_hebben_git_en_lopen_nooit_tegelijk(ci):
    basis = ci[".pakketbot-mr"]
    assert basis["resource_group"] == "pakketcatalogus"
    assert any("install" in regel and "git" in regel for regel in basis["before_script"])
    assert basis["before_script"][-1] == "uv sync --frozen"
    for naam in ("cbs:laatste-update", "catalogus:site"):
        assert ci[naam]["extends"] == ".pakketbot-mr"


def test_de_wekelijkse_laatste_update_doorloopt_de_hele_keten_voor_de_mr(ci):
    """Uit de pakketrepo (review F2): pas na afleiding, validatie, publicatie en tests komt er iets op main."""
    script = _script(ci["cbs:laatste-update"])
    stappen = [
        "scripts/update_laatste_update.py",
        "catalogus/verrijk_catalogus.py",
        "catalogus/verrijk_tableinfo.py",
        "catalogus/bouw_artefact.py",
        "pytest",
        "scripts/pakketbot.py mr",
    ]
    posities = [script.index(s) for s in stappen]
    assert posities == sorted(posities)
    for pad in (
        "packages/onderwijsdata/data/02-prepared",
        "packages/onderwijsdata/src/onderwijsdata/data",
        "packages/onderwijsdata/docs/catalogus_manifest.json",
    ):
        assert pad in script


def test_de_site_job_publiceert_via_bouwartefact_en_kopieert_niet_zelf(ci):
    script = _script(ci["catalogus:site"])
    assert "catalogus/bouw_artefact.py" in script and "catalogus/exporteer_site.py" in script
    assert "scripts/catalogussite.py" in script
    assert "cp " not in script
    assert "packages/onderwijsdata/docs" in script and "packages/riodata/docs" in script


def test_discovery_bewaart_het_rapport_en_meldt_via_een_issue(ci):
    job = ci["cbs:discovery"]
    assert "catalogus/discovery_diff.py" in _script(job) and "meld-discovery" in _script(job)
    assert job["artifacts"]["paths"] == ["packages/onderwijsdata/data/03-output/cbs_discovery.json"]


def test_de_broncontrole_houdt_het_manifest_van_de_vorige_controle_in_de_cache(ci):
    job = ci["rio:broncontrole"]
    manifest = "packages/riodata/catalogus/bronmanifest.json"
    assert any(manifest in c["paths"] for c in job["cache"])
    assert all(c.get("when", "on_success") == "on_success" for c in job["cache"])
    script = _script(job)
    assert "--schrijf" in script and '--code "$code"' in script and "|| code=$?" in script


def test_de_oude_github_workflows_staan_niet_meer_in_de_pakketten():
    """GitHub voert alleen root-workflows uit: in packages/ waren ze dood en dubbel met deze jobs."""
    assert not list((ROOT / "packages").glob("*/.github"))
