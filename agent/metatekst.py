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

In de lopende tekst haalt code alleen de vaste patronen weg die de zin heel laten:
een haakje met toolnamen ("2.724 (via `query_data`)") en een staart met via/met
vlak voor een leesteken ("2.724, berekend met `query_data`."). Een toolnaam die
dan nog staat ("Met query_data heb ik gefilterd"), blijft een herkansing: zonder
de toolnaam bleef er een kapotte zin over (#1028).
"""

import re

from tools.schemas import TOOL_SCHEMAS

from .labels import BRONNEN
from .probleem import Probleem

_TOOLS = sorted(t["function"]["name"] for t in TOOL_SCHEMAS)
_META = re.compile(
    # Geen \n voor "volledig antwoord": met \W liep elke regelstart door alle volgende lege regels, kwadratisch (#1048).
    r"\bik schreef\b|\beerdere versie\b|\bde correctie\b|\bde controle\b|^[^\w\n]*volledig antwoord\b"
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
# Lopende tekst: ", berekend met `query_data`." of "opgehaald via get_cbs_data." Alleen een kleine via/met na een
# woord of komma (geen zinsbegin) en vlak voor een leesteken of regeleinde; anders bleef er een kapotte zin over.
_TOOL_BIJZIN = re.compile(
    r"(?:\s*,\s*(?:(?:opgehaald|geraadpleegd|opgevraagd|gefilterd|berekend)\s+)?|(?<=[\w%*)`])\s+)"
    rf"(?:via|met)\s+{_TOOLNAMEN}(?=[.,;:!?)]|\s*$)"
)
_CODEBLOK = re.compile(r"^\s*(?:```|~~~)")


def _zonder_toolnamen(regel: str) -> str:
    schoon = _TOOL_LOS.sub("", _TOOL_HAAKJE.sub("", regel))
    return schoon if schoon == regel else schoon.rstrip(" ,;:")


def _bronnen_zonder_toolnamen(sectie: str) -> str:
    regels = [_zonder_toolnamen(r) for r in sectie.split("\n")]
    return "\n".join(r for r in regels if r.strip(" -*") or not r)


def _lopend_zonder_toolnamen(tekst: str) -> str:
    """De vaste patronen weg uit elke tekstregel; een codeblok of tabelregel blijft zoals hij is."""
    regels, in_code = [], False
    for regel in tekst.split("\n"):
        if _CODEBLOK.match(regel):
            in_code = not in_code
        elif not in_code and not regel.lstrip().startswith("|"):
            regel = _TOOL_BIJZIN.sub("", _TOOL_HAAKJE.sub("", regel))
        regels.append(regel)
    return "\n".join(regels)


def zonder_toolnamen(tekst: str) -> str:
    """De tekst zonder toolnamen: in de Bronnen-sectie elke toolnaam (een regel die dan leeg is, vervalt), in de
    lopende tekst alleen de vaste patronen die de zin heel laten."""
    if not (sectie := BRONNEN.search(tekst)):
        return _lopend_zonder_toolnamen(tekst)
    return (
        _lopend_zonder_toolnamen(tekst[: sectie.start(1)])
        + _bronnen_zonder_toolnamen(sectie.group(1))
        + _lopend_zonder_toolnamen(tekst[sectie.end(1) :])
    )


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
