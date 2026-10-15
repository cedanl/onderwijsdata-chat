"""Antwoorden die uit code komen, niet uit het model (#324, #330).

Een vraag naar de betekenis van een sentinel en een weigering van een vraag buiten
het domein hebben één juist antwoord. Per model verschilde het: uit het geheugen
("doorgaans 1-4 personen") of een kale "Ik kan geen antwoord geven".

Code beslist, niet het model (#403): ook een langere vraag over -1 krijgt het
vaste antwoord, en een antwoord met feiten zonder enige opgehaalde data (een
verzonnen wedstrijddatum) wordt de vaste weigering, ook als het model niet weigert.

Een vraag over po, so of vo krijgt de vaste scope-uitleg (BEV-12): het model gaf op "groep 8"
de tooltaal door ("De tool weigerde mijn selectie") zonder de reden in gewone taal.
"""

import json
import re

from core.sentinels import BETEKENIS
from tools import scopeprofiel

from .selectie import data_keys

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


# De uitleg als de beurt op de scopegrens van de chat stuit (#355, BEV-12). Gewone taal: geen tool,
# selectie of weigering, en niet dat de bron niet bestaat (zoals scopeprofiel.MELDING het model vraagt).
SCOPE_UITLEG = (
    "Deze chat beantwoordt alleen vragen over het mbo, hbo en wo. Het primair, speciaal en voortgezet onderwijs "
    "(po, so en vo, zoals de basisschool en de middelbare school) behandelt de chat niet, dus daar geeft hij "
    "geen cijfers over.\n\n"
    "Een vraag die wel kan:\n"
    "- Hoeveel eerstejaars had de Hogeschool Utrecht in 2024/25?"
)

# Tooltaal in het antwoord: "De tool weigerde mijn selectie", "de selectie werd geweigerd".
_TOOLWEIGERING = re.compile(
    r"\btools?\b[^.\n]{0,30}\bweiger|\bweiger\w*\s+(?:mijn|de|je)\s+selectie\b|\bselectie\b[^.\n]{0,30}\bgeweigerd\b",
    re.IGNORECASE,
)
# Een vraag die ook mbo, hbo of wo noemt ("hbo-studenten die van het vwo komen") valt niet buiten de scope.
_MBO_HBO_WO = re.compile(r"\b(?:mbo|hbo|wo|ho|hoger\s+onderwijs|hogescho\w*|universiteit\w*|roc)\b", re.IGNORECASE)


def _scopegrens(result: str) -> bool:
    """Weigerde een tool deze stap omdat de data over po, so of vo gaat? Een RIO-register zonder
    sectorfilter (REGISTER_MELDING) is geen po/so/vo-vraag: dat register haalt de chat voor niemand op."""
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return False
    return (
        isinstance(parsed, dict)
        and parsed.get("buiten_scope") is True
        and parsed.get("melding") != scopeprofiel.REGISTER_MELDING
    )


def scope_uitleg(tekst: str, tool_results: list[str], vraag: str) -> str | None:
    """De vaste scope-uitleg als de beurt zonder data op de scopegrens stuitte; anders None.

    Code beslist (#191): heeft een stap data geladen, dan blijft het antwoord van het model. Zonder data
    is het de uitleg als een tool de data buiten de scope legde (`buiten_scope`), of als het antwoord
    tooltaal doorgeeft op een vraag die po, so of vo noemt en geen mbo, hbo of wo."""
    if data_keys(tool_results):
        return None
    if any(_scopegrens(result) for result in tool_results):
        return SCOPE_UITLEG
    po_so_vo = scopeprofiel.PO_SO_VO.search(vraag) and not _MBO_HBO_WO.search(vraag)
    if po_so_vo and _TOOLWEIGERING.search(tekst):
        return SCOPE_UITLEG
    return None


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
