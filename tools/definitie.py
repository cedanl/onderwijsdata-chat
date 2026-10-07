"""Voorbeelden in een kolomdefinitie zijn geen gesloten lijst (#430).

Een definitie als "Studierichting (bijv. TECHNIEK, ECONOMIE, GEZONDHEIDSZORG)" noemt
voorbeelden. Las het model dat als de toegestane waarden, dan zag het andere waarden
in de data als een "metadata-conflict". De code beslist of een definitie voorbeelden
noemt en zegt dat er in de tooluitvoer bij; het model hoeft het niet af te leiden.

"zoals" gevolgd door een voltooid deelwoord ("zoals geregistreerd", "zoals
gepubliceerd: A, B of C") is een vergelijking, geen voorbeeld.
"""

import re

_VOORBEELD = re.compile(
    r"\b(?:bijv\.|bijvoorbeeld|bv\.|b\.v\.|o\.a\.|onder andere|zoals(?!\s+ge\w+[dt]\b))",
    re.IGNORECASE,
)

VOORBEELDEN = "De genoemde waarden zijn voorbeelden, geen volledige lijst: de data kan andere waarden hebben."


def noemt_voorbeelden(tekst: str) -> bool:
    return bool(_VOORBEELD.search(tekst))


def met_voorbeeldstatus(tekst: str) -> str:
    """De definitie, met de zin dat genoemde waarden voorbeelden zijn als dat zo is."""
    return f"{tekst} ({VOORBEELDEN})" if noemt_voorbeelden(tekst) else tekst
