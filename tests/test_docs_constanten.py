"""Een getal in de docs dat een constante uit `core/config.py` herhaalt, is de waarde die de code afdwingt (audit 27-11-2026, M1).

De zoeklimiet stond in één pagina op 5 en op 3, terwijl de code 3 afdwingt; `test_tool_limits.py` bewaakt de prompt,
niet de docs. Deze test leest per constante elke plek in docs/ die de naam noemt met een getal binnen 50 tekens
ervoor of erna, en eist dat de waarde van de code in dat venster staat (ook als 12.000 met punt). Een plek zonder getal
in de buurt telt niet mee.
"""

import re
from pathlib import Path

import pytest

from core import config

ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted((ROOT / "docs").rglob("*.md"))
GETAL = re.compile(r"\d")
VENSTER = 50

# (constante, alleen regels die zo beginnen; None = elke regel die de naam noemt)
CONSTANTEN = [
    ("SEARCH_CATALOG_LIMIT", None),
    ("MAX_TOOL_ITERATIONS", None),
    ("TOOL_RESULT_MAX_CHARS", None),
    # MAX_HISTORY staat in veel formules ("MAX_HISTORY // 2"); alleen de rij met de standaardwaarde telt.
    ("MAX_HISTORY", "| `MAX_HISTORY` |"),
]


def _vormen(waarde: int) -> tuple[str, ...]:
    return (str(waarde), f"{waarde:,}".replace(",", "."))


def _regels(naam: str, begin: str | None):
    for pad in DOCS:
        for nr, regel in enumerate(pad.read_text(encoding="utf-8").splitlines(), 1):
            if naam not in regel or (begin is not None and not regel.startswith(begin)):
                continue
            i = regel.index(naam)
            venster = regel[max(0, i - VENSTER) : i] + " " + regel[i + len(naam) : i + len(naam) + VENSTER]
            if GETAL.search(venster):
                yield pad.relative_to(ROOT), nr, venster


@pytest.mark.parametrize(("naam", "begin"), CONSTANTEN)
def test_docs_noemen_de_waarde_van_de_code(naam, begin):
    waarde = getattr(config, naam)
    gezien = list(_regels(naam, begin))
    assert gezien, f"{naam} staat nergens met een getal in docs/: de test bewaakt dan niets meer"

    afwijkend = [f"{pad}:{nr}" for pad, nr, venster in gezien if not any(v in venster for v in _vormen(waarde))]

    assert not afwijkend, f"{naam} is {waarde} in core/config.py, maar de docs noemen een ander getal: {afwijkend}"
