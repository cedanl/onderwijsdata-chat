"""Vragenlijst voor feedback op rapporten en dashboards (#250, #253).

Eén definitie voor backend en frontend: de frontend haalt de vragen op via
GET /api/feedback/questions en de backend toetst ingestuurde antwoorden eraan.
Een vraag wijzigen is dus één aanpassing hier (wel een redeploy).

Vraag-id's zijn tekst en blijven stabiel: ze staan als sleutel in de opgeslagen
antwoorden. Een vraag schrappen of herformuleren mag; een id hergebruiken voor
een andere vraag niet, anders lopen oude en nieuwe antwoorden door elkaar.
"""

_SCALE = ["1", "2", "3", "4", "5"]
MAX_TEXT_LENGTH = 2000

QUESTIONS: tuple[dict, ...] = (
    {
        "id": "nuttig",
        "text": "Hoe nuttig was dit rapport voor je?",
        "type": "scale",
        "options": _SCALE,
        "labels": ["Niet nuttig", "Zeer nuttig"],
    },
    {
        "id": "duidelijk",
        "text": "Hoe duidelijk is de data gepresenteerd?",
        "type": "scale",
        "options": _SCALE,
        "labels": ["Onduidelijk", "Zeer duidelijk"],
    },
    {
        "id": "vertrouwen",
        "text": "Vertrouw je de cijfers in dit rapport?",
        "type": "choice",
        "options": ["Ja", "Deels", "Nee", "Weet ik niet"],
    },
    {
        "id": "delen",
        "text": "Zou je dit rapport delen met collega's?",
        "type": "choice",
        "options": ["Ja", "Misschien", "Nee"],
    },
    {"id": "mist", "text": "Mist er iets in dit rapport?", "type": "text"},
    {"id": "verbeteren", "text": "Wat zou je willen verbeteren?", "type": "text"},
)

_BY_ID = {q["id"]: q for q in QUESTIONS}


def validate_answers(answers: dict) -> dict[str, str]:
    """De ingevulde antwoorden, getoetst aan QUESTIONS; ValueError bij iets onbekends.

    Alle vragen zijn optioneel, maar een inzending zonder enig antwoord wordt
    geweigerd. Lege antwoorden vallen weg; tekst wordt bijgeknipt.
    """
    result: dict[str, str] = {}
    for qid, raw in answers.items():
        question = _BY_ID.get(qid)
        if question is None:
            raise ValueError(f"Onbekende vraag: {qid}")
        if not isinstance(raw, str):
            raise ValueError(f"Antwoord op {qid} moet tekst zijn")
        value = raw.strip()
        if not value:
            continue
        if question["type"] == "text":
            if len(value) > MAX_TEXT_LENGTH:
                raise ValueError(f"Antwoord op {qid} is langer dan {MAX_TEXT_LENGTH} tekens")
        elif value not in question["options"]:
            raise ValueError(f"Ongeldig antwoord op {qid}: {value}")
        result[qid] = value
    if not result:
        raise ValueError("Vul minstens één vraag in")
    return result
