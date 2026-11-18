"""Groeit de rekentijd lineair met de invoer? Een verhouding van twee metingen, geen vaste grens in seconden (#1048).

Een absolute grens ("onder 1 s") faalt op een drukke gedeelde runner ook voor lineaire code. Hier telt de groei:
lineair werk kost bij 4n ongeveer 4 keer zo veel, kwadratisch werk 16 keer. De grens ligt op 8 keer plus een vaste
marge voor ruis; een runner die 3 tot 5 keer zo traag is, verandert de verhouding niet (zoals #1018 het werk telt).
"""

import time
from collections.abc import Callable

_POGINGEN = 3
_FACTOR = 4
_GRENS = 8
_MARGE = 0.1  # seconden: een pauze van een drukke runner op een meting van een paar milliseconden


def _duur(functie: Callable[[str], object], invoer: str) -> float:
    start = time.perf_counter()
    functie(invoer)
    return time.perf_counter() - start


def assert_lineair(functie: Callable[[str], object], maak: Callable[[int], str], n: int = 10_000) -> None:
    """`functie(maak(4n))` duurt minder dan 8 keer `functie(maak(n))` plus de marge; elke meting de snelste poging."""
    enkel = min(_duur(functie, maak(n)) for _ in range(_POGINGEN))
    grens = _GRENS * enkel + _MARGE
    groot = maak(_FACTOR * n)
    metingen = []
    for _ in range(_POGINGEN):
        metingen.append(_duur(functie, groot))
        if metingen[-1] < grens:
            return
    raise AssertionError(
        f"niet lineair: {enkel:.4f} s bij n={n}, {min(metingen):.4f} s bij {_FACTOR}n (grens {grens:.4f} s)"
    )
