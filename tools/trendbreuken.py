"""Trendbreuken in een reeks: CBS-definitiebreuken en fusies, als lijn met label in de grafiek (#1262).

Twee bronnen, beide uit code en metadata; het model voegt niets toe:
- CBS: de passages over definitiebreuken uit TableInfos (`cbs_meta.metadata`, methodiek.definitiebreuken), zoals
  "vanaf 2016/'17 is ook de Transnationale Universiteit Limburg meegenomen". Het jaar komt uit de passage zelf; een
  passage zonder jaar gaat alleen in de noot. Een passage over de status van de cijfers (definitief, voorlopig) is geen
  breuk.
- DUO: de vaste fusieregel van de selectie (`KeyMeta.fusies`, `fusies.in_reeks`, #728): DUO telt de jaren vóór de fusie
  bij de huidige instelling. De lijn staat bij het eerste schooljaar dat na de fusie geteld is (DUO telt op 1 oktober)
  en noemt de voorganger.

Een breuk krijgt alleen een lijn als ze binnen de getekende jaren valt: na het eerste en uiterlijk op het laatste.
"""

import re
from dataclasses import asdict, dataclass

from . import cbs_meta, periode, store
from .fusies import _MAANDEN, _TELDAG

# De kleur van de lijn: grijs met 3:1 contrast op het lichte en het donkere thema (WCAG 1.4.11), en gestippeld, dus
# niet te verwarren met een reeks.
KLEUR = "#808080"
NAAM = "trendbreuk"

_JAAR = re.compile(r"(?:19|20)\d{2}")
# Het jaar waarop de definitie wijzigde: "vanaf 2016/'17", "sinds 2020", "per 2020", "met ingang van 2020", "in 2020".
_BREUKJAAR = re.compile(
    r"\b(?:vanaf|sinds|per|met ingang van|in)\s+(?:het\s+)?(?:(?:school|studie|verslag)?jaar\s+)?((?:19|20)\d{2})",
    re.IGNORECASE,
)
# Een passage over de status van de cijfers is geen definitiebreuk (85353NED: "zijn definitief en ... voorlopig").
_STATUS = re.compile(r"\b(?:definitief|voorlopig|nader voorlopig)\b", re.IGNORECASE)
# De vaste fusieregel van tools/fusies.py (_regel): per fusiedag de voorgangers.
_FUSIE_KOP = re.compile(r"^Fusie bij (?P<wie>.+?): DUO telt")
_FUSIE_DEEL = re.compile(
    r"DUO telt de jaren vóór de fusie \((?P<dag>\d{1,2}) (?P<maand>[a-z]+) (?P<jaar>\d{4})\) bij de huidige instelling "
    r"\(voorgangers: (?P<voor>.*?)\)(?=; DUO telt|\.$)"
)


@dataclass(frozen=True)
class Trendbreuk:
    jaar: int | None  # het eerste jaar na de breuk; None als de bron geen jaar noemt
    label: str  # de korte tekst bij de lijn
    bron: str  # waar de breuk vandaan komt, voor de noot
    passage: str  # de bronpassage of de vaste fusieregel, letterlijk

    def noot(self) -> str:
        """De noot onder de figuur en de '#'-regel boven de CSV: het jaar, de bron en de passage letterlijk."""
        wanneer = f"vanaf {self.jaar}" if self.jaar is not None else "jaar niet in de bron"
        return f"Trendbreuk {wanneer} ({self.bron}): “{self.passage}”"

    def als_meta(self) -> dict:
        return asdict(self)


def _cbs_jaren(passage: str) -> list[int]:
    return list(dict.fromkeys(int(j) for j in _BREUKJAAR.findall(passage)))


