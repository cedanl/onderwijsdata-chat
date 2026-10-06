"""Welke toolstap droeg een getal in het antwoord? (#365)

De getalcontrole (grounding) weet al welke getallen in de toolresultaten staan. Hier
komt die uitkomst naar de lezer: elk getal dat de controle doorstond, linkt naar de
eerste stap waarin het staat. Een getal dat nergens staat krijgt geen citatie; het
model schrijft zelf geen markering.
"""

import json

from tools import LABELS

from .grounding import bewijs_getallen, checked_numbers


def _veld(result: str, naam: str) -> str | None:
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return None
    value = parsed.get(naam) if isinstance(parsed, dict) else None
    return value if isinstance(value, str) else None


def citaties(tekst: str, steps: list[tuple[str, str]]) -> list[dict]:
    """Per gecontroleerd getal in `tekst`: zoals geschreven, de stap, de bron en de datakey."""
    bewijs = [(tool, result, bewijs_getallen(result)) for tool, result in steps]
    gevonden: dict[str, dict] = {}
    for geschreven, cijfers in checked_numbers(tekst):
        stap = next(((t, r) for t, r, getallen in bewijs if cijfers in getallen), None)
        if stap and geschreven not in gevonden:
            tool, result = stap
            gevonden[geschreven] = {
                "getal": geschreven,
                "tool": tool,
                "label": LABELS.get(tool, tool),
                "bron": _veld(result, "bron"),
                "data_key": _veld(result, "data_key"),
            }
    return list(gevonden.values())
