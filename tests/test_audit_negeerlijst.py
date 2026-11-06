"""De bewust genegeerde CVE's van `audit:python` staan in SECURITY.md S12, met reden (#972).

Een CVE op de lijst zonder beoordeling, of een beoordeling die de job niet toepast, laat de job zwijgen over iets dat
niemand bekeek, of rood worden op iets dat al besloten is.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CVE = re.compile(r"CVE-\d{4}-\d+")


def _genegeerd_in_ci() -> set[str]:
    job = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text())["audit:python"]
    script = "\n".join(job["script"])
    return set(re.findall(r"--ignore-vuln\s+(CVE-\d{4}-\d+)", script))


def _beoordeeld_in_s12() -> set[str]:
    tekst = (ROOT / "SECURITY.md").read_text()
    sectie = tekst.split("### S12 ")[1].split("\n### ")[0]
    return set(CVE.findall(sectie))


def test_de_job_negeert_precies_wat_s12_beoordeelt():
    assert _genegeerd_in_ci() == _beoordeeld_in_s12()
