"""Welke indeling een grafiek toont, in woorden uit de metadata van de data, niet van het model (#1232).

Dezelfde vraag ("hbo-studenten per sector") gaf de ene keer een grafiek op de DUO-sectoren en de andere keer op de
CBS-studierichtingen, en de titel zei niet welke. De code weet het: de bron en de kolommen staan in `KeyMeta`, de
x-kolom is de categorie. Eén functie maakt de woorden ("per sector (DUO)"); de titel van de grafiek, de bronregel
onder de rapportfiguur en de regel boven de CSV lezen ze hier, zodat ze gelijk opgaan.
"""

import re
from collections.abc import Mapping

from .kolomlabel import kolomlabel
from .store import KeyMeta

# DUO deelt hbo/wo in naar ONDERDEEL en mbo naar HOOFDGROEP NAAM: allebei de sector (docs/databronnen.md).
_DUO_INDELING = {"ONDERDEEL": "sector", "HOOFDGROEP NAAM": "sector"}

# Een CBS-dimensie die een opleidingsindeling is: "Studierichting", "Opleidingsrichting en sector", "Sectorkamer".
# Jaren, regio's en geslacht vallen erbuiten.
_CBS_INDELING = re.compile(r"richting|sector", re.IGNORECASE)


def _indeling(known: KeyMeta | None, x: str, titels: Mapping[str, str] | None) -> tuple[str, str] | None:
    """(indeling, bron) van de x-kolom, zoals ("sector", "DUO"); None als de x-kolom geen bekende indeling is."""
    if known is None or not x:
        return None
    bron = (known.bron or "").lower()
    if bron == "duo" and (woord := _DUO_INDELING.get(x)):
        return woord, "DUO"
    if bron == "cbs" and _CBS_INDELING.search(label := kolomlabel(x, titels)):
        return label.lower(), "CBS"
    return None


def indeling_in_woorden(known: KeyMeta | None, x: str, titels: Mapping[str, str] | None = None) -> str | None:
    """De indeling van een grafiek met categorieën `x`: "per sector (DUO)", "per studierichting (CBS)"; None als de
    data geen bron heeft of `x` geen bekende indeling is (jaren, regio's)."""
    gevonden = _indeling(known, x, titels)
    return f"per {gevonden[0]} ({gevonden[1]})" if gevonden else None


def titel_met_indeling(titel: str, known: KeyMeta | None, x: str, titels: Mapping[str, str] | None = None) -> str:
    """De titel van het model met de indeling erachter, zonder te herhalen wat er al in staat: noemt de titel de
    indeling al ("per sector"), dan komt alleen de bron erbij, en noemt hij ook de bron, dan blijft hij gelijk."""
    if not (gevonden := _indeling(known, x, titels)):
        return titel
    woord, bron = gevonden
    tekst = titel if isinstance(titel, str) else ""
    erbij = ""
    if woord not in tekst.lower():
        erbij += f" per {woord}"
    if not re.search(rf"\b{bron}\b", tekst, re.IGNORECASE):
        erbij += f" ({bron})"
    return f"{tekst}{erbij}".strip()


def indelingsregel(indeling: str) -> str:
    """De regel over de indeling boven de CSV en in de bronregel van de rapportfiguur: "indeling: per sector (DUO)"."""
    return f"indeling: {indeling}"
