"""Gaat een vraag aantoonbaar over vervolgonderwijs? Code beslist, niet het model (#556, #191, #877).

De zoekpoort voor de vo-context (`scopeprofiel.VO_CONTEXT`) gaat open als `opent_vo_context` waar is: de
vraag noemt het hoger onderwijs (`noemt_ho`, epic #554), of ze noemt een vo-niveau samen met een vervolgdoel
(`noemt_vo_doorstroom`, besluit A van #877: ook vmbo → mbo, niet alleen naar het ho).

`noemt_ho` volgt de woordgrensregel van `tools.catalog._word_match`: korte termen (<= 3 tekens) alleen als
heel woord (`\\b<term>\\b`, dus "woning", "hoger" en "vwo" tellen niet, "wo-master" en "(wo)" wel); langere
termen als deelstring, zodat "Hanzehogeschool" en "universiteiten" meetellen. De regel is gekopieerd, niet
geïmporteerd: deze module kent alleen strings en importeert de catalogus niet.

Alleen geen marker: "instroom", "studenten", "doorstroom", "instelling" en "regio". Ze komen ook in
mbo-vragen voor; als losse marker brachten ze het lek van 6 oktober terug (`voprognoses` bij "per
instelling"). Ook "havo" en "vwo" niet (#597): een zuivere vo-vraag ("Hoeveel leerlingen zitten er op het
vwo?") opende zo de poort, tegen het scopebesluit in (#355). Een doorstroomwoord telt daarom alleen naast
een vo-niveau ("Hoeveel vmbo'ers stromen door?"), het mbo alleen naast een vo-niveau ("van het vmbo naar
het mbo"), en een vraag die het po noemt opent zo niets: po en (v)so blijven dicht. Voortijdig
schoolverlaters (vsv) zijn geen vo-niveau, maar hun terugkeer in het onderwijs is wel doorstroom.

De poort kijkt naar de vraag van de gebruiker, niet naar de zoekterm van het model (#597): anders opent
het model de poort door zelf "hbo" of "doorstroom" toe te voegen. `run()` zet die vraag per beurt
(`beurtvraag`); buiten de chat (MCP, evals) is er geen en beslist de zoekterm.

`HO_MBO_CONTEXT` is een andere, bredere wegblijf-guard (met mbo, student, eerstejaars, roc) voor de vaste
uitleg vóór het model (`agent.vo_school`, `agent.po_vraag`); `opent_vo_context` is de striktere toets voor
het zoeken.
"""

import contextlib
import re
from collections.abc import Generator
from contextvars import ContextVar

_KORT = ("wo", "ho", "hbo")
_LANG = ("hogeschool", "hogescholen", "universiteit", "universiteiten")

_KORTE_MARKER = re.compile(rf"\b(?:{'|'.join(_KORT)})\b")
_HOGER_ONDERWIJS = re.compile(r"hoger\s+onderwijs")

# Een vo-niveau (#877): de onderwijssoort, of een leerling ervan ("havisten", "vmbo'ers", "vwo-leerlingen").
# Geen vso: (v)so blijft dicht. "vo" en de soorten alleen als heel woord: "vooral", "vwoord" tellen niet.
_VO_NIVEAU = re.compile(
    r"\b(?:vo|vmbo|havo|vwo|vavo|havist(?:en)?|voortgezet\s+onderwijs|middelbare\s+scho(?:ol|len))\b", re.IGNORECASE
)
# Een vervolgdoel na het vo: het mbo of een roc, of een woord dat zegt dat leerlingen ergens heen gaan.
_MBO = re.compile(r"\b(?:mbo|roc)\b", re.IGNORECASE)
_DOORSTROOM = re.compile(
    r"\b(?:doorstro\w*|uitstro\w*|stro\w*\s+(?:\w+\s+)?(?:door|uit)|vervolgonderwijs|vervolgopleiding\w*|vervolgstudie\w*"
    r"|verder\s+(?:studeren|leren)"
    r"|na\s+(?:het\s+|hun\s+|een\s+|zijn\s+|haar\s+)?(?:behalen\s+van\s+(?:het\s+|hun\s+|een\s+)?)?"
    r"(?:eind)?(?:examen\w*|diploma\w*|diplomering)"
    r"|na\s+(?:het|de|hun)\s+(?:vmbo|havo|vwo|vo|vavo|middelbare\s+school))\b",
    re.IGNORECASE,
)
# Doorstroom binnen het vo ("van het vmbo naar de havo", "door naar de bovenbouw") is geen vervolgonderwijs.
_VO_DOEL = re.compile(
    r"\bnaar\s+(?:het\s+|de\s+|een\s+)?(?:vmbo|havo|vwo|vo|gymnasium|bovenbouw|voortgezet\s+onderwijs)\b", re.IGNORECASE
)
# Voortijdig schoolverlaters die terugkeren in het onderwijs (#877).
_VSV = re.compile(r"\b(?:vsv\w*|voortijdig(?:e)?\s+schoolverlat\w*)", re.IGNORECASE)
_TERUGKEER = re.compile(
    r"\b(?:terugke\w*|herinstro\w*|(?:ke(?:ren|ert|erden)|ko(?:men|mt))\s+(?:\w+\s+){0,3}terug)\b", re.IGNORECASE
)
# Po en (v)so: wie die noemt, opent met een doorstroomwoord niets ("doorstroom van de basisschool naar het vwo").
_PO_SO = re.compile(
    r"\b(?:po|vso|sbo|basisonderwijs|basisschool|basisscholen|primair\s+onderwijs|speciaal\s+onderwijs"
    r"|groep\s+[1-8])\b",
    re.IGNORECASE,
)

