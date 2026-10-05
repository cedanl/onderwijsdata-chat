"""Het antwoord spreekt de gebruiker aan, niet de controle of de tools (#215).

Audit 10 en 11: na een correctieronde opende het antwoord met "ik schreef 'ruim
3.400'", "De correctie is terecht", "Volledig antwoord op basis van opgehaalde
data:" of "bevestigd door compute_kpi". Dat is een gesprek met de controle, en de
gebruiker heeft de eerdere versie nooit gezien.

Ook interne tekst van de modelkoppeling hoort er niet in, zoals "[System: Empty
message content sanitised to satisfy protocol]" (#322).
"""

import re

from tools.schemas import TOOL_SCHEMAS

from .probleem import Probleem

_TOOLS = sorted(t["function"]["name"] for t in TOOL_SCHEMAS)
_META = re.compile(
    r"\bik schreef\b|\beerdere versie\b|\bde correctie\b|\bde controle\b|^\W*volledig antwoord\b"
    # LiteLLM's placeholder for an empty assistant message; leaked once after a clarification (#322).
    r"|\[system:"
    rf"|\b(?:{'|'.join(_TOOLS)})\b",
    re.IGNORECASE | re.MULTILINE,
)


def metatekst(tekst: str) -> list[str]:
    gevonden = list(dict.fromkeys(m.group(0).strip().lower() for m in _META.finditer(tekst)))
    if not gevonden:
        return []
    # De gevonden woorden alleen voor het model: een toolnaam hoort ook niet in de melding.
    return [
        Probleem(
            "Het antwoord verwijst naar een eerdere versie of een interne verwerkingsstap.",
            f"Gevonden: {', '.join(gevonden)}. Schrijf het antwoord voor de gebruiker: geen verwijzing naar een "
            "eerdere versie, de controle of toolnamen.",
        )
    ]
