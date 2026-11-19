"""Elke module in de root en elk pakket dat de app importeert, zit in het runtime-image.

#706 voegde `mcp_server.py` toe zonder `COPY` in de Dockerfile: de tests draaien op de checkout en bleven groen, maar
de pod op test kwam niet op ("No module named 'mcp_server'", CrashLoopBackOff).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# De root-modules van de app; wat hier ontbreekt, hoort niet in het image (tests, scripts, tooling).
GEEN_RUNTIME = {"conftest.py"}


def _gekopieerd() -> set[str]:
    """De bronnen van elke COPY uit de checkout (niet uit een andere stage: `--from`), los van vlaggen als `--chown`."""
    uit = set()
    for r in (ROOT / "Dockerfile").read_text().splitlines():
        if not (m := re.match(r"COPY\s+((?:--\S+\s+)*)(\S+)\s+\./(?:\S*)\s*$", r)):
            continue
        if "--from" not in m.group(1):
            uit.add(m.group(2).rstrip("/"))
    return uit


def _runtime_stage() -> list[str]:
    """De regels van de laatste stage: het image dat draait."""
    regels = (ROOT / "Dockerfile").read_text().splitlines()
    begin = max(i for i, r in enumerate(regels) if r.startswith("FROM "))
    return regels[begin:]


def test_de_runtime_stage_geeft_de_bestanden_bij_het_kopieren_aan_appuser():
    """Geen `chown -R /app` aan het eind: dat kostte op de CI-runner 650 s per build en zette elk bestand nog eens in een
    eigen laag. Elke COPY geeft de bestanden meteen aan appuser, en de gebruiker bestaat vóór de eerste COPY."""
    stage = _runtime_stage()
    assert not [r for r in stage if not r.lstrip().startswith("#") and re.search(r"chown\s+-R", r)]
    copies = [i for i, r in enumerate(stage) if r.startswith("COPY ")]
    assert copies
    assert all("--chown=appuser:appuser" in stage[i] for i in copies)
    useradd = next(i for i, r in enumerate(stage) if "useradd" in r)
    assert useradd < copies[0]
    assert any(r.strip() == "USER appuser" for r in stage)


def test_elke_root_module_wordt_gekopieerd():
    modules = {p.name for p in ROOT.glob("*.py")} - GEEN_RUNTIME
    ontbreekt = sorted(modules - _gekopieerd())
    assert not ontbreekt, f"niet in het image (COPY in de Dockerfile ontbreekt): {ontbreekt}"


def test_elk_pakket_met_init_wordt_gekopieerd():
    pakketten = {p.parent.name for p in ROOT.glob("*/__init__.py")} - {"tests"}
    ontbreekt = sorted(pakketten - _gekopieerd())
    assert not ontbreekt, f"niet in het image (COPY in de Dockerfile ontbreekt): {ontbreekt}"


def test_het_wordsjabloon_zit_in_het_image():
    """Het rapport als Word-document (#1038) leest templates/rapport.docx bij elk verzoek."""
    from tools.rapport_docx.render import SJABLOON

    assert SJABLOON.relative_to(ROOT).parts[0] in _gekopieerd()
