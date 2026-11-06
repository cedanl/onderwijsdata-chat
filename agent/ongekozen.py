"""Een studie of instelling die de gebruiker niet koos, hoort niet in het antwoord (#961, #970).

Review 08-B5: "Wat verdienen afgestudeerden Psychologie?" Bij meer studies met die naam geeft get_studiekeuze een
melding met de opties en de vaste zin dat de gebruiker kiest (`studiekeuze.KIES_EERST`). Het model haalde daarna zelf
drie studiecodes uit die opties op en beantwoordde ze allemaal. Deze controle ziet dat in de stappen van de beurt: een
studiecode uit een keuzemelding die daarna toch geladen werd, terwijl de vraag hem niet noemt. Hetzelfde geldt voor
"Meer instellingen passen": een BRIN-code uit die melding, geladen terwijl de vraag de code noch de naam noemt (#970).
De herkansing vraagt om de keuze; de cijfers kwamen wel uit de tool, dus het probleem is zacht.

Na drie keuzevragen is clarify_scope niet meer in de toolset (agent/run.py, `tools_for`): de herkansing en
`KIES_EERST` zeggen daarom ook wat het model dan doet, de keuze als vraag in het antwoord stellen (#970).
"""

import json
import re
from dataclasses import dataclass

from tools.studiekeuze import DATASET, KIES_EERST

from .probleem import Probleem

_STUDIECODE = re.compile(r"studiecode (\d{5})")
_INSTELLING = re.compile(r"([^:;]+?) \((\d{2}[A-Z]{2})\)")


@dataclass(frozen=True)
class _Soort:
    """Een keuzemelding van get_studiekeuze: hoe ze begint, hoe ze haar opties noemt en welk selectieveld de keuze is."""

    begin: str
    veld: str
    woord: str  # in de melding: "studies", "instellingen"
    code: str  # hoe de melding een code noemt


_STUDIES = _Soort("Meer studies passen", "opleiding", "studies", "studiecode")
_INSTELLINGEN = _Soort("Meer instellingen passen", "instelling", "instellingen", "BRIN-code")


def _opties(soort: _Soort, resultaat: str) -> dict[str, str]:
    """Code → naam van de opties in een keuzemelding van deze soort; leeg voor elk ander resultaat."""
    if not resultaat.startswith(soort.begin) or KIES_EERST not in resultaat:
        return {}
    lijst = resultaat.split(": ", 1)[-1]
    if soort is _STUDIES:
        return {code: code for code in _STUDIECODE.findall(lijst)}
    return {code: naam.strip() for naam, code in _INSTELLING.findall(lijst)}


def _geladen(resultaat: str) -> dict:
    """De selectie waarop een uitkomst van get_studiekeuze laadde; leeg voor elk ander resultaat."""
    try:
        uit = json.loads(resultaat)
    except (TypeError, ValueError):
        return {}
    if not isinstance(uit, dict) or uit.get("dataset") != DATASET:
        return {}
    selectie = uit.get("selectie")
    return selectie if isinstance(selectie, dict) else {}


def _gekozen(vraag: str, code: str, naam: str) -> bool:
    """Noemt de vraag de code of de naam? Dan koos de gebruiker hem."""
    tekst = vraag.casefold()
    return code.casefold() in tekst or naam.casefold() in tekst


def _ongekozen(soort: _Soort, vraag: str, tool_results: list[str]) -> list[str]:
    aangeboden: dict[str, str] = {}
    ongekozen: list[str] = []
    for resultaat in tool_results:
        aangeboden |= _opties(soort, resultaat)
        code = str(_geladen(resultaat).get(soort.veld) or "")
        if code in aangeboden and not _gekozen(vraag, code, aangeboden[code]) and code not in ongekozen:
            ongekozen.append(code)
    return ongekozen


def _probleem(soort: _Soort, codes: list[str]) -> Probleem:
    return Probleem(
        f"De Studiekeuzedatabase vond meer {soort.woord} en vroeg de gebruiker te kiezen, maar het antwoord gebruikt "
        f"{soort.woord} die de gebruiker niet koos ({soort.code} {', '.join(codes)}).",
        f"Stel de keuze met clarify_scope, met de {soort.woord} uit de melding als opties; is clarify_scope er niet "
        "meer, stel de keuze dan als vraag met die opties in je antwoord. Geef nog geen cijfers.",
    )


def ongekozen_studies(vraag: str, tool_results: list[str]) -> list[Probleem]:
    """Per soort keuzemelding (studies, instellingen) één probleem als de beurt daarna iets laadde dat de gebruiker
    niet koos."""
    return [
        _probleem(soort, codes)
        for soort in (_STUDIES, _INSTELLINGEN)
        if (codes := _ongekozen(soort, vraag, tool_results))
    ]
