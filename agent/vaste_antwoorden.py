"""Antwoorden die uit code komen, niet uit het model (#324, #330).

Een vraag naar de betekenis van een sentinel en een weigering van een vraag buiten
het domein hebben één juist antwoord. Per model verschilde het: uit het geheugen
("doorgaans 1-4 personen") of een kale "Ik kan geen antwoord geven".
"""

import re

from core.sentinels import BETEKENIS

_MIN = r"[-−–]\s?1"
_SENTINELVRAAG = re.compile(
    rf"\b(?:wat\s+(?:betekent|beteken|is|zegt)|waarvoor\s+staat|wat\s+houdt)\b[^?.\n]{{0,40}}(?<![\w.,]){_MIN}(?![\d.,])",
    re.IGNORECASE,
)

SENTINEL_ANTWOORD = (
    f"In DUO-bestanden is −1 een {BETEKENIS}. De app behandelt zulke cellen als leeg en meldt bij een totaal dat "
    "het een ondergrens is, omdat de onderdrukte aantallen erbij ontbreken. Een drempel of een bandbreedte "
    "(bijvoorbeeld 'minder dan 10') noemt de app niet: die staat niet in de brontekst die de app gebruikt.\n\n"
    "Bron: de DUO-bestandsbeschrijving, zoals vastgelegd in de app."
)

_WEIGERING = re.compile(
    r"\bkan\s+(?:u|je|jou)?\s*(?:hier|daar|hierbij|dit)?\s*geen\s+antwoord\b"
    r"|\bkan\s+(?:daar|hier|hierbij|dit)\s+niet\s+mee\s+helpen\b"
    r"|\bkan\s+(?:u|je)\s+(?:hier|daar)?\s*niet\s+helpen\b"
    r"|\bvalt\s+(?:daar|hier|dit)?\s*buiten\b"
    r"|\bbuiten\s+(?:mijn|het)\s+(?:bereik|domein|onderwerp|scope)\b",
    re.IGNORECASE,
)

WEIGER_ANTWOORD = (
    "Deze vraag valt buiten wat ik kan beantwoorden: ik werk met open Nederlandse onderwijsdata (CBS, DUO en RIO).\n\n"
    "Vragen die wel kunnen:\n"
    "- Hoeveel eerstejaars had de Hogeschool Utrecht in 2024/25?\n"
    "- Hoe ontwikkelde het aantal wo-studenten zich de afgelopen vijf jaar?\n"
    "- Welke hbo-opleidingen hebben de meeste deeltijdstudenten?"
)


def sentinelvraag(vraag: str) -> str | None:
    """Het vaste antwoord als de vraag naar de betekenis van -1 gaat."""
    return SENTINEL_ANTWOORD if _SENTINELVRAAG.search(vraag) else None


def weigering(tekst: str, tool_calls: list[dict]) -> str | None:
    """Het vaste weigerantwoord als het model zonder tools een vraag afwijst."""
    if tool_calls or not _WEIGERING.search(tekst):
        return None
    return WEIGER_ANTWOORD
