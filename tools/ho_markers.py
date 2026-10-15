"""Gaat een vraag aantoonbaar over hoger onderwijs? Code beslist, niet het model (#556, #191).

Stap 3 van epic #554 (#557) laat vo-contextrecords alleen in zoekresultaten toe als
`noemt_ho` waar is. De woordgrensregel volgt `tools.catalog._word_match`: korte
termen (<= 3 tekens) alleen als heel woord (`\\b<term>\\b`, dus "woning" en "hoger"
tellen niet, "wo-master" en "(vwo)" wel); langere termen als deelstring, zodat
"Hanzehogeschool" en "universiteiten" meetellen. De regel is gekopieerd, niet
geïmporteerd: deze module kent alleen strings en importeert de catalogus niet.

Bewust geen marker: "instroom", "studenten", "doorstroom", "instelling" en "regio".
Ze komen ook in mbo-vragen voor; als marker brachten ze het lek van 6 oktober terug
(`voprognoses` bij "per instelling").

`agent.vo_school._HO_MBO_CONTEXT` is een andere, bredere wegblijf-guard (met mbo,
student, eerstejaars, roc) voor de vo-schooluitleg; `noemt_ho` is de striktere toets
"aantoonbaar ho" voor het zoeken.
"""

import re

_KORT = ("wo", "ho", "hbo", "vwo")
_LANG = ("havo", "hogeschool", "hogescholen", "universiteit", "universiteiten")

_KORTE_MARKER = re.compile(rf"\b(?:{'|'.join(_KORT)})\b")
_HOGER_ONDERWIJS = re.compile(r"hoger\s+onderwijs")


def noemt_ho(query: str) -> bool:
    """Waar als de vraag een ho-marker noemt (hoofdletterongevoelig)."""
    tekst = query.lower()
    return bool(_KORTE_MARKER.search(tekst) or _HOGER_ONDERWIJS.search(tekst) or any(term in tekst for term in _LANG))
