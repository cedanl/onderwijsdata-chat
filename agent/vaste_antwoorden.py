"""Antwoorden die uit code komen, niet uit het model (#324, #330).

Een vraag naar de betekenis van een sentinel en een weigering van een vraag buiten
het domein hebben één juist antwoord. Per model verschilde het: uit het geheugen
("doorgaans 1-4 personen") of een kale "Ik kan geen antwoord geven".

Code beslist, niet het model (#403): ook een langere vraag over -1 krijgt het
vaste antwoord, en een antwoord met feiten zonder enige opgehaalde data (een
verzonnen wedstrijddatum) wordt de vaste weigering, ook als het model niet weigert.
"""

import re

from core.sentinels import BETEKENIS

_MIN = r"[-−–]\s?1"
_SENTINELVRAAG = re.compile(
    rf"\b(?:wat\s+(?:betekent|beteken|is|zegt)|waarvoor\s+staat|wat\s+houdt)\b[^?.\n]{{0,40}}(?<![\w.,]){_MIN}(?![\d.,])",
    re.IGNORECASE,
)
# Een langere vraag: "... staan soms waarden van -1. Wat betekent dat, en hoe reken ik ermee?" (#403)
_LOSSE_MIN_EEN = re.compile(rf"(?<![\w.,]){_MIN}(?![\d]|[.,]\d)")  # -1. aan zinseinde wel, -1,5 niet
_BETEKENISWOORD = re.compile(
    r"\b(?:betekent|betekenis|beteken|staat\s+(?:dat|dit|het)?\s*voor|waarvoor\s+staat|houdt\s+(?:dat|dit|het)\s+in)\b",
    re.IGNORECASE,
)
# Een feitelijke bewering: een getal of jaartal. Zonder opgehaalde data heeft die geen bron.
_GETAL = re.compile(r"\d")

SENTINEL_ANTWOORD = (
    f"In DUO-bestanden is −1 een {BETEKENIS}. Een totaal over zulke cellen is daarom een ondergrens: "
    "de onderdrukte aantallen ontbreken erin.\n\n"
    "Voor kleine aantallen noemt DUO in de bestandsbeschrijving de regel '1 t/m 4 gepubliceerd als 4'. "
    "Niet elk bestand volgt die: de vo-bestanden publiceren een aantal van 1 t/m 4 als 4 (een som is dan een "
    "bovengrens), andere bestanden, zoals die van het hoger onderwijs, zetten kleine aantallen op −1. Welk aantal "
    "achter een −1 zit, staat niet in de DUO-beschrijving.\n\n"
    "Bron: de DUO-bestandsbeschrijving, getoetst aan de data van de bestanden."
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
    if _SENTINELVRAAG.search(vraag) or (_LOSSE_MIN_EEN.search(vraag) and _BETEKENISWOORD.search(vraag)):
        return SENTINEL_ANTWOORD
    return None


def weigering(tekst: str, tool_calls: list[dict], eerder_gesprek: bool = False) -> str | None:
    """Het vaste weigerantwoord als het model zonder tools weigert of iets beweert.

    Een vervolgvraag op een eerder antwoord of eerder opgehaalde data (`eerder_gesprek`)
    mag zonder tools een getal noemen; een eerste antwoord zonder enige data niet.
    """
    if tool_calls:
        return None
    if _WEIGERING.search(tekst) or (not eerder_gesprek and _GETAL.search(tekst)):
        return WEIGER_ANTWOORD
    return None
