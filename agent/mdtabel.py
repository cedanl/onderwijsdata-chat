"""De markdowntabellen in lopende antwoordtekst: waar ze staan en wat erin staat (#811, #982).

Een tabel is een kopregel met pijpen, een scheidingsregel eronder (|---|---:|) en de rijen die daarop volgen. Een tabel
in een codeblok is geen tabel van het antwoord: die telt niet.
"""

from dataclasses import dataclass

from .beschermd import lopende_regels
from .getalnotatie import tabelscheiding

# Opmaak rond een cel: **70,6%** is de cel 70,6%.
_OPMAAK = " \t*_`"


@dataclass(frozen=True)
class Tabel:
    begin: int  # index van de kopregel in de regels van de tekst
    einde: int  # index van de laatste rij
    kop: tuple[str, ...]
    rijen: tuple[tuple[str, ...], ...]  # de datarijen, zonder kop en scheidingsregel


def cellen(regel: str) -> tuple[str, ...]:
    """De cellen van een tabelrij, zonder opmaak en zonder de lege stukken buiten de buitenste pijpen."""
    delen = regel.strip().split("|")
    if delen and not delen[0].strip():
        delen = delen[1:]
    if delen and not delen[-1].strip():
        delen = delen[:-1]
    return tuple(cel.strip(_OPMAAK) for cel in delen)


def tabellen(regels: list[str]) -> list[Tabel]:
    """De tabellen in lopende tekst, in tekstvolgorde."""
    lopend = [isloop for _, isloop in lopende_regels(regels)]
    gevonden: list[Tabel] = []
    i = 0
    while i + 1 < len(regels):
        if not (lopend[i] and "|" in regels[i] and tabelscheiding(regels[i + 1])):
            i += 1
            continue
        einde = i + 1
        while einde + 1 < len(regels) and lopend[einde + 1] and "|" in regels[einde + 1]:
            einde += 1
        rijen = tuple(cellen(regel) for regel in regels[i + 2 : einde + 1])
        gevonden.append(Tabel(i, einde, cellen(regels[i]), rijen))
        i = einde + 1
    return gevonden
