"""Eén versiebron en README-aantallen die uit de catalogus komen."""
import re
import tomllib
from pathlib import Path

import onderwijsbronnen

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_runtimeversie_is_distributieversie():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert onderwijsbronnen.__version__ == pyproject["project"]["version"]
    assert onderwijsbronnen.cbs.__version__ == onderwijsbronnen.__version__  # één pakket, één versie (#910)


def test_versie_staat_niet_hardcoded_in_code():
    versie = (ROOT / "src" / "onderwijsbronnen" / "_kern" / "versie.py").read_text(encoding="utf-8")
    assert 'version("onderwijsbronnen")' in versie


def _aantal(patroon: str) -> int:
    m = re.search(patroon, README)
    assert m, f"README mist regel voor: {patroon}"
    return int(m.group(1))


def test_readme_aantallen_komen_uit_de_catalogus():
    assert _aantal(r'source="rio"\)\s+# (\d+) RIO') == len(onderwijsbronnen.catalog("rio"))
    assert _aantal(r'source="duo"\)\s+# (\d+) DUO') == len(onderwijsbronnen.catalog("duo"))
    assert _aantal(r'source="all"\)\s+# (\d+) gecombineerd') == len(onderwijsbronnen.catalog("all"))
    assert _aantal(r"\*\*DUO Open Data\*\* — (\d+) datasets") == len(onderwijsbronnen.catalog("duo"))
    assert _aantal(r"\*\*RIO LOD API v3\*\*.*\((\d+) resources") == len(onderwijsbronnen.catalog("rio"))
    assert _aantal(r"\*\*ROA\*\* — .*\((\d+) datasets\)") == len(onderwijsbronnen.catalog("roa"))
    assert _aantal(r"\*\*UWV\*\* — .*\((\d+) dataset\)") == len(onderwijsbronnen.catalog("uwv"))
    assert _aantal(r"\*\*Inspectie van het Onderwijs\*\* — .*\((\d+) datasets\)") == len(onderwijsbronnen.catalog("inspectie"))
    assert _aantal(r"\*\*SBB\*\* — .*\((\d+) datasets\)") == len(onderwijsbronnen.catalog("sbb"))


def test_claude_md_aantallen_komen_uit_de_catalogus():
    tekst = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for n in re.findall(r'source="all"\)\s+# (\d+) gecombineerd', tekst):
        assert int(n) == len(onderwijsbronnen.catalog("all"))
    for n in re.findall(r'source="duo"\)\s+# (\d+) DUO', tekst):
        assert int(n) == len(onderwijsbronnen.catalog("duo"))


def test_elke_extra_staat_in_de_readme():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    for extra in pyproject["project"].get("optional-dependencies", {}):
        assert f"onderwijsbronnen[{extra}]" in README, f"extra '{extra}' ontbreekt in README"
