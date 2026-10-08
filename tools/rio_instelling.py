"""Eén instelling in RIO: naam → bevoegd gezag → instellingen → vestigingen, in code (#412).

CH-05: drie keer dezelfde vraag over ROC Mondriaan gaf drie antwoorden, omdat het
model zelf koos welke erkenningen het ophaalde en hoe het ze telde. De route ligt hier
vast: zoek het bevoegd gezag op naam (of via de instelling met die naam), volg de
hiërarchische instellingsrelaties naar de instellingen en van daar naar de vestigingen,
geldig op de peildatum. Lijsten zijn gesorteerd, dus dezelfde registertoestand geeft
dezelfde uitkomst, ongeacht de volgorde waarin RIO ze levert.

Op naam zoeken telt ook vestigingen die uit bedrijf zijn (hun erkenning loopt door,
hun relatie naar de instelling niet) en mist een instelling met een andere volledige
naam onder hetzelfde bestuur. De relaties volgen doet beide goed.
"""

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

import httpx
from riodata import fetch, get, related

from . import fouten, scopeprofiel
from .catalog import catalogus_titel

_ERKENNINGEN = "erkenningen"
_BEVOEGD_GEZAG = "BEVOEGD_GEZAG"
_INSTELLING = "ERKENDE_ONDERWIJSINSTELLING"
_VESTIGING = "ERKENDE_VESTIGING"
# Zoveel erkenningen tegelijk lezen: elk doelobject is een eigen RIO-aanroep (CH-29).
_PARALLEL = 8
_HIERARCHISCH = "HIERARCHISCH"
# mbo (WEB) en ho (WHW) maken een bestuur tot een bestuur binnen het profiel (#355);
# po/vo/so-instellingen eronder tellen niet mee.
_WETTEN_IN_SCOPE = frozenset({"WEB", "WHW"})
_WETTEN_BUITEN_SCOPE = ("WPO", "WVO", "WEC")
_MAX_INSTELLINGEN_OMHOOG = 10
_DEFINITIE = (
    "Instellingen en vestigingen: erkenningen met een geldige hiërarchische relatie naar het bestuur "
    "of de instelling op de peildatum, in bedrijf. Erkenningen = bestuur + instellingen + vestigingen."
)


def _naam(erkenning: dict) -> str:
    return " ".join(str(erkenning.get("volledigeNaam") or "").split())


def _code(href: str) -> str:
    return urlparse(href).path.rstrip("/").rsplit("/", 1)[-1]


def _geldig(item: dict, peildatum: str) -> bool:
    """Geldig en in bedrijf op de peildatum; een relatie kent alleen begin en einde."""
    begin, eind, uit = item.get("begindatum"), item.get("einddatum"), item.get("uitBedrijfdatum")
    return (not begin or begin <= peildatum) and (not eind or eind >= peildatum) and (not uit or uit > peildatum)


def _zoek(naam: str, soort: str, peildatum: str) -> list[dict]:
    gevonden = fetch(_ERKENNINGEN, volledigeNaam=naam, erkenningtype=soort, datumGeldigOp=peildatum)
    return [e for e in gevonden if e.get("type") == soort and _geldig(e, peildatum)]


def _relaties(code: str, peildatum: str) -> list[tuple[str, str]]:
    """De geldige hiërarchische relaties van een erkenning, als (van, naar)."""
    return [
        (_code(r["vanErkenning"]), _code(r["naarErkenning"]))
        # Dit endpoint pagineert niet en weigert page/pageSize (HTTP 400): related, niet fetch.
        for r in related(_ERKENNINGEN, code, "instellingsrelaties")
        if r.get("soort") == _HIERARCHISCH and _geldig(r, peildatum)
    ]


def _onder(code: str, peildatum: str) -> list[str]:
    return sorted({naar for van, naar in _relaties(code, peildatum) if van == code})


def _boven(code: str, peildatum: str) -> list[str]:
    return sorted({van for van, naar in _relaties(code, peildatum) if naar == code})


def _besturen(naam: str, peildatum: str) -> list[dict]:
    """Bevoegde gezagen met deze naam; anders de besturen van instellingen met deze naam."""
    if besturen := _zoek(naam, _BEVOEGD_GEZAG, peildatum):
        return besturen
    instellingen = _zoek(naam, _INSTELLING, peildatum)[:_MAX_INSTELLINGEN_OMHOOG]
    codes = sorted({b for i in instellingen for b in _boven(i["code"], peildatum)})
    return [e for e in _lees(codes)[0].values() if e.get("type") == _BEVOEGD_GEZAG and _geldig(e, peildatum)]


def _kies(naam: str, besturen: list[dict]) -> dict | list[dict]:
    """Het ene bestuur, of de kandidaten als de naam er meer dekt en geen ervan exact is."""
    uniek = {b["code"]: b for b in besturen}
    if len(uniek) == 1:
        return next(iter(uniek.values()))
    gezocht = " ".join(naam.split()).casefold()
    exact = [b for b in uniek.values() if _naam(b).casefold() == gezocht]
    if len(exact) == 1:
        return exact[0]
    return [{"code": c, "naam": _naam(uniek[c])} for c in sorted(uniek)]


