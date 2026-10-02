"""Voorbeeldtitels in prompts en docs zijn de catalogustitel (#204).

De prompt eist de exacte titel uit de catalogus, maar een voorbeeld noemde 85423NED als
"MBO; deelnemers naar geslacht en niveau" terwijl het "Hoger onderwijs; ingeschrevenen, …" is:
het model leest voorbeelden als waarheid.
"""
import re
from pathlib import Path

import pytest

from tools.catalog import catalogus_titel

ROOT = Path(__file__).resolve().parent.parent
FILES = sorted([*ROOT.glob("prompts/*.md"), *ROOT.glob("docs/**/*.md"), ROOT / "README.md"])

# Een bronvermelding: "- CBS dataset 85423NED — *Titel*" of "- DUO — *Titel* (**p02ho1ejrs**)".
_BRON_REGEL = re.compile(r"^\s*[-*]\s+(?:CBS|DUO|RIO)\b.*—.*\*[^*]+\*")
_DATASET_ID = re.compile(r"\b(\d{5}(?:NED|ENG)|p\d{2}[a-z0-9]{3,})\b")
_CURSIEF = re.compile(r"(?<!\*)\*([^*]{8,}?)\*(?!\*)")


def _bronregels():
    for path in FILES:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _BRON_REGEL.search(line) and (ids := set(_DATASET_ID.findall(line))):
                yield pytest.param(path.relative_to(ROOT), number, line, ids, id=f"{path.name}:{number}")


@pytest.mark.parametrize(("path", "number", "line", "ids"), list(_bronregels()))
def test_example_title_is_the_catalog_title(path, number, line, ids):
    titels = set(_CURSIEF.findall(line))
    for dataset_id in ids:
        verwacht = catalogus_titel(dataset_id)
        if verwacht == dataset_id:
            pytest.fail(f"{path}:{number} noemt {dataset_id}, dat niet in de catalogus staat")
        assert verwacht in titels, f"{path}:{number}: titel van {dataset_id} moet '{verwacht}' zijn, niet {sorted(titels)}"
