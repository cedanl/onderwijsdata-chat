"""Een vraag over een vo-school krijgt de scope-uitleg uit code, vóór elke kaart en vóór het model (#549).

"Hoeveel leerlingen heeft het Erasmus Gymnasium in Rotterdam?" kreeg de plaatskaart "Over welke
'Rotterdam'?" met de Erasmus Universiteit als optie: een stille herinterpretatie, terwijl vo buiten
de scope valt (#355). Code herkent een vo-schoolnaam aan een schooltype als eigennaam: een naamwoord
direct voor of na gymnasium, lyceum, atheneum of scholengemeenschap ("Erasmus Gymnasium", "Gymnasium
Haganum", "Christelijk Lyceum Zeist"), en "college" alleen na een naam met hoofdletter ("Mendel
College"). Een los typewoord ("van het vwo of gymnasium") is een vooropleiding, geen school: een
ho-vraag met vo-context blijft bij het model (epic #554).

Een naam heeft een hoofdletter, behalve bij wie nergens hoofdletters typt; de hoofdletter van het
eerste woord van een zin telt alleen als het typewoord er zelf ook een heeft ("Aandeel gymnasium
leerlingen" is geen school). Noemt de vraag een sector of studenten ("wo-studenten",
"eerstejaars", "naar het mbo"), dan is het een ho-vraag met vo-context en beslist deze check niet.

Mbo-instellingen dragen dezelfde typewoorden ("Grafisch Lyceum Rotterdam", "Deltion College"):
noemt de vraag een registerinstelling, een registernaam met dat schooltype ("Grafisch Lyceum
R'dam"), of een universiteit, hogeschool of ROC, dan beslist deze check evenmin. Zonder register
(offline) ook niet: dan is een mbo-naam niet uit te sluiten en gaat de vraag, zoals vroeger, naar
model en scopepoort. Een vo-school zonder typewoord ("SG Lelystad") gaat die weg ook.
"""

from __future__ import annotations

import re

from data.instellingen import get_all
from tools import instelling

from .vaste_antwoorden import VO_ANTWOORD

_TYPEWOORDEN = frozenset({"gymnasium", "lyceum", "atheneum", "scholengemeenschap", "college"})
_ALLEEN_NA_NAAM = "college"  # "College van Bestuur" is geen school
_WOORD = re.compile(r"[^\W\d_]+")
_AANSLUITEND = re.compile(r"\s*(?:-\s*)?")  # "Erasmus Gymnasium", "Erasmus-Gymnasium"
# Woorden naast een typewoord die geen schoolnaam zijn: lidwoorden, voorzetsels, werkwoorden uit
# een telvraag en vo-context ("vooropleiding gymnasium", "het categoriaal gymnasium").
_GEEN_NAAM = frozenset(
    {
        *("de", "het", "een", "dit", "dat", "deze", "die", "elk", "elke", "ieder", "iedere", "welk", "welke"),
        *("alle", "ander", "andere", "geen", "ons", "onze", "mijn", "jouw", "hun", "haar", "zijn"),
        *("van", "vanaf", "vanuit", "uit", "op", "naar", "in", "aan", "bij", "voor", "met", "zonder", "per"),
        *("door", "over", "na", "tot", "en", "of", "dan", "als", "hoeveel", "aantal", "er", "is", "was"),
        *("heeft", "hebben", "had", "hadden", "telt", "tellen", "waren", "komen", "komt", "kwam", "kwamen"),
        *("gaan", "gaat", "ging", "gingen", "zit", "zitten", "zat", "zaten", "volgt", "volgen", "volgde"),
        *("volgden", "vooropleiding", "vooropleidingen", "diploma", "opleiding", "leerlingen", "scholieren"),
        *("havo", "vwo", "vmbo", "vo", "po", "so", "aandeel", "percentage", "deel"),
        *("zelfstandig", "zelfstandige", "categoriaal", "categoriale", "regulier", "reguliere"),
    }
)
# Een mbo/hbo/wo-instelling ("Erasmus Universiteit Rotterdam", "Hanzehogeschool", "ROC van Twente") of
# ho-context ("wo-studenten", "eerstejaars", "naar het mbo") in de vraag: die blijft bij het model (epic #554).
_HO_MBO_CONTEXT = re.compile(
    r"\b(?:\w*universiteit\w*|\w*hogeschool\w*|university|roc|mbo|hbo|wo|ho|\w*student\w*|eerstejaars)\b",
    re.IGNORECASE,
)


