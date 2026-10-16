"""Gaat een vraag aantoonbaar over hoger onderwijs? Code beslist, niet het model (#556, #191).

Stap 3 van epic #554 (#557) laat vo-contextrecords alleen in zoekresultaten toe als
`noemt_ho` waar is. De woordgrensregel volgt `tools.catalog._word_match`: korte
termen (<= 3 tekens) alleen als heel woord (`\\b<term>\\b`, dus "woning", "hoger" en
"vwo" tellen niet, "wo-master" en "(wo)" wel); langere termen als deelstring, zodat
"Hanzehogeschool" en "universiteiten" meetellen. De regel is gekopieerd, niet
geïmporteerd: deze module kent alleen strings en importeert de catalogus niet.

Bewust geen marker: "instroom", "studenten", "doorstroom", "instelling" en "regio".
Ze komen ook in mbo-vragen voor; als marker brachten ze het lek van 6 oktober terug
(`voprognoses` bij "per instelling"). Ook "havo" en "vwo" niet (#597): dat is vo, en een
zuivere vo-vraag ("Hoeveel leerlingen zitten er op het vwo?") opende zo de poort, tegen het
scopebesluit in (#355). Een ho-contextvraag noemt het ho zelf ("doorstroom van havo naar hbo").

De poort kijkt naar de vraag van de gebruiker, niet naar de zoekterm van het model (#597):
anders opent het model de poort door zelf "hbo" toe te voegen. `run()` zet die vraag per
beurt (`beurtvraag`); buiten de chat (MCP, evals) is er geen en beslist de zoekterm.

`agent.vo_school._HO_MBO_CONTEXT` is een andere, bredere wegblijf-guard (met mbo,
student, eerstejaars, roc) voor de vo-schooluitleg; `noemt_ho` is de striktere toets
"aantoonbaar ho" voor het zoeken.
"""

import contextlib
import re
from collections.abc import Generator
from contextvars import ContextVar

_KORT = ("wo", "ho", "hbo")
_LANG = ("hogeschool", "hogescholen", "universiteit", "universiteiten")

_KORTE_MARKER = re.compile(rf"\b(?:{'|'.join(_KORT)})\b")
_HOGER_ONDERWIJS = re.compile(r"hoger\s+onderwijs")

# De vraag van de gebruiker in deze beurt; taken en threads van de beurt erven hem (asyncio.to_thread).
_beurtvraag: ContextVar[str | None] = ContextVar("beurtvraag", default=None)


def noemt_ho(query: str) -> bool:
    """Waar als de vraag een ho-marker noemt (hoofdletterongevoelig)."""
    tekst = query.lower()
    return bool(_KORTE_MARKER.search(tekst) or _HOGER_ONDERWIJS.search(tekst) or any(term in tekst for term in _LANG))


@contextlib.contextmanager
def beurtvraag(vraag: str) -> Generator[None, None, None]:
    """Binnen dit blok beslist de zoekpoort op `vraag`, de vraag van de gebruiker (#597)."""
    token = _beurtvraag.set(vraag)
    try:
        yield
    finally:
        _beurtvraag.reset(token)


def ho_poort(zoekterm: str) -> bool:
    """Gaat de zoekpoort voor vo-context open (#557)? Op de vraag van de gebruiker als er een beurt loopt,
    anders op de zoekterm (#597)."""
    vraag = _beurtvraag.get()
    return noemt_ho(zoekterm if vraag is None else vraag)