def cbs(dataset_id: str) -> list[Trendbreuk]:
    """De definitiebreuken van een CBS-tabel, één per jaar in de passage; zonder jaar één zonder jaar."""
    passages = (cbs_meta.metadata(dataset_id).get("methodiek") or {}).get("definitiebreuken") or []
    bron = f"CBS, tabel {dataset_id}, definitiebreuken in de tabeltoelichting"
    breuken = []
    for passage in passages:
        if not isinstance(passage, str) or not passage.strip() or _STATUS.search(passage):
            continue
        jaren = _cbs_jaren(passage) or [None]
        breuken += [
            Trendbreuk(jaar, f"definitiebreuk {jaar}" if jaar else "definitiebreuk", bron, passage) for jaar in jaren
        ]
    return breuken


def _eerste_telling(dag: int, maand: int, jaar: int) -> int:
    """Het eerste schooljaar dat DUO na een fusie op deze dag telt: de telling van 1 oktober."""
    return jaar if (maand, dag) <= _TELDAG else jaar + 1


def fusie(regels: tuple[str, ...] | list[str]) -> list[Trendbreuk]:
    """De fusies uit de vaste regels van `fusies.in_reeks`; een regel in een andere vorm (een storing) blijft weg."""
    breuken = []
    for regel in regels:
        if not (kop := _FUSIE_KOP.match(regel)):
            continue
        for deel in _FUSIE_DEEL.finditer(regel):
            maand = deel["maand"]
            if maand not in _MAANDEN:
                continue
            jaar = _eerste_telling(int(deel["dag"]), _MAANDEN.index(maand) + 1, int(deel["jaar"]))
            voor = deel["voor"]
            breuken.append(Trendbreuk(jaar, f"fusie: {voor}", f"RIO, fusie bij {kop['wie']}", regel))
    return breuken


def van_key(data_key: str | None) -> list[Trendbreuk]:
    """Alle trendbreuken achter de tabel van `data_key`: CBS-definitiebreuken en fusies binnen de reeks."""
    known = store.meta(data_key) if data_key else None
    if known is None:
        return []
    breuken = fusie(known.fusies)
    if known.bron == "cbs":
        breuken = cbs(known.dataset) + breuken
    return breuken


def jaar_van(waarde) -> int | None:
    """Het (start)jaar van een waarde op een tijdas: 2020, "2020", "2020/21", "2020SJ00", "2020JJ00"."""
    if isinstance(waarde, bool):
        return None
    if isinstance(waarde, int | float):
        return int(waarde) if 1900 <= waarde <= 2100 else None
    tekst = str(waarde).strip()
    if (start := periode.startjaar_van_spelling(tekst)) is not None:
        return start
    match = _JAAR.match(tekst)
    return int(match.group(0)) if match else None


def in_bereik(breuk: Trendbreuk, jaren: list[int]) -> bool:
    """Valt de breuk binnen de getekende reeks: na het eerste jaar en uiterlijk op het laatste?"""
    return breuk.jaar is not None and bool(jaren) and min(jaren) < breuk.jaar <= max(jaren)


def plek(breuk: Trendbreuk, posities: dict[int, object]) -> object | None:
    """De x-waarde waar de lijn komt: het jaar zelf, of anders het eerste getekende jaar erna."""
    later = sorted(j for j in posities if breuk.jaar is not None and j >= breuk.jaar)
    return posities[later[0]] if later else None


def lijn(x) -> dict:
    """De gestippelde verticale lijn over de hele hoogte van het plotvlak."""
    return {
        "type": "line",
        "name": NAAM,
        "xref": "x",
        "yref": "paper",
        "x0": x,
        "x1": x,
        "y0": 0,
        "y1": 1,
        "line": {"color": KLEUR, "width": 1.5, "dash": "dot"},
        "layer": "below",
    }


def label(x, tekst: str) -> dict:
    """Het label naast de lijn, bovenin het plotvlak: erboven staat in afdruk en rapport de bronregel (#1257). Op een
    smal scherm haalt de chat het weg; de noot onder de figuur blijft (#1262)."""
    return {
        "name": NAAM,
        "x": x,
        "xref": "x",
        "xshift": 4,
        "y": 1,
        "yref": "paper",
        "text": tekst,
        "showarrow": False,
        "xanchor": "left",
        "yanchor": "top",
        "font": {"size": 11, "color": KLEUR},
    }