def _aansluitend(vraag: str, links: re.Match, rechts: re.Match) -> bool:
    return bool(_AANSLUITEND.fullmatch(vraag[links.end() : rechts.start()]))


def _zinsbegin(vraag: str, woord: re.Match) -> bool:
    """Staat het woord aan het begin van de vraag of van een zin erin?"""
    for teken in reversed(vraag[: woord.start()]):
        if teken in ".!?:":
            return True
        if teken.isalnum():
            return False
    return True


def _is_naam(woord: str, zonder_hoofdletters: bool) -> bool:
    """Een eigennaam naast het typewoord; wie nergens hoofdletters typt, krijgt ze niet als eis."""
    kaal = woord.lower()
    return kaal not in _GEEN_NAAM and kaal not in _TYPEWOORDEN and (woord[0].isupper() or zonder_hoofdletters)


def _naam_ervoor(vraag: str, voor: re.Match, woord: re.Match) -> bool:
    """Een naam ervoor: "Erasmus Gymnasium", "Mendel College"; wie geen hoofdletters typt ook "erasmus gymnasium".

    Bij "college" is de hoofdletter altijd een eis.
    """
    if not _aansluitend(vraag, voor, woord):
        return False
    if voor.group()[0].isupper() and not woord.group()[0].isupper() and _zinsbegin(vraag, voor):
        return False  # "Aandeel gymnasium leerlingen": de hoofdletter is die van de zin
    zonder_hoofdletters = vraag == vraag.lower() and woord.group().lower() != _ALLEEN_NA_NAAM
    return _is_naam(voor.group(), zonder_hoofdletters)


def _naam_erna(vraag: str, woord: re.Match, na: re.Match) -> bool:
    """Een naam erna: "Gymnasium Haganum", alleen met hoofdletter en nooit na "college" ("College van Bestuur")."""
    if woord.group().lower() == _ALLEEN_NA_NAAM:
        return False
    return _aansluitend(vraag, woord, na) and _is_naam(na.group(), zonder_hoofdletters=False)


def _schoolnamen(vraag: str) -> list[str]:
    """De frasen schooltype + eigennaam in de vraag: "Erasmus Gymnasium", "Gymnasium Haganum"."""
    woorden = list(_WOORD.finditer(vraag))
    namen: list[str] = []
    for i, woord in enumerate(woorden):
        if woord.group().lower() not in _TYPEWOORDEN:
            continue
        voor = woorden[i - 1] if i > 0 else None
        na = woorden[i + 1] if i + 1 < len(woorden) else None
        if voor is not None and _naam_ervoor(vraag, voor, woord):
            namen.append(vraag[voor.start() : woord.end()])
        elif na is not None and _naam_erna(vraag, woord, na):
            namen.append(vraag[woord.start() : na.end()])
    return namen


def _genormaliseerd(tekst: str) -> str:
    return " ".join(re.sub(r"[\W_]+", " ", tekst.lower()).split())


def _in_register(naam: str, registernamen: list[str]) -> bool:
    """Staat de frase in een registernaam? "Grafisch Lyceum" in "Grafisch Lyceum R'dam", "Alfa College" in "Alfa-college"."""
    patroon = re.compile(rf"(?<!\w){re.escape(_genormaliseerd(naam))}(?!\w)")
    return any(patroon.search(registernaam) for registernaam in registernamen)


def _registernamen() -> list[str]:
    """De genormaliseerde namen uit het register; leeg zonder register (offline)."""
    try:
        return [_genormaliseerd(i["naam"]) for i in get_all() if isinstance(i.get("naam"), str)]
    except Exception:
        return []


def vo_schoolvraag(vraag: str) -> str | None:
    """Het vaste vo-antwoord als de vraag een vo-school noemt; anders None.

    Het register laadt alleen bij een schoolnaam in de vraag, maar dan over het netwerk: roep dit
    vanuit async code aan via `asyncio.to_thread`.
    """
    namen = _schoolnamen(vraag)
    if not namen or _HO_MBO_CONTEXT.search(vraag):
        return None
    registernamen = _registernamen()
    if not registernamen or instelling.noemt_instelling(vraag):
        return None
    if all(_in_register(naam, registernamen) for naam in namen):
        return None
    return VO_ANTWOORD
