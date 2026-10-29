"""De bronnen onder een dataantwoord, uit de toolstappen van de beurt (#416, CH-09).

Het model schreef zelf een Bronnen-sectie. Vijf keer dezelfde vraag gaf de ene keer één bron,
de andere keer twee, met een eigen titel of zonder periode. Welke data de beurt las, staat in
de stappen: de app zet die lijst onder het antwoord, en de eigen sectie van het model vervalt,
net als zijn Definities bij een teldefinitie uit de bron (agent/telling.py, #402).

Elke regel linkt naar de bronpagina van zijn dataset (#621), met de documentatie-URL uit de
catalogus: dezelfde link als onder een rapportgrafiek (agent/figuurbron.py, #569).
"""

import json
import re
from collections.abc import Callable

from tools import store
from tools.arbeidsmarkt import DATASET
from tools.catalog import documentatie_url
from tools.inspectie import BRONNAAM, BRONTITEL
from tools.rio_instelling import ERKENNINGEN
from tools.schemas import TOOL_GET_INSPECTIEOORDEEL, TOOL_GET_RIO_INSTELLING

from .meetwaarden import meetwaarden
from .selectie import SCHEIDING, laadkey, selectie_in_woorden, stapkeys

# Een bronregel en de dataset waar hij over gaat; None als de stap die niet noemt.
Bronregel = tuple[str, str | None]

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


def _datasetbron(key: str) -> Bronregel | None:
    """De geladen dataset achter een key in woorden, met zijn ID; None als hij onbekend is (CH-30)."""
    geladen = laadkey(key)
    if not (known := store.meta(geladen)) or not (tekst := selectie_in_woorden(geladen)):
        return None
    # Zonder catalogustitel is de titel het ID al.
    return (tekst if known.dataset in tekst else f"{tekst} ({known.dataset})"), str(known.dataset)


def _registerbron(tool: str, result: str) -> list[Bronregel]:
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
    return [(f"{tekst}, peildatum {parsed['peildatum']}" if parsed.get("peildatum") else tekst, ERKENNINGEN)]


def _inspectie(tool: str, result: str) -> dict | None:
    """De bron van een Inspectie-oordeel (#749): het peilbestand per bestuur, met peildatum en link."""
    if tool != TOOL_GET_INSPECTIEOORDEEL:
        return None
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return None
    bron = parsed.get("bron") if isinstance(parsed, dict) else None
    return bron if isinstance(bron, dict) else None


def _inspectiebron(tool: str, result: str) -> list[Bronregel]:
    if (bron := _inspectie(tool, result)) is None:
        return []
    tekst = f"{BRONNAAM}{SCHEIDING}{BRONTITEL}"
    return [(f"{tekst}, peildatum {bron['peildatum']}" if bron.get("peildatum") else tekst, None)]


def _stapbronnen(tool: str, result: str) -> list[Bronregel]:
    datasets = [bron for key in stapkeys(result) if (bron := _datasetbron(key))]
    # Een UWV- of ROA-resultaat van vóór #577 heeft geen tabel in de store: dan is zijn bron die van zijn
    # citaties (agent/meetwaarden.py), en zijn dataset die van de tool. Met een data_key staat de bron, met
    # peildatum of versie, al in `datasets`.
    buiten_de_store = [(w.bron, DATASET.get(tool)) for w in meetwaarden(result, tool) if w.bron]
    return datasets + buiten_de_store + _registerbron(tool, result) + _inspectiebron(tool, result)


def _bronregels(steps: list[tuple[str, str]]) -> dict[str, str | None]:
    """Elke bronregel één keer, in volgorde van eerste gebruik, met de dataset van dat eerste gebruik."""
    regels: dict[str, str | None] = {}
    for tool, result in steps:
        for tekst, dataset in _stapbronnen(tool, result):
            regels.setdefault(tekst, dataset)
    return regels


def bronnen_van(steps: list[tuple[str, str]]) -> list[str]:
    """Elke geladen dataset en elke bron buiten de store één keer, in volgorde van eerste gebruik.

    Leeg als de beurt geen data las. Alleen de stappen tellen, niet wat het model schreef.
    """
    return list(_bronregels(steps))


def bronlinks_van(steps: list[tuple[str, str]]) -> dict[str, str]:
    """Bronregel → link naar de bronpagina (#621), voor dezelfde stappen en regels als `bronnen_van`.

    De link is de documentatie-URL van de dataset in de catalogus, alleen als http(s)-adres. Een regel
    zonder dataset die de catalogus kent, of zonder zo'n link, staat er niet in: die blijft tekst, geen gok.
    """
    links = {
        tekst: url for tekst, dataset in _bronregels(steps).items() if dataset and (url := documentatie_url(dataset))
    }
    # Het Inspectie-oordeel staat niet in de catalogus: zijn link is het peilbestand zelf (#749).
    for tool, result in steps:
        bron, regels = _inspectie(tool, result), _inspectiebron(tool, result)
        if bron and regels and str(bron.get("url") or "").startswith("https://"):
            links.setdefault(regels[0][0], str(bron["url"]))
    return links


def zonder_bronnensectie(tekst: str) -> str:
    """Het antwoord zonder de eigen Bronnen-sectie van het model."""
    return _EIGEN_BRONNEN.sub(_zonder_sectie, tekst)


def zonder_eigen_bronnen(tekst: str, bronnen: list[str]) -> str:
    """Het antwoord zonder de eigen Bronnen-sectie van het model, als de app de bronnen zelf geeft."""
    return zonder_bronnensectie(tekst) if bronnen else tekst


def buiten_bronnensectie(tekst: str, omzetten: Callable[[str], str]) -> str:
    """`omzetten` op het antwoord, niet op de eigen Bronnen-sectie van het model: een brontitel is een citaat."""
    stukken, vorige = [], 0
    for sectie in _EIGEN_BRONNEN.finditer(tekst):
        stukken += [omzetten(tekst[vorige : sectie.start()]), sectie.group(0)]
        vorige = sectie.end()
    return "".join([*stukken, omzetten(tekst[vorige:])])
