"""Een codeverzoek krijgt de code van de app, niet een script van het model (#959, #969).

Review 08-B9: na "Geef de code om dit zelf na te rekenen" schreef het model een script dat een verzonnen CSV-bestand
inlas, met "pas de kolomnamen aan". De juiste snippet (`skdb.lees(*skdb.haal_op())`, met de sleutel uit de omgeving)
stond in het tool_end-event achter "Bekijk code", maar het model ziet die snippet niet. Hier beslist code: is de vraag
een codeverzoek, dan zet de app onder het antwoord wat ze van de laatste datastap van het gesprek weet, letterlijk zoals
onder "Bekijk code". De systeemprompt zegt het model geen eigen script te schrijven.

Wat de app weet, is de laatste datastap, mét of zonder snippet (#969): na collegegeld (geen snippet) gaf een codeverzoek
de snippet van een eerdere stap, alsof die bij het antwoord hoorde. Een stap zonder snippet en een gesprek zonder
datastap (nieuw, of heropend: de sessie begint dan leeg) krijgen een vaste zin. Een stap die alleen de catalogus
doorzoekt of een geladen tabel beschrijft, laadt geen data: die verandert niets aan de laatste datastap.
"""

import re

from tools import LABELS
from tools.schemas import (
    TOOL_CLARIFY_SCOPE,
    TOOL_DATASET_COUNTS,
    TOOL_DATASET_DETAILS,
    TOOL_DATASET_PROFIEL,
    TOOL_GET_CBS_DIMENSION,
    TOOL_RELATIE,
    TOOL_SEARCH_CATALOG,
)

CODEKOP = "### Code"
GEEN_DATASTAP = (
    "Sinds dit gesprek open staat, heeft de app nog geen data opgehaald: er is hier geen code om te tonen. "
    'Bij een eerder antwoord staat de code onder "Bekijk code" bij de stap.'
)

# De sessiesleutel: {"label": ..., "snippet": ... of None}. Een nieuw of heropend gesprek begint met een lege sessie.
_SESSIESLEUTEL = "laatste_datastap"
# Stappen die geen data laden: de catalogus, codes van een dimensie, of een beschrijving van een tabel die er al is.
_GEEN_DATASTAP = frozenset(
    {
        TOOL_SEARCH_CATALOG,
        TOOL_DATASET_DETAILS,
        TOOL_DATASET_COUNTS,
        TOOL_DATASET_PROFIEL,
        TOOL_GET_CBS_DIMENSION,
        TOOL_RELATIE,
        TOOL_CLARIFY_SCOPE,
    }
)

# Smal (#969): alleen een woord dat programmacode noemt, "code" met een lidwoord ervoor (de code, the code) die niet
# om de code ván iets vraagt (de code van de Universiteit Utrecht is een sleutel), of zelf narekenen. Geen CROHO code,
# brin code of ISCED code (een sleutel met een spatie), geen Python-cursussen.
_PROGRAMMA = re.compile(
    r"\b(?:scripts?|snippets?|notebook|jupyter)\b"
    r"|\b(?:python|pandas)[\s-]?code\b"
    r"|\b(?:in|met|via|with|using)\s+(?:python|pandas)\b",
    re.IGNORECASE,
)
_CODE = re.compile(
    r"\b(?:de|die|deze|je|jouw|jullie|the|your|this|that)\s+code\b"
    r"(?!\s+(?:van|voor|of|for)\b(?!\s+(?:dit|deze|dat|die|het\s+antwoord|de\s+berekening|this|that|the\s+answer)\b))",
    re.IGNORECASE,
)
_NAREKENEN = re.compile(
    r"\bzelf\b.{0,40}\b(?:na\s*te\s*rekenen|narekenen|reproduceren|nabouwen)\b|\breproduc", re.IGNORECASE
)


def is_codeverzoek(vraag: str) -> bool:
    """Vraagt de gebruiker om de code achter een uitkomst?"""
    return bool(_PROGRAMMA.search(vraag) or _CODE.search(vraag) or _NAREKENEN.search(vraag))


def onthoud(session: dict, event: dict) -> None:
    """Na elk tool_end-event van een datastap: welke stap het was en haar snippet, of dat ze er geen heeft."""
    naam = event.get("name")
    if event.get("type") != "tool_end" or not isinstance(naam, str) or naam in _GEEN_DATASTAP:
        return
    snippet = event.get("snippet")
    session[_SESSIESLEUTEL] = {
        "label": LABELS.get(naam, naam),
        "snippet": snippet if isinstance(snippet, str) and snippet.strip() else None,
    }


def codeblok(session: dict) -> str:
    """Wat onder een codeverzoek komt: de snippet van de laatste datastap, of een vaste zin waarom die er niet is."""
    stap = session.get(_SESSIESLEUTEL)
    if not stap:
        return f"{CODEKOP}\n{GEEN_DATASTAP}"
    label, snippet = stap["label"], stap["snippet"]
    if snippet is None:
        return (
            f'{CODEKOP}\nDe laatste datastap, "{label}", heeft geen code: voor die stap maakt de app geen code om '
            "zelf na te rekenen."
        )
    return (
        f'{CODEKOP}\nDe code van de laatste datastap, "{label}", dezelfde als onder "Bekijk code" bij die stap:\n\n'
        f"```python\n{snippet.strip()}\n```"
    )


def met_code(tekst: str, blok: str) -> str:
    """Het antwoord met het codeblok eronder; zonder blok het antwoord zelf."""
    return f"{tekst.rstrip()}\n\n{blok}" if blok else tekst
