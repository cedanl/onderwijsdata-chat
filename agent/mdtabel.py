"""De markdowntabellen in lopende antwoordtekst: waar ze staan en wat erin staat (#811, #982).

Een tabel is een kopregel met pijpen, een scheidingsregel eronder (|---|---:|) en de rijen die daarop volgen. Een tabel
in een codeblok is geen tabel van het antwoord: die telt niet.

Een getal in een tabelcel duidt de lezer met de kolomkop, de labelcellen van de rij en de tekst vóór de tabel, niet
met de rij alleen (#1002): "| 2020/21 | 43.070 |" zegt niet dat 43.070 bachelordiploma's zijn, de kop "Bachelor" wel.
`tabelcellen` geeft die context per cel, voor de tabelcontrole (agent/tabelbinding.py) en de citaties
(agent/citaties.py).
"""

from dataclasses import dataclass

from .beschermd import lopende_regels
from .getalnotatie import tabelscheiding
from .grounding import decimalen_met_positie

# Opmaak rond een cel: **70,6%** is de cel 70,6%.
_OPMAAK = " \t*_`"


@dataclass(frozen=True)
class Tabel:
    begin: int  # index van de kopregel in de regels van de tekst
    einde: int  # index van de laatste rij
    kop: tuple[str, ...]
    rijen: tuple[tuple[str, ...], ...]  # de datarijen, zonder kop en scheidingsregel


@dataclass(frozen=True)
class Cel:
    """Eén cel van een datarij, met wat haar duidt."""

    begin: int  # positie van de cel in de tekst, de pijpen niet meegeteld
    einde: int
    tekst: str  # de cel zonder opmaak
    kop: str  # de kolomkop; leeg als de rij meer cellen heeft dan de kop
    rij: tuple[str, ...]
    labels: tuple[str, ...]  # de cellen van de rij zonder decimaal getal: het schooljaar, de instelling
    ervoor: str  # de tekst vóór de tabel en de kopregel: waar de maat van de tabel staat

    @property
    def context(self) -> str:
        """Wat de cel aanwijst, zoals een zin: de kolomkop en de labelcellen van de rij."""
        return " ".join([self.kop, *self.labels])


def _celgrenzen(regel: str) -> list[tuple[int, int]]:
    """Begin en einde van elke cel in de regel, zonder de witruimte om de regel en zonder de lege stukken buiten de
    buitenste pijpen."""
    begin = len(regel) - len(regel.lstrip())
    grenzen = []
    for deel in regel.strip().split("|"):
        grenzen.append((begin, begin + len(deel)))
        begin += len(deel) + 1
    if grenzen and not regel[slice(*grenzen[0])].strip():
        grenzen = grenzen[1:]
    if grenzen and not regel[slice(*grenzen[-1])].strip():
        grenzen = grenzen[:-1]
    return grenzen


def cellen(regel: str) -> tuple[str, ...]:
    """De cellen van een tabelrij, zonder opmaak en zonder de lege stukken buiten de buitenste pijpen."""
    return tuple(regel[begin:einde].strip(_OPMAAK) for begin, einde in _celgrenzen(regel))


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


def tabelcellen(tekst: str) -> list[Cel]:
    """Elke cel van elke datarij van de tabellen in `tekst`, in tekstvolgorde, met haar kop, labels en de tekst ervoor."""
    regels = tekst.split("\n")
    regelbegin = [0]
    for regel in regels:
        regelbegin.append(regelbegin[-1] + len(regel) + 1)
    gevonden: list[Cel] = []
    for tabel in tabellen(regels):
        ervoor = "\n".join(regels[: tabel.begin]) + "\n" + " | ".join(tabel.kop)
        for i, rij in enumerate(tabel.rijen, tabel.begin + 2):
            labels = tuple(cel for cel in rij if not decimalen_met_positie(cel))
            for k, (begin, einde) in enumerate(_celgrenzen(regels[i])):
                kop = tabel.kop[k] if k < len(tabel.kop) else ""
                plek = regelbegin[i]
                gevonden.append(Cel(plek + begin, plek + einde, rij[k], kop, rij, labels, ervoor))
    return gevonden