def _lees(codes: list[str]) -> tuple[dict[str, dict], list[str]]:
    """De erkenningen achter `codes`, en de codes waarvan RIO geen object heeft (404)."""

    def een(code: str) -> tuple[str, dict | None]:
        try:
            return code, get(_ERKENNINGEN, code)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return code, None
            raise

    with ThreadPoolExecutor(max_workers=_PARALLEL) as pool:
        paren = list(pool.map(een, codes))
    return {c: e for c, e in paren if e is not None}, sorted(c for c, e in paren if e is None)


@dataclass
class _Telling:
    """Wat onder een erkenning hangt, getoetst op het doelobject zelf (CH-29)."""

    passend: dict[str, dict]  # code → erkenning van het gezochte type, in bedrijf op de peildatum
    onleesbaar: list[str]  # relatie zonder object in RIO
    anders: Counter  # andere typen erkenning: genoemd, niet geteld


def _onder_van(code: str, soort: str, peildatum: str) -> _Telling:
    """De erkenningen van `soort` onder `code`: relatie én doelobject geldig en in bedrijf op de peildatum.

    Een geldige relatie naar een vestiging die uit bedrijf is, telde eerder gewoon mee.
    """
    gelezen, onleesbaar = _lees(_onder(code, peildatum))
    passend = {c: e for c, e in gelezen.items() if e.get("type") == soort and _geldig(e, peildatum)}
    anders = Counter(str(e.get("type")) for e in gelezen.values() if e.get("type") != soort)
    return _Telling(passend, onleesbaar, anders)


def _instelling(code: str, erkenning: dict, peildatum: str) -> tuple[dict, _Telling]:
    """De instelling met haar vestigingen in bedrijf."""
    vestigingen = _onder_van(code, _VESTIGING, peildatum)
    codes = sorted(vestigingen.passend)
    return {
        "code": code,
        "naam": _naam(erkenning),
        "wet": erkenning.get("wet"),
        "erkenner": erkenning.get("erkenner"),
        "vestigingen": len(codes),
        "vestigingscodes": codes,
    }, vestigingen


def _overzicht(bestuur: dict, peildatum: str) -> dict:
    onder = _onder_van(bestuur["code"], _INSTELLING, peildatum)
    paren = [_instelling(c, e, peildatum) for c, e in sorted(onder.passend.items())]
    instellingen = [i for i, _ in paren]
    if not any(i["wet"] in _WETTEN_IN_SCOPE for i in instellingen):
        return {
            **scopeprofiel.buiten_scope("RIO"),
            "bevoegd_gezag": {"code": bestuur["code"], "naam": _naam(bestuur)},
            "melding": (
                "Dit bestuur heeft geen mbo-, hbo- of wo-instelling: de chat werkt alleen voor mbo, hbo en wo. "
                "Geef er geen aantallen voor en zeg niet dat de instelling niet bestaat."
            ),
        }
    binnen = [i for i in instellingen if not str(i["wet"] or "").startswith(_WETTEN_BUITEN_SCOPE)]
    weggelaten = sorted(i["code"] for i in instellingen if i not in binnen)
    vestigingen = sum(i["vestigingen"] for i in binnen)
    tellingen = [onder, *(t for i, t in paren if i in binnen)]
    anders = sum((t.anders for t in tellingen), Counter())
    onleesbaar = sorted({c for t in tellingen for c in t.onleesbaar})
    uit = {
        "bevoegd_gezag": {"code": bestuur["code"], "naam": _naam(bestuur)},
        # Een erkenning is het bestuur, een instelling of een vestiging.
        "aantallen": {
            "erkenningen": 1 + len(binnen) + vestigingen,
            "instellingen": len(binnen),
            "vestigingen": vestigingen,
        },
        "instellingen": binnen,
        "definitie": _DEFINITIE,
    }
    if weggelaten:
        uit["buiten_scope_weggelaten"] = weggelaten
    if anders:
        # Fontys: "23 erkenningen" verzweeg twee erkende onderwijsondersteuners (CH-29).
        uit["niet_meegeteld"] = dict(sorted(anders.items()))
    if onleesbaar:
        uit["niet_te_lezen"] = onleesbaar
    return uit


def get_rio_instelling(naam: str, peildatum: date | None = None) -> str:
    """Bestuur, instellingen en vestigingen van één onderwijsinstelling, geteld in code."""
    naam = " ".join(naam.split())
    peil = (peildatum or date.today()).isoformat()
    kop = {"bron": "RIO", "catalogus_titel": catalogus_titel(_ERKENNINGEN), "peildatum": peil, "gezocht": naam}
    try:
        gekozen = _kies(naam, _besturen(naam, peil))
        if not gekozen:
            uit = {
                "status": "niet_gevonden",
                "melding": f"RIO kent geen bevoegd gezag of instelling met '{naam}' in de naam op {peil}.",
            }
        elif isinstance(gekozen, list):
            uit = {
                "status": "meerdere",
                "kandidaten": gekozen,
                "melding": "De naam past bij meer besturen. Vraag welke bedoeld is, of zoek opnieuw met de volledige naam.",
            }
        else:
            uit = _overzicht(gekozen, peil)
    except Exception as e:
        return fouten.bronfout("RIO", e, f" Instelling '{naam}'.")
    return json.dumps({**kop, **uit}, ensure_ascii=False, separators=(",", ":"))
