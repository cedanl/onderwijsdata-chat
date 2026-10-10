"""Voorbeeldtitels in prompts en docs zijn de catalogustitel (#204).

De prompt eist de exacte titel uit de catalogus, maar een voorbeeld noemde 85423NED als
"MBO; deelnemers naar geslacht en niveau" terwijl het "Hoger onderwijs; ingeschrevenen, …" is:
het model leest voorbeelden als waarheid.

Sinds de app de Bronnen zelf onder het antwoord zet (#416) staat er geen voorbeeld-bronregel meer
in de prompt. De bewaking blijft voor een voorbeeld dat terugkomt; een eigen test laat zien dat
ze nog werkt, zodat een lege set niet stil als "overgeslagen" door de suite gaat.
"""

import re
from collections.abc import Iterator
from pathlib import Path

from tools.catalog import catalogus_titel

ROOT = Path(__file__).resolve().parent.parent
FILES = sorted([*ROOT.glob("prompts/*.md"), *ROOT.glob("docs/**/*.md"), ROOT / "README.md"])

# Een bronvermelding: "- CBS dataset 85423NED — *Titel*" of "- DUO — *Titel* (**p02ho1ejrs**)".
_BRON_REGEL = re.compile(r"^\s*[-*]\s+(?:CBS|DUO|RIO)\b.*—.*\*[^*]+\*")
_DATASET_ID = re.compile(r"\b(\d{5}(?:NED|ENG)|p\d{2}[a-z0-9]{3,})\b")
_CURSIEF = re.compile(r"(?<!\*)\*([^*]{8,}?)\*(?!\*)")


def _titelfouten(path: Path | str, lines: list[str]) -> Iterator[str]:
    """Elke voorbeeld-bronregel waarvan de cursieve titel niet de catalogustitel van zijn dataset-ID is."""
    for number, line in enumerate(lines, 1):
        if not _BRON_REGEL.search(line):
            continue
        titels = set(_CURSIEF.findall(line))
        for dataset_id in sorted(set(_DATASET_ID.findall(line))):
            verwacht = catalogus_titel(dataset_id)
            if verwacht == dataset_id:
                yield f"{path}:{number} noemt {dataset_id}, dat niet in de catalogus staat"
            elif verwacht not in titels:
                yield f"{path}:{number}: titel van {dataset_id} moet '{verwacht}' zijn, niet {sorted(titels)}"


def test_example_titles_are_the_catalog_titles():
    fouten = [
        fout
        for path in FILES
        for fout in _titelfouten(path.relative_to(ROOT), path.read_text(encoding="utf-8").splitlines())
    ]
    assert not fouten, "\n".join(fouten)


def test_the_guard_flags_a_wrong_or_unknown_title():
    goed = "- CBS dataset 85423NED — *Hoger onderwijs; ingeschrevenen, onderwijssoort, opleidingsfase en -vorm*"
    fout = "- CBS dataset 85423NED — *MBO; deelnemers naar geslacht en niveau*"
    onbekend = "- DUO — *Een dataset die niet bestaat* (**p99onbekend**)"

    assert list(_titelfouten("voorbeeld.md", [goed])) == []
    assert list(_titelfouten("voorbeeld.md", [fout, onbekend])) == [
        "voorbeeld.md:1: titel van 85423NED moet "
        "'Hoger onderwijs; ingeschrevenen, onderwijssoort, opleidingsfase en -vorm' zijn, "
        "niet ['MBO; deelnemers naar geslacht en niveau']",
        "voorbeeld.md:2 noemt p99onbekend, dat niet in de catalogus staat",
    ]
