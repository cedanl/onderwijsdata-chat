"""De bronnen onder een dataantwoord, uit de toolstappen van de beurt (#416, CH-09).

Het model schreef zelf een Bronnen-sectie. Vijf keer dezelfde vraag gaf de ene keer één bron,
de andere keer twee, met een eigen titel of zonder periode. Welke data de beurt las, staat in
de stappen: de app zet die lijst onder het antwoord, en de eigen sectie van het model vervalt,
net als zijn Definities bij een teldefinitie uit de bron (agent/telling.py, #402).
"""

import json
import re

from tools import store
from tools.schemas import TOOL_GET_RIO_INSTELLING

from .meetwaarden import meetwaarden
from .selectie import SCHEIDING, laadkey, selectie_in_woorden, stapkeys

# De eigen Bronnen-sectie van het model: de kop (**Bronnen**, **Bronnen:** of **Bronnen**:) en zijn lijst.
_KOP = r"\*\*Bronnen(?::\*\*|\*\*:?)"
_OPSOMMING = r"[ \t]*[-*+][ \t]"
_GENUMMERD = r"[ \t]*\d+[.)][ \t]"
# Onder een kale kop mogen de bronnen ook als losse regels staan, tot een lege regel, lijst of vetgedrukte kop.
_LOSSE_REGELS = rf"(?:\n(?!{_OPSOMMING}|{_GENUMMERD}|\n|\*\*)[^\n]*)*"


def _lijst(item: str) -> str:
    """Items van één soort, ook met lege regels ertussen, elk met zijn ingesprongen vervolgregels.

    Een regel die zonder inspringen tegen de lijst plakt (een kanttekening) of een lijst van een
    andere soort na een lege regel (vervolgstappen) hoort er niet meer bij.
    """
    return rf"(?:\n+{item}[^\n]*(?:\n[ \t]+\S[^\n]*)*)+"


# Alleen vanaf de eerste van een reeks lege regels: elk beginpunt erbinnen kostte kwadratische tijd
# op een lange reeks, en dat bevroor de event loop voor iedereen.
_EIGEN_BRONNEN = re.compile(
    rf"(?<!\n)\n*^{_KOP}(?:[ \t]*(?=\n|\Z){_LOSSE_REGELS}|[^\n]*)"
    rf"(?:{_lijst(_OPSOMMING)}|{_lijst(_GENUMMERD)})?(?:\n\Z)?",
    re.MULTILINE,
)


def _zonder_sectie(sectie: re.Match[str]) -> str:
    """Plakt er een regel direct onder de sectie, dan houdt die een lege regel boven zich: een eigen alinea."""
    volgt = sectie.string[sectie.end() : sectie.end() + 2]
    return "\n" if len(volgt) == 2 and volgt[0] == "\n" and volgt[1] != "\n" else ""


def _datasetbron(key: str) -> str | None:
    """De geladen dataset achter een key in woorden, met zijn ID; None als hij onbekend is (CH-30)."""
    geladen = laadkey(key)
    if not (known := store.meta(geladen)) or not (tekst := selectie_in_woorden(geladen)):
        return None
    # Zonder catalogustitel is de titel het ID al.
    return tekst if known.dataset in tekst else f"{tekst} ({known.dataset})"


def _registerbron(tool: str, result: str) -> list[str]:
    """Een opzoeking in het RIO-register (get_rio_instelling) laadt niets in de store, maar leest wel data."""
    if tool != TOOL_GET_RIO_INSTELLING:
        return []
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, dict) or not isinstance(titel := parsed.get("catalogus_titel"), str):
        return []
    bron = str(parsed.get("bron") or "RIO")
    tekst = titel if titel.startswith(bron) else f"{bron}{SCHEIDING}{titel}"
    return [f"{tekst}, peildatum {parsed['peildatum']}" if parsed.get("peildatum") else tekst]


def _stapbronnen(tool: str, result: str) -> list[str]:
    datasets = [bron for key in stapkeys(result) if (bron := _datasetbron(key))]
    # UWV en ROA staan niet in de store: hun bron is die van hun citaties (agent/meetwaarden.py).
    buiten_de_store = [w.bron for w in meetwaarden(result, tool) if w.bron]
    return datasets + buiten_de_store + _registerbron(tool, result)


def bronnen_van(steps: list[tuple[str, str]]) -> list[str]:
    """Elke geladen dataset en elke bron buiten de store één keer, in volgorde van eerste gebruik.

    Leeg als de beurt geen data las. Alleen de stappen tellen, niet wat het model schreef.
    """
    return list(dict.fromkeys(bron for tool, result in steps for bron in _stapbronnen(tool, result)))


def zonder_eigen_bronnen(tekst: str, bronnen: list[str]) -> str:
    """Het antwoord zonder de eigen Bronnen-sectie van het model, als de app de bronnen zelf geeft."""
    return _EIGEN_BRONNEN.sub(_zonder_sectie, tekst) if bronnen else tekst
