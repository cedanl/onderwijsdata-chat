"""Persoonsgegevens in een vraag herkennen, deterministisch en in code (#478, #191).

Een BSN (negen cijfers die de elfproef doorstaan), een e-mailadres of een Nederlands
telefoonnummer. Een naam is niet te herkennen; daarom staat de waarschuwing in de app er
altijd. Dezelfde regels als frontend/src/persoonsgegevens.js: de titel van een gesprek
(frontend, en bij het opslaan nog eens op de server, #552) en de terugvaltitel van een
rapport (hier) volgen beide deze herkenning.
"""

import re
from dataclasses import dataclass
from typing import TypeVar

# Negen losse cijfers: niet midden in een langer of gegroepeerd getal (een telefoonnummer, 1.234.567.890).
_BSN = re.compile(r"(?<!\d)(?<!\d[.,-])\d{9}(?![.,-]?\d)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
# 06 12345678, 030-1234567, +31 6 12345678: tien cijfers vanaf 0, of negen na +31/0031.
_TELEFOON = re.compile(r"(?<![\d+])(?:\+31|0031|0)[\s-]?[1-9](?:[\s-]?\d){8}(?!\d)")

# Gelijk aan TITEL_ZONDER_PERSOONSGEGEVENS in frontend/src/conversationTitle.js; een test bewaakt dat.
GESPREKSTITEL_ZONDER_PERSOONSGEGEVENS = "Gesprek (persoonsgegevens weggelaten)"

_T = TypeVar("_T")


@dataclass(frozen=True)
class Persoonsgegeven:
    soort: str  # bsn | email | telefoon
    tekst: str


def elfproef(cijfers: str) -> bool:
    """De elfproef van een BSN: 9·d1 + 8·d2 + … + 2·d8 - d9 is deelbaar door 11."""
    if not re.fullmatch(r"\d{9}", cijfers) or cijfers == "0" * 9:
        return False
    d = [int(c) for c in cijfers]
    return (sum(cijfer * (9 - i) for i, cijfer in enumerate(d[:8])) - d[8]) % 11 == 0


def vind(tekst: str) -> list[Persoonsgegeven]:
    """Wat er in de tekst staat, in volgorde van de tekst."""
    tekst = tekst or ""
    treffers = [(m.start(), "bsn", m.group()) for m in _BSN.finditer(tekst) if elfproef(m.group())]
    treffers += [(m.start(), "email", m.group()) for m in _EMAIL.finditer(tekst)]
    treffers += [(m.start(), "telefoon", m.group()) for m in _TELEFOON.finditer(tekst)]
    return [Persoonsgegeven(soort, gevonden) for _, soort, gevonden in sorted(treffers)]


def bevat(tekst: str) -> bool:
    return bool(vind(tekst))


def veilige_gesprekstitel(titel: _T) -> _T | str:
    """De titel, of de generieke titel als er een BSN, e-mailadres of telefoonnummer in staat (#552).

    Een titel die geen tekst is, gaat ongewijzigd door: dat gedrag blijft zoals het was.
    """
    return GESPREKSTITEL_ZONDER_PERSOONSGEGEVENS if isinstance(titel, str) and bevat(titel) else titel
