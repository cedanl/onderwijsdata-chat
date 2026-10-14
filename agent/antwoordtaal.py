"""Het antwoord is in de taal van de vraag (besluit #326).

Audit 12: een Engelse vraag kreeg een Nederlands antwoord, terwijl audit 11 een Engelse
vraag wel in het Engels beantwoord kreeg. Besluit van de product owner: een Engelse vraag
krijgt een Engels antwoord, een Nederlandse vraag een Nederlands antwoord. Een Nederlands
antwoord schrijft decimalen met een komma (6,4); dat doet `getalnotatie.nl_notatie`.

De code bepaalt de taal, niet alleen de prompt: `taalinstructie` zegt het model in welke
taal het antwoordt, `verkeerde_antwoordtaal` is een zachte controle op het antwoord, en
alleen een antwoord dat niet Engels is, krijgt de Nederlandse getalnotatie.

`taal` telt veelvoorkomende woorden per taal: functiewoorden en een paar woorden die in
vragen over onderwijsdata steeds terugkomen (studenten, eerstejaars). Woorden die in beide
talen bestaan (in, is, was, of, die) tellen niet mee. Bij weinig woorden of een gemengde
tekst is de uitkomst None: dan doet de code niets, want een misser kost een modelronde of
zet een Engels antwoord in de verkeerde notatie.

Vaste teksten uit code (weigering, ingehouden antwoord, scopekaarten, meldingen) blijven
Nederlands; vertalen is een vervolgstap.
"""

import re
from typing import Literal

from .probleem import Probleem

Taal = Literal["nl", "en"]

_NEDERLANDS = frozenset(
    [
        "de",
        "het",
        "een",
        "en",
        "van",
        "voor",
        "met",
        "op",
        "te",
        "dat",
        "niet",
        "zijn",
        "er",
        "aan",
        "ook",
        "als",
        "bij",
        "maar",
        "om",
        "dan",
        "naar",
        "nog",
        "hoe",
        "wat",
        "welke",
        "welk",
        "hoeveel",
        "waar",
        "wanneer",
        "waarom",
        "wie",
        "deze",
        "dit",
        "uit",
        "tot",
        "wordt",
        "worden",
        "werd",
        "waren",
        "heeft",
        "hebben",
        "kan",
        "kunnen",
        "ik",
        "jij",
        "je",
        "wij",
        "zij",
        "hun",
        "geen",
        "meer",
        "minder",
        "alle",
        "tussen",
        "sinds",
        "onder",
        "tegen",
        "zoals",
        "omdat",
        "graag",
        "geef",
        "toon",
        "laat",
        "zou",
        "moet",
        "studenten",
        "leerlingen",
        "eerstejaars",
        "aantal",
        "jaar",
        "opleiding",
        "opleidingen",
    ]
)
_ENGELS = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "for",
        "with",
        "from",
        "by",
        "at",
        "on",
        "that",
        "this",
        "these",
        "those",
        "there",
        "their",
        "they",
        "it",
        "its",
        "are",
        "were",
        "be",
        "been",
        "has",
        "have",
        "does",
        "do",
        "did",
        "how",
        "what",
        "which",
        "many",
        "much",
        "where",
        "when",
        "why",
        "who",
        "not",
        "than",
        "more",
        "less",
        "can",
        "could",
        "would",
        "should",
        "will",
        "about",
        "into",
        "between",
        "since",
        "all",
        "each",
        "only",
        "also",
        "please",
        "show",
        "give",
        "my",
        "your",
        "our",
        "if",
        "students",
        "pupils",
        "number",
        "year",
        "years",
        "first",
    ]
)
_WOORD = re.compile(r"[^\W\d_]+")
_VOORSPRONG = 2  # zoveel herkende woorden meer dan de andere taal, minstens
_OVERWICHT = 1.5  # en de ene taal komt duidelijk vaker voor dan de andere

_NAAM = {"nl": "Nederlands", "en": "Engels"}
_INSTRUCTIE = {
    "nl": "Taal: de vraag is in het Nederlands gesteld. Schrijf het antwoord in het Nederlands.",
    "en": (
        "Taal: de vraag is in het Engels gesteld. Schrijf het hele antwoord in het Engels (Answer in English), "
        "ook als de data, de bronnen en deze instructies Nederlands zijn."
    ),
}


def taal(tekst: str) -> Taal | None:
    """ "nl" of "en" als de tekst duidelijk in die taal is; None bij twijfel (kort, gemengd of alleen namen)."""
    woorden = _WOORD.findall(tekst.lower())
    nl = sum(w in _NEDERLANDS for w in woorden)
    en = sum(w in _ENGELS for w in woorden)
    if _duidelijk(nl, en):
        return "nl"
    if _duidelijk(en, nl):
        return "en"
    return None


def _duidelijk(voor: int, tegen: int) -> bool:
    return voor >= tegen + _VOORSPRONG and voor > _OVERWICHT * tegen


def taalinstructie(vraag: str) -> str:
    """Systeemtekst voor deze beurt: antwoord in de taal van de vraag; leeg als die taal onzeker is."""
    gevraagd = taal(vraag)
    return _INSTRUCTIE[gevraagd] if gevraagd else ""


def verkeerde_antwoordtaal(vraag: str, tekst: str) -> list[Probleem]:
    """Zacht: een antwoord dat duidelijk in de andere taal is dan de vraag. Bij twijfel aan een kant niets."""
    gevraagd, geschreven = taal(vraag), taal(tekst)
    if gevraagd is None or geschreven is None or gevraagd == geschreven:
        return []
    opdracht = f"Schrijf het hele antwoord in het {_NAAM[gevraagd]}" + (
        " (Answer in English)." if gevraagd == "en" else "."
    )
    return [
        Probleem(
            f"Het antwoord is in het {_NAAM[geschreven]} geschreven, maar de vraag is in het {_NAAM[gevraagd]} gesteld.",
            opdracht,
        )
    ]
