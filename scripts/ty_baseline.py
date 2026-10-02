#!/usr/bin/env python
"""
ty-poort met baseline: faal alleen op diagnostics die er nog niet waren (#230).

Gebruik:
    uv run python scripts/ty_baseline.py           # controleer tegen ty-baseline.txt
    uv run python scripts/ty_baseline.py --update  # leg de huidige stand vast

ty kent zelf geen baseline. Dit script vergelijkt per bestand, regel en melding hoe vaak
een diagnostic voorkomt; het regelnummer telt niet mee, zodat een regel erboven toevoegen
geen nieuwe fout oplevert. Los je diagnostics op, draai dan --update zodat de baseline
mee krimpt.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

BASELINE = Path(__file__).resolve().parent.parent / "ty-baseline.txt"

# agent/loop.py:88:67: warning[invalid-argument-type] Argument ...
_DIAGNOSTIC = re.compile(r"^(?P<pad>[^:\s]+):\d+:\d+: (?P<rest>\w+\[[\w-]+\] .*)$")


def sleutels(uitvoer: str) -> Counter[str]:
    """Tel diagnostics uit `ty check --output-format concise`, zonder regel- en kolomnummer."""
    return Counter(f"{m['pad']}: {m['rest']}" for regel in uitvoer.splitlines() if (m := _DIAGNOSTIC.match(regel)))


def nieuwe(huidig: Counter[str], baseline: Counter[str]) -> list[str]:
    """Diagnostics die vaker voorkomen dan in de baseline."""
    return sorted((huidig - baseline).elements())


def _ty_check() -> str:
    resultaat = subprocess.run(
        ["ty", "check", "--output-format", "concise", "--exit-zero"],
        capture_output=True,
        text=True,
        check=True,
    )
    return resultaat.stdout


def main(argv: list[str]) -> int:
    huidig = sleutels(_ty_check())
    if "--update" in argv:
        BASELINE.write_text("".join(f"{s}\n" for s in sorted(huidig.elements())), encoding="utf-8")
        print(f"{BASELINE.name}: {huidig.total()} diagnostics vastgelegd")
        return 0

    baseline = sleutels_uit_baseline()
    erbij = nieuwe(huidig, baseline)
    if erbij:
        print(f"{len(erbij)} nieuwe ty-diagnostics (niet in {BASELINE.name}):")
        print("\n".join(f"  {s}" for s in erbij))
        print("Los ze op; draai `uv run ty check` voor de regelnummers.")
        return 1
    opgelost = (baseline - huidig).total()
    print(f"ty: {huidig.total()} diagnostics, geen nieuwe.")
    if opgelost:
        print(f"{opgelost} uit de baseline zijn opgelost; draai --update zodat de baseline krimpt.")
    return 0


def sleutels_uit_baseline() -> Counter[str]:
    return Counter(regel for regel in BASELINE.read_text(encoding="utf-8").splitlines() if regel)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
