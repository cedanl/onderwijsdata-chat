"""Welke bronbestanden een lading gebruikte (#904).

Een lader meldt elk bestand dat hij met succes laadde (`meld`); wie wil weten waar een uitkomst op rust, verzamelt die
meldingen (`verzamel`). Een dashboard maakt er zijn bronblok van. Buiten een verzameling doet een melding niets: de
chat laadt dezelfde bestanden zonder te verzamelen.

`actualiteit.Lading` bewaart de meldingen van een lading bij haar waarde en meldt ze bij elke cachetreffer opnieuw.
Anders zag alleen de eerste aanroep na de TTL welke bestanden erachter zitten.
"""

import contextvars
from collections.abc import Generator, Mapping
from contextlib import contextmanager

_verzameling: contextvars.ContextVar[list[Mapping] | None] = contextvars.ContextVar("brongebruik", default=None)


@contextmanager
def verzamel() -> Generator[list[Mapping]]:
    """De meldingen binnen het blok, in de volgorde waarin ze kwamen. Een binnenste verzameling vangt ze af."""
    gemeld: list[Mapping] = []
    token = _verzameling.set(gemeld)
    try:
        yield gemeld
    finally:
        _verzameling.reset(token)


def meld(*bestanden: Mapping) -> None:
    """Deze bestanden zijn geladen; zonder verzameling eromheen gaat de melding nergens heen."""
    gemeld = _verzameling.get()
    if gemeld is not None:
        gemeld.extend(bestanden)
