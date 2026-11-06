"""Een codeverzoek krijgt de code van de app, niet een script van het model (#959).

Review 08-B9: na "Geef de code om dit zelf na te rekenen" schreef het model een script dat een verzonnen CSV-bestand
inlas, met "pas de kolomnamen aan". De juiste snippet (`skdb.lees(*skdb.haal_op())`, met de sleutel uit de omgeving)
stond in het tool_end-event achter "Bekijk code", maar het model ziet die snippet niet. Hier beslist code: is de vraag
een codeverzoek, dan zet de app de snippet van de laatste datastap van het gesprek onder het antwoord, letterlijk zoals
onder "Bekijk code". De systeemprompt zegt het model geen eigen script te schrijven.
"""

import re

CODEKOP = "### Code"
_UITLEG = 'De code van de laatste stap, dezelfde als onder "Bekijk code" bij die stap:'

# Een verzoek om code of een script, of om de uitkomst zelf na te rekenen. "code" telt alleen als los woord: geen
# CROHO-code, brincode of opleidingscode, en niet "de code van de opleiding" (een vraag naar een sleutel).
_CODEWOORD = re.compile(r"\b(?:script|snippet|python|pandas|notebook|jupyter)\b", re.IGNORECASE)
_CODE = re.compile(
    r"(?<![\w-])code\b(?!\s+(?:van|voor)\s+(?:de|het|deze|dit|die)?\s*(?:opleiding|instelling|studie|school))",
    re.IGNORECASE,
)
_NAREKENEN = re.compile(
    r"\bzelf\b.{0,40}\b(?:na\s*te\s*rekenen|narekenen|reproduceren|nabouwen)\b|\breproduc", re.IGNORECASE
)


def is_codeverzoek(vraag: str) -> bool:
    """Vraagt de gebruiker om de code achter een uitkomst?"""
    return bool(_CODEWOORD.search(vraag) or _CODE.search(vraag) or _NAREKENEN.search(vraag))


def met_code(tekst: str, snippet: str) -> str:
    """Het antwoord met de snippet eronder, onder een vaste kop."""
    return f"{tekst.rstrip()}\n\n{CODEKOP}\n{_UITLEG}\n\n```python\n{snippet.strip()}\n```"


def laatste_snippet(event: dict) -> str | None:
    """De snippet van een tool_end-event, als die er is."""
    snippet = event.get("snippet") if event.get("type") == "tool_end" else None
    return snippet if isinstance(snippet, str) and snippet.strip() else None
