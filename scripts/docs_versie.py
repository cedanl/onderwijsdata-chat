"""Schrijft de versieregel van de documentatie uit `pyproject.toml` (audit 26-11-2026, G2).

De regel staat in `docs/.versie.md` en wordt op de startpagina en op "Over Onderwijsdata Chat" ingevoegd
(`--8<-- "docs/.versie.md"`). Een bestand met een punt vooraan wordt geen pagina van de site.

    uv run python scripts/docs_versie.py             # schrijf docs/.versie.md
    uv run python scripts/docs_versie.py --controle  # exit 1 als het bestand niet klopt

De docs-workflow draait het schrijven vóór de build, en `tests/test_docs_versie.py` houdt het bestand in de repo gelijk.
Bij een release (stap 0 van `Agents.md`) draai je het mee met de versie in `pyproject.toml`.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BESTAND = ROOT / "docs" / ".versie.md"


def versie() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def regel() -> str:
    return f"*Documentatie bij versie {versie()}.*\n"


def main(argv: list[str]) -> int:
    if "--controle" in argv:
        if BESTAND.read_text(encoding="utf-8") != regel():
            print(
                f"{BESTAND.relative_to(ROOT)} loopt achter op pyproject.toml: draai scripts/docs_versie.py",
                file=sys.stderr,
            )
            return 1
        return 0
    BESTAND.write_text(regel(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