# Een mbo/hbo/wo-instelling ("Erasmus Universiteit Rotterdam", "Hanzehogeschool", "ROC van Twente") of
# ho-context ("wo-studenten", "eerstejaars", "naar het mbo") in de vraag: die blijft bij het model (epic #554).
HO_MBO_CONTEXT = re.compile(
    r"\b(?:\w*universiteit\w*|\w*hogeschool\w*|university|roc|mbo|hbo|wo|ho|\w*student\w*|eerstejaars)\b",
    re.IGNORECASE,
)

# De vraag van de gebruiker in deze beurt; taken en threads van de beurt erven hem (asyncio.to_thread).
_beurtvraag: ContextVar[str | None] = ContextVar("beurtvraag", default=None)


def noemt_ho(query: str) -> bool:
    """Waar als de vraag een ho-marker noemt (hoofdletterongevoelig)."""
    tekst = query.lower()
    return bool(_KORTE_MARKER.search(tekst) or _HOGER_ONDERWIJS.search(tekst) or any(term in tekst for term in _LANG))


def noemt_vo_doorstroom(query: str) -> bool:
    """Waar als de vraag gaat over doorstroom uit het vo naar vervolgonderwijs zonder het ho te noemen (#877).

    Een vo-niveau met het mbo of een doorstroomwoord ("van het vmbo naar het mbo", "havisten na hun diploma"),
    of voortijdig schoolverlaters die terugkeren in het onderwijs. Noemt de vraag het po of (v)so, dan niet; een
    doorstroomwoord met een vo-doel ("van het vmbo naar de havo") is doorstroom binnen het vo, en ook niet.
    """
    if _PO_SO.search(query):
        return False
    doorstroom = _DOORSTROOM.search(query) and not _VO_DOEL.search(query)
    vo_vervolg = _VO_NIVEAU.search(query) and (_MBO.search(query) or doorstroom)
    return bool(vo_vervolg or (_VSV.search(query) and _TERUGKEER.search(query)))


def opent_vo_context(query: str) -> bool:
    """Gaat de vraag over vervolgonderwijs: het ho, of doorstroom uit het vo (#877)? Dan mag de vo-context mee."""
    return noemt_ho(query) or noemt_vo_doorstroom(query)


@contextlib.contextmanager
def beurtvraag(vraag: str) -> Generator[None, None, None]:
    """Binnen dit blok beslist de zoekpoort op `vraag`, de vraag van de gebruiker (#597)."""
    token = _beurtvraag.set(vraag)
    try:
        yield
    finally:
        _beurtvraag.reset(token)


def vo_context_poort(zoekterm: str) -> bool:
    """Gaat de zoekpoort voor vo-context open (#557, #877)? Op de vraag van de gebruiker als er een beurt loopt,
    anders op de zoekterm (#597)."""
    vraag = _beurtvraag.get()
    return opent_vo_context(zoekterm if vraag is None else vraag)
