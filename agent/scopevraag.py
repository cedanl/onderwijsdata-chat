"""Verduidelijking als slots-controle in code (#348): dezelfde vage vraag, altijd dezelfde eerste stap.

Of de scopevraag in de eerste ronde komt, lag bij het model: "Hoeveel studenten heeft Utrecht?" gaf
de ene run negentien toolaanroepen zonder antwoord en de andere een goede verduidelijking (audit 12).
Hier leest code de vraag vóór het model haar ziet, op twee slots:

- **scope**: een plaatsnaam die in meer dan één instellingsnaam uit het register zit (Utrecht,
  Groningen, Amsterdam, Twente), terwijl de vraag geen instelling noemt: de kaart vraagt instelling
  of woonplaats, met de instellingen uit het register als opties.
- **maat**: een kort thema zonder maat ("studentenwelzijn", `interpretatie.is_vaag`): de kaart vraagt
  welke maat, met de catalogusrecords die `search_catalog` bovenaan zet als opties.
- **fase** (#743): instroom in het hoger onderwijs zonder fase ("de instroom van de HvA"). Eerstejaars ho (DUO)
  telt wie voor het eerst in het ho staat, dus geen doorstroom naar een master; na doorvragen bleek dat de masters
  ontbraken. De kaart vraagt welke instroom, met wat elke optie wel en niet kan.

De opties komen uit het register en de catalogus, dus ze zijn altijd geldig; het model formuleert na
de keuze het antwoord en beslist niet óf de vraag komt. Alleen in de eerste ronde (daarna is
clarify_scope ook voor het model weg, #75) en nooit als het profiel de instelling al bepaalt. De
vaste plannen voor de aanbevolen startvragen, het tweede deel van #348, wachten op het besluit in #349.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from data.instellingen import get_all
from tools import catalog, instelling, scopeprofiel

from .interpretatie import is_vaag

# Een vraag naar een aantal of een telling: dan maakt het uit of een plaats een instelling of een gebied is.
_MAAT = re.compile(
    r"\b(hoeveel|aantal(?:len)?|studenten|leerlingen|deelnemers|ingeschreven\w*|inschrijving\w*|instroom|"
    r"uitstroom|uitval|eerstejaars|gediplomeerd\w*|diploma\w*)\b",
    re.IGNORECASE,
)
# Woorden uit instellingsnamen die geen plaats zijn: soort, richting, rechtsvorm, land.
_GENERIEK = frozenset(
    {
        "hogeschool",
        "hogescholen",
        "universiteit",
        "universiteiten",
        "roc",
        "aoc",
        "college",
        "academie",
        "instituut",
        "school",
        "scholen",
        "stichting",
        "nederland",
        "nederlandse",
        "holland",
        "midden",
        "noord",
        "zuid",
        "oost",
        "west",
        "christelijke",
        "katholieke",
        "gereformeerde",
        "protestants",
        "vrije",
        "rijks",
        "open",
        "technische",
        "internationale",
        "kunsten",
        "arts",
        "university",
        "applied",
        "sciences",
    }
)
_MIN_LETTERS = 4
_MAX_INSTELLINGEN = 2
_MAX_MATEN = 3
_SECTOREN = ("wo", "hbo", "mbo")
_MAX_BESCHRIJVING = 140


@dataclass(frozen=True)
class Kaart:
    """Een verduidelijkingskaart uit code, in de vorm die de clarify_scope-tool ook geeft."""

    slot: str  # scope | maat | fase
    vraag: str
    opties: list[dict] = field(default_factory=list)


def _register() -> list[dict]:
    """De instellingen uit het register; leeg zonder register (offline), dan geen scopevraag."""
    try:
        return [i for i in get_all() if isinstance(i.get("naam"), str)]
    except Exception:
        return []


def _kaal(woord: str) -> str:
    return woord.strip("'’(),.;:-")


def _is_plaatswoord(woord: str) -> bool:
    return len(woord) >= _MIN_LETTERS and woord[0].isupper() and woord.isalpha() and woord.lower() not in _GENERIEK


def _plaatsen(register: list[dict]) -> dict[str, list[dict]]:
    """Plaats → instellingen die haar in hun naam dragen, voor plaatsen in meer dan één naam.

    Een plaats staat in een Nederlandse instellingsnaam achteraan ("Hogeschool Utrecht", "ROC van
    Twente", "Grafisch Lyceum Rotterdam"); een merknaam of soortaanduiding vooraan ("Aeres
    Hogeschool", "Theologische Universiteit") is geen plaats, ook als ze in meer namen staat.
    """
    plaatsen = {_kaal(inst["naam"].split()[-1]) for inst in register if inst["naam"].split()}
    uit: dict[str, list[dict]] = {}
    for plaats in sorted(p for p in plaatsen if _is_plaatswoord(p)):
        patroon = re.compile(rf"(?<!\w){re.escape(plaats)}(?!\w)")
        dragers = [inst for inst in register if patroon.search(inst["naam"])]
        if len(dragers) > 1:
            uit[plaats] = dragers
    return uit


# De sector die de vraag zelf noemt: dan komen alleen instellingen van die sector in aanmerking.
_SECTORWOORDEN = {
    "wo": re.compile(r"\b(wo|universiteit\w*|wo-\w+)\b", re.IGNORECASE),
    "hbo": re.compile(r"\b(hbo|hogescho(?:ol|len)|hbo-\w+)\b", re.IGNORECASE),
    "mbo": re.compile(r"\b(mbo|roc(?:'s)?|mbo-\w+)\b", re.IGNORECASE),
}


def _sector_in_vraag(vraag: str) -> str | None:
    genoemd = [sector for sector, patroon in _SECTORWOORDEN.items() if patroon.search(vraag)]
    return genoemd[0] if len(genoemd) == 1 else None


def _profielinstelling(settings: dict, register: list[dict]) -> str | None:
    """De naam uit het register die het profiel noemt (naam of afkorting); None zonder of onbekend."""
    opgave = " ".join((settings.get("instelling") or "").split()).lower()
    if not opgave:
        return None
    for inst in register:
        if opgave == inst["naam"].lower() or opgave in {a.lower() for a in inst.get("aliassen") or []}:
            return inst["naam"]
    return None


def _volgorde(settings: dict) -> list[str]:
    """De eigen sector van het profiel eerst, dan wo, hbo, mbo."""
    eigen = str(settings.get("domein") or "").strip().lower()
    return [eigen, *(s for s in _SECTOREN if s != eigen)] if eigen in _SECTOREN else list(_SECTOREN)


def _hoofdinstellingen(kandidaten: list[dict], volgorde: list[str]) -> list[dict]:
    """Per sector de instelling met de kortste naam (de hoofdinstelling: "Universiteit Utrecht" vóór
    "Theologische Universiteit Utrecht"), de eigen sector eerst; hooguit twee."""
    rang = {sector: i for i, sector in enumerate(volgorde)}
    gekozen: list[dict] = []
    for sector in volgorde:
        per_sector = sorted(
            (i for i in kandidaten if i.get("type") == sector), key=lambda i: (len(i["naam"]), i["naam"])
        )
        gekozen += per_sector[:1]
    rest = sorted(
        (i for i in kandidaten if i not in gekozen),
        key=lambda i: (rang.get(i.get("type"), 9), len(i["naam"]), i["naam"]),
    )
    return (gekozen + rest)[:_MAX_INSTELLINGEN]


def plaatsvraag(vraag: str, settings: dict | None = None) -> Kaart | None:
    """De scopekaart voor een telling bij een plaats die ook een instellingsnaam kan zijn; anders None."""
    settings = settings or {}
    if not _MAAT.search(vraag):
        return None
    register = _register()
    if not register or instelling.genoemde_namen(vraag):
        return None
    plaatsen = _plaatsen(register)
    genoemd = [p for p in plaatsen if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", vraag, re.IGNORECASE)]
    if len(genoemd) != 1:  # geen plaats, of twee: dan is het een vergelijking tussen gebieden
        return None
    plaats = genoemd[0]
    kandidaten = plaatsen[plaats]
    if _profielinstelling(settings, register) in {i["naam"] for i in kandidaten}:
        return None  # het profiel bepaalt de instelling; de prompt laat de scopevraag dan ook weg
    if sector := _sector_in_vraag(vraag):
        kandidaten = [i for i in kandidaten if i.get("type") == sector]
        if not kandidaten:
            return None  # "mbo-studenten in Groningen": geen mbo-instelling draagt de naam, dus een gebied
    opties = [{"label": i["naam"]} for i in _hoofdinstellingen(kandidaten, _volgorde(settings))]
    opties.append({"label": f"Studenten die in {plaats} wonen (gemeente of provincie)"})
    return Kaart(
        "scope", f"Over welke '{plaats}' gaat je vraag: een instelling of de woonplaats van studenten?", opties
    )


def _beschrijving(record: dict) -> str | None:
    """De samenvatting uit de catalogus als ze kort is; anders niets (de kaart is geen catalogus)."""
    tekst = " ".join(str(record.get("samenvatting") or "").split())
    return tekst if tekst and len(tekst) <= _MAX_BESCHRIJVING else None


def maatvraag(vraag: str) -> Kaart | None:
    """De maatkaart voor een kort thema zonder maat; None als de catalogus er geen twee records bij vindt."""
    if not is_vaag(vraag):
        return None
    records = catalog.kandidaten(vraag, _MAX_MATEN)
    if len(records) < 2:
        return None
    opties = []
    for record in records:
        # Een vo-contextbron noemt het deel, zoals in een bronregel en een suggestie (#557, #597).
        label = f"{record['titel']}, {scopeprofiel.HO_CONTEXT_DEEL}" if "context" in record else record["titel"]
        optie: dict = {"label": label}
        if beschrijving := _beschrijving(record):
            optie["beschrijving"] = beschrijving
        opties.append(optie)
    thema = " ".join(vraag.split()).strip(" ?!.,:")
    return Kaart("maat", f"Welke maat bedoel je bij '{thema}'?", opties)


_INSTROOM = re.compile(r"\b(instroom|instromers?|instromen|instroomcijfers?)\b", re.IGNORECASE)
_HO = re.compile(r"\b(ho|hbo|wo|hoger onderwijs|universiteit\w*|hogescho(?:ol|len)|hbo-\w+|wo-\w+)\b", re.IGNORECASE)
# Een fase die de vraag al noemt: bachelor, master, eerstejaars, Ad, of een opleidingsnaam als "B Informatica".
_FASE = re.compile(
    r"\b(bachelor\w*|master\w*|eerstejaars\w*|eerste jaar|propedeuse|associate degree|ad-\w+|vervolgopleiding\w*|"
    r"pre-?master\w*)\b",
    re.IGNORECASE,
)
_OPLEIDINGSNAAM = re.compile(r"(?<!\w)(?:B|M|Ad) [A-Z]")
# Het model krijgt alleen het label als keuze: de tweede noemt daarom de tabel, die de app dan oppikt (#334).
_FASE_OPTIES = [
    {
        "label": "Eerstejaars ho per instelling (DUO, zonder masters)",
        "beschrijving": "Wie voor het eerst in het hoger onderwijs staat, per instelling en opleiding. Doorstroom naar "
        "een master telt niet mee.",
        "aanbevolen": True,
    },
    {
        "label": "Ook masters: landelijk per hbo en wo (CBS 85422NED)",
        "beschrijving": "Eerstejaars per opleidingsfase, bachelor en master; niet per instelling of opleiding.",
    },
]


def _ho_instelling(vraag: str) -> bool:
    """Noemt de vraag een hbo- of wo-instelling uit het register (naam of afkorting)?"""
    genoemd = instelling.genoemde_namen(vraag)
    return bool(genoemd) and any(i["naam"] in genoemd and i.get("type") in ("hbo", "wo") for i in _register())


def fasevraag(vraag: str) -> Kaart | None:
    """De fasekaart voor instroom in het hoger onderwijs zonder fase; anders None."""
    if not _INSTROOM.search(vraag) or _FASE.search(vraag) or _OPLEIDINGSNAAM.search(vraag):
        return None
    if not (_HO.search(vraag) or _ho_instelling(vraag)):
        return None  # mbo, of geen sector: daar telt instroom zonder masterkwestie
    return Kaart("fase", "Welke instroom bedoel je?", [dict(optie) for optie in _FASE_OPTIES])


def scopevraag(vraag: str, settings: dict | None = None) -> Kaart | None:
    """De vaste eerste stap voor een vraag met een open slot; None als code niets te vragen heeft."""
    return plaatsvraag(vraag, settings) or maatvraag(vraag) or fasevraag(vraag)
