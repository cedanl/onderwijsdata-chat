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
# "Anders" in een meerkeuzevraag: kaal, of "Anders: <wat>" met een korte toelichting.
OTHER = "Anders"
MAX_OTHER_LENGTH = 200

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
        "id": "vertrouwen_waarom",
        "text": "Kun je toelichten waarom je de cijfers (niet) vertrouwt?",
        "type": "text",
    },
    {
        "id": "delen",
        "text": "Zou je dit rapport delen met collega's?",
        "type": "choice",
        "options": ["Ja", "Misschien", "Nee"],
    },
    {"id": "mist", "text": "Mist er iets in dit rapport?", "type": "text"},
    {"id": "verbeteren", "text": "Wat zou je willen verbeteren?", "type": "text"},
    # Vragen over de instelling (conferentie): niet over dit rapport, maar wel hier gesteld.
    {
        "id": "poc",
        "section": "Over jouw instelling",
        "text": "Zie je voor komend jaar mogelijkheden om een PoC te doen binnen je instelling?",
        "type": "scale",
        "options": _SCALE,
        "labels": ["Geen mogelijkheden", "Zeker mogelijk"],
    },
    {
        "id": "dashboardtool",
        "text": "Welke dashboardtool gebruiken jullie? (meerdere antwoorden)",
        "type": "multi",
        "options": ["Power BI", "Tableau", "Qlik", OTHER, "Weet ik niet"],
    },
    {
        "id": "doelgroep",
        "text": "Voor welke doelgroep(en) wil je data inzichtelijk maken? (meerdere antwoorden)",
        "type": "multi",
        "options": [
            "Bestuur",
            "Management",
            "Opleidingen en docenten",
            "Beleidsmedewerkers",
            "Studenten",
            "Externe partijen",
            OTHER,
        ],
    },
    {"id": "ceda_oppakken", "text": "Wat moet CEDA wat jou betreft oppakken?", "type": "text"},
    {
        "id": "contact",
        "text": "Wil je contactgegevens achter laten, zodat we je eventueel vervolgvragen kunnen stellen?",
        "type": "text",
    },
)

_BY_ID = {q["id"]: q for q in QUESTIONS}


def _validate_multi(qid: str, question: dict, raw: list) -> list[str]:
    """De gekozen opties van een meerkeuzevraag, zonder dubbelen; "Anders: <wat>" telt als de optie Anders."""
    chosen: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ValueError(f"Antwoord op {qid} moet een lijst met tekst zijn")
        value = item.strip()
        if value.startswith(f"{OTHER}:"):
            detail = value.removeprefix(f"{OTHER}:").strip()
            if not detail or len(detail) > MAX_OTHER_LENGTH:
                raise ValueError(f"Toelichting bij {OTHER} op {qid} moet 1 tot {MAX_OTHER_LENGTH} tekens zijn")
            value = f"{OTHER}: {detail}"
        elif value not in question["options"]:
            raise ValueError(f"Ongeldig antwoord op {qid}: {value}")
        if value not in chosen:
            chosen.append(value)
    return chosen


def validate_answers(answers: dict) -> dict[str, str | list[str]]:
    """De ingevulde antwoorden, getoetst aan QUESTIONS; ValueError bij iets onbekends.

    Alle vragen zijn optioneel, maar een inzending zonder enig antwoord wordt
    geweigerd. Lege antwoorden vallen weg; tekst wordt bijgeknipt. Een
    meerkeuzevraag (type "multi") antwoordt met een lijst, de rest met tekst.
    """
    result: dict[str, str | list[str]] = {}
    for qid, raw in answers.items():
        question = _BY_ID.get(qid)
        if question is None:
            raise ValueError(f"Onbekende vraag: {qid}")
        if question["type"] == "multi":
            if not isinstance(raw, list):
                raise ValueError(f"Antwoord op {qid} moet een lijst zijn")
            if chosen := _validate_multi(qid, question, raw):
                result[qid] = chosen
            continue
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
