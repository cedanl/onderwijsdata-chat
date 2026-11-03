"""Een vaste voetnoot onder een tabel met "niet beschikbaar"-cellen, uit code (#811).

`query_data` geeft een onderdrukte cel als null, en het model zet die in een tabel als "niet beschikbaar", een streepje
of een lege cel. De Ondergrens-regel in het Telling-blok verschijnt alleen als een getal in de tekst op zo'n selectie
rust (#414): toonde het antwoord alleen een tabel zonder totaal, dan stond nergens waarom die cellen leeg waren
(mobiel N39). Nu staat direct onder zo'n tabel wat de cel is, in de woorden van de bron (`BETEKENIS`): de uitleg staat
waar de lege cellen staan, ook zonder totaal in de tekst.
"""

import re

from core.sentinels import BETEKENIS, CBS_BETEKENIS
from tools import duo

from .beschermd import lopende_regels
from .getalnotatie import tabelscheiding
from .selectie import stapkeys

# Per bron de voetnoot, in de woorden van de Ondergrens-regel (agent/telling.py).
NOTEN = {
    "duo": f"*Niet beschikbaar: in het DUO-bestand staat hier -1 ({BETEKENIS}).*",
    "cbs": f"*Niet beschikbaar: in de CBS-tabel is deze cel leeg ('.'; {CBS_BETEKENIS}).*",
}

# Hoe het model een onderdrukte cel in een tabel schrijft: leeg, een streepje, -1, "niet beschikbaar" of iets ervan.
_LEGE_CEL = re.compile(
    r"(?:|[-–—−]|[-–—−]\s?1|n\.?\s?b\.?|niet\s+beschikbaar\b.*|onderdrukt\b.*|geen\s+cijfer\b.*|<\s?5|null|nan)",
    re.IGNORECASE,
)
_OPMAAK = " \t*_`"


def _bronnen(tool_results: list[str]) -> list[str]:
    """De bronnen met een onderdrukte cel achter een stap van de beurt, in de volgorde van NOTEN."""
    gevonden = {duo.bron_van(key) for result in tool_results for key in stapkeys(result) if duo.onderdrukt(key)}
    return [bron for bron in NOTEN if bron in gevonden]


def _cellen(regel: str) -> list[str]:
    """De cellen van een tabelrij, zonder de lege stukken buiten de buitenste pijpen."""
    delen = regel.strip().split("|")
    if delen and not delen[0].strip():
        delen = delen[1:]
    if delen and not delen[-1].strip():
        delen = delen[:-1]
    return [cel.strip(_OPMAAK) for cel in delen]


def _lege_cel(regel: str) -> bool:
    return any(_LEGE_CEL.fullmatch(cel) for cel in _cellen(regel))


def _tabellen(regels: list[str]) -> list[tuple[int, bool]]:
    """Per tabel in lopende tekst: de index van haar laatste rij en of een datarij een lege cel heeft."""
    lopend = [isloop for _, isloop in lopende_regels(regels)]
    tabellen: list[tuple[int, bool]] = []
    i = 0
    while i + 1 < len(regels):
        if not (lopend[i] and "|" in regels[i] and tabelscheiding(regels[i + 1])):
            i += 1
            continue
        einde, leeg = i + 1, False
        while einde + 1 < len(regels) and lopend[einde + 1] and "|" in regels[einde + 1]:
            einde += 1
            leeg = leeg or _lege_cel(regels[einde])
        tabellen.append((einde, leeg))
        i = einde + 1
    return tabellen


def met_tabelnoot(tekst: str, tool_results: list[str]) -> str:
    """Het antwoord met onder elke tabel met een lege cel de voetnoot van elke bron met onderdrukte cellen.

    Alleen als de beurt een selectie met onderdrukte cellen las: een lege cel in een tabel zonder zulke data is iets
    anders, en dan zegt de app er niets over. Staat de noot er al (een tweede keer verwerkt), dan komt er geen bij.
    """
    if not (bronnen := _bronnen(tool_results)):
        return tekst
    noten = [NOTEN[bron] for bron in bronnen]
    regels = tekst.split("\n")
    for einde, leeg in reversed(_tabellen(regels)):
        na = regels[einde + 1 :]
        if not leeg or na[:2] == ["", noten[0]]:
            continue
        # Een eigen alinea: een lege regel erboven, en eronder als er direct tekst volgt.
        regels[einde + 1 : einde + 1] = ["", *noten, *([""] if na and na[0].strip() else [])]
    return "\n".join(regels)
