"""Arbeidsmarktregio van een gemeente, uit de CBS-gebiedsindeling (#454).

DUO geeft bij een instellingsadres het RPA-gebied: een oudere indeling met andere namen en
grenzen dan de 35 arbeidsmarktregio's van UWV en ROA (Utrecht-Midden tegenover
Midden-Utrecht, Nijmegen tegenover Rijk van Nijmegen). De gemeente van het adres plus deze
indeling geeft de regio die ROA kent. `scripts/refresh_arbeidsmarktregio.py` ververst het
bestand per CBS-jaargang.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PAD = Path(__file__).with_name("arbeidsmarktregio_gemeente.json")


@lru_cache(maxsize=1)
def _indeling() -> dict:
    return json.loads(_PAD.read_text())


def gemeenten() -> dict[str, str]:
    """Gemeentecode (vier cijfers) → arbeidsmarktregio."""
    return _indeling()["gemeenten"]


def bron() -> dict[str, str]:
    """CBS-tabel, titel, url en ophaaldatum van de indeling."""
    return _indeling()["_bron"]


def van_gemeente(gemeentenummer) -> str | None:
    """De arbeidsmarktregio bij een CBS-gemeentenummer (80 of '0080'); None als onbekend, geen gok."""
    try:
        code = f"{int(str(gemeentenummer).strip()):04d}"
    except ValueError:
        return None
    return gemeenten().get(code)
