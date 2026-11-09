"""Een vaste voetnoot onder een tabel met "niet beschikbaar"-cellen, uit code (#811).

`query_data` geeft een onderdrukte cel als null, en het model zet die in een tabel als "niet beschikbaar", een streepje
of een lege cel. De Ondergrens-regel in het Telling-blok verschijnt alleen als een getal in de tekst op zo'n selectie
rust (#414): toonde het antwoord alleen een tabel zonder totaal, dan stond nergens waarom die cellen leeg waren
(mobiel N39). Nu staat direct onder zo'n tabel wat de cel is, in de woorden van de bron (`BETEKENIS`): de uitleg staat
waar de lege cellen staan, ook zonder totaal in de tekst.
"""

import re

from core.sentinels import BETEKENIS, CBS_BETEKENIS
from tools import bron_ids, duo

from .mdtabel import tabellen
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


def _bronnen(tool_results: list[str]) -> list[str]:
    """De bronnen met een onderdrukte cel achter een stap van de beurt, in de volgorde van NOTEN."""
    gevonden = {bron_ids.bron_van(key) for result in tool_results for key in stapkeys(result) if duo.onderdrukt(key)}
    return [bron for bron in NOTEN if bron in gevonden]


def _tabellen(regels: list[str]) -> list[tuple[int, bool]]:
    """Per tabel in lopende tekst: de index van haar laatste rij en of een datarij een lege cel heeft."""
    return [(t.einde, any(_LEGE_CEL.fullmatch(cel) for rij in t.rijen for cel in rij)) for t in tabellen(regels)]


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
