"""Een studie die de gebruiker niet koos, hoort niet in het antwoord (#961).

Review 08-B5: "Wat verdienen afgestudeerden Psychologie?" Bij meer studies met die naam geeft get_studiekeuze een
melding met de opties en de vaste zin dat de gebruiker kiest (`studiekeuze.KIES_EERST`). Het model haalde daarna zelf
drie studiecodes uit die opties op en beantwoordde ze allemaal. Deze controle ziet dat in de stappen van de beurt: een
studiecode uit een keuzemelding die daarna toch geladen werd, terwijl de vraag hem niet noemt. De herkansing vraagt om
de keuze; de cijfers kwamen wel uit de tool, dus het probleem is zacht.
"""

import json
import re

from tools.studiekeuze import DATASET, KIES_EERST

from .probleem import Probleem

_STUDIECODE = re.compile(r"studiecode (\d{5})")


def _keuzecodes(resultaat: str) -> set[str]:
    """De studiecodes die een keuzemelding van get_studiekeuze als opties noemt; leeg voor elk ander resultaat."""
    if not resultaat.startswith("Meer studies passen") or KIES_EERST not in resultaat:
        return set()
    return set(_STUDIECODE.findall(resultaat))


def _geladen_studiecode(resultaat: str) -> str | None:
    """De studiecode waarop een uitkomst van get_studiekeuze selecteerde; None voor elk ander resultaat."""
    try:
        uit = json.loads(resultaat)
    except (TypeError, ValueError):
        return None
    if not isinstance(uit, dict) or uit.get("dataset") != DATASET:
        return None
    opleiding = str((uit.get("selectie") or {}).get("opleiding") or "")
    return opleiding if re.fullmatch(r"\d{5}", opleiding) else None


def ongekozen_studies(vraag: str, tool_results: list[str]) -> list[Probleem]:
    """Eén probleem als de beurt na een keuzemelding studies laadde die de gebruiker niet koos."""
    aangeboden: set[str] = set()
    ongekozen: list[str] = []
    for resultaat in tool_results:
        aangeboden |= _keuzecodes(resultaat)
        code = _geladen_studiecode(resultaat)
        if code in aangeboden and code not in vraag and code not in ongekozen:
            ongekozen.append(code)
    if not ongekozen:
        return []
    return [
        Probleem(
            f"De Studiekeuzedatabase vond meer studies en vroeg de gebruiker te kiezen, maar het antwoord gebruikt "
            f"studies die de gebruiker niet koos (studiecode {', '.join(ongekozen)}).",
            "Stel de keuze met clarify_scope, met de studies uit de melding als opties, en geef nog geen cijfers.",
        )
    ]
