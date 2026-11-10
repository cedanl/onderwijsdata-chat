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
    regels = (ROOT / "Dockerfile").read_text().splitlines()
    return {
        m.group(1).rstrip("/")
        for r in regels
        if (m := re.match(r"COPY\s+(?!--from)(\S+)\s+\./(?:\S*)\s*$", r)) and not r.startswith("COPY --from")
    }


def test_elke_root_module_wordt_gekopieerd():
    modules = {p.name for p in ROOT.glob("*.py")} - GEEN_RUNTIME
    ontbreekt = sorted(modules - _gekopieerd())
    assert not ontbreekt, f"niet in het image (COPY in de Dockerfile ontbreekt): {ontbreekt}"


def test_elk_pakket_met_init_wordt_gekopieerd():
    pakketten = {p.parent.name for p in ROOT.glob("*/__init__.py")} - {"tests"}
    ontbreekt = sorted(pakketten - _gekopieerd())
    assert not ontbreekt, f"niet in het image (COPY in de Dockerfile ontbreekt): {ontbreekt}"
