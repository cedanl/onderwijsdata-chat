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

# De eigen Bronnen-kop van het model (**Bronnen**, **Bronnen:** of **Bronnen**:) met de regels eronder:
# tot een lege regel zonder lijstitem erna, een vetgedrukte kop zoals **Definities**, of het einde.
_EIGEN_BRONNEN = re.compile(
    r"\n*^\*\*Bronnen(?::\*\*|\*\*:?)[^\n]*"
    r"(?:\n(?!\n|\*\*)[^\n]*|\n+(?=[ \t]*(?:[-*+]|\d+[.)])[ \t])[^\n]*)*",
    re.MULTILINE,
)


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
    return _EIGEN_BRONNEN.sub("", tekst) if bronnen else tekst
