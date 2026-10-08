"""Het antwoord spreekt de gebruiker aan, niet de controle of de tools (#215).

Audit 10 en 11: na een correctieronde opende het antwoord met "ik schreef 'ruim
3.400'", "De correctie is terecht", "Volledig antwoord op basis van opgehaalde
data:" of "bevestigd door compute_kpi". Dat is een gesprek met de controle, en de
gebruiker heeft de eerdere versie nooit gezien.

Ook interne tekst van de modelkoppeling hoort er niet in, zoals "[System: Empty
message content sanitised to satisfy protocol]" (#322).

Een toolnaam in de Bronnen-sectie ("RIO (via `get_rio_instelling`)") is geen
gesprek met de controle, alleen een detail te veel. Die haalt code eruit, zonder
herschrijving: elke herschrijving kost een modelronde (CH-01).
"""

import re

from tools.schemas import TOOL_SCHEMAS

from .labels import BRONNEN
from .probleem import Probleem

_TOOLS = sorted(t["function"]["name"] for t in TOOL_SCHEMAS)
_META = re.compile(
    r"\bik schreef\b|\beerdere versie\b|\bde correctie\b|\bde controle\b|^\W*volledig antwoord\b"
    # LiteLLM's placeholder for an empty assistant message; leaked once after a clarification (#322).
    r"|\[system:"
    rf"|\b(?:{'|'.join(_TOOLS)})\b",
    re.IGNORECASE | re.MULTILINE,
)

# Eén toolnaam of een opsomming ervan, met of zonder backticks en haakjes: `query_data`, get_cbs_data().
_TOOLNAAM = rf"`?\b(?:{'|'.join(_TOOLS)})\b(?:\(\))?`?"
_TOOLNAMEN = rf"{_TOOLNAAM}(?:\s*(?:,|en)\s*{_TOOLNAAM})*"
_VIA = r"\b(?:via|met)\s+"
# "(via `get_rio_instelling`)" of "(`get_cbs_data`, `query_data`)": het hele haakje gaat weg.
_TOOL_HAAKJE = re.compile(rf"\s*\((?:[\w ]*?{_VIA})?{_TOOLNAMEN}\s*\)", re.IGNORECASE)
# ", opgehaald via get_rio_instelling" of een losse toolnaam.
_TOOL_LOS = re.compile(
    rf"(?:\s*,)?(?:\s+(?:opgehaald|geraadpleegd|opgevraagd|gefilterd|berekend))?\s*(?:{_VIA})?{_TOOLNAMEN}",
    re.IGNORECASE,
)


def _zonder_toolnamen(regel: str) -> str:
    schoon = _TOOL_LOS.sub("", _TOOL_HAAKJE.sub("", regel))
    return schoon if schoon == regel else schoon.rstrip(" ,;:")


def zonder_toolnamen(tekst: str) -> str:
    """De tekst zonder toolnamen in de Bronnen-sectie; een regel die dan leeg is, vervalt."""
    if not (sectie := BRONNEN.search(tekst)):
        return tekst
    regels = [_zonder_toolnamen(r) for r in sectie.group(1).split("\n")]
    schoon = "\n".join(r for r in regels if r.strip(" -*") or not r)
    return tekst[: sectie.start(1)] + schoon + tekst[sectie.end(1) :]


def metatekst(tekst: str) -> list[str]:
    gevonden = list(dict.fromkeys(m.group(0).strip().lower() for m in _META.finditer(zonder_toolnamen(tekst))))
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
