"""Gemeente en provincie van een woonplaats, uit de CBS-tabel "Woonplaatsen in Nederland" (#744).

De plaats van een onderwijslocatie (RIO, DUO's mbo_opleidingsaanbod) is een BAG-woonplaats; een regio op gemeente- of
provincieniveau vraagt om de gemeente erachter. `scripts/refresh_woonplaatsen.py` ververst het bestand per
CBS-jaargang. Een woonplaatsnaam bij meer gemeenten (Velp: Rheden en Land van Cuijk) houdt ze allemaal.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PAD = Path(__file__).with_name("woonplaatsen.json")


@lru_cache(maxsize=1)
def _indeling() -> dict:
    return json.loads(_PAD.read_text())


def woonplaatsen() -> dict[str, list[str]]:
    """Woonplaatsnaam → de gemeentecodes (vier cijfers) waarin een woonplaats met die naam ligt."""
    return _indeling()["woonplaatsen"]


def gemeenten() -> dict[str, dict[str, str]]:
    """Gemeentecode (vier cijfers) → {naam, provincie}; de provincie als CBS-code (PV25)."""
    return _indeling()["gemeenten"]


def bron() -> dict[str, str]:
    """CBS-tabel, titel, url en ophaaldatum van de indeling."""
    return _indeling()["_bron"]
