"""Opvolgers en voorgangers van een erkenning langs de overgangen in RIO v3 (#728).

RIO legt elke fusie en overdracht vast als instellingsrelatie met soort ``OVERGANG_VOLLEDIG`` of
``OVERGANG_GEDEELTELIJK``: van de oude erkenning naar de nieuwe, met de dag van de overgang als ``begindatum``.
Friesland College (25LG) staat zo per 2023-08-01 volledig in Firda (08PG). Besturen fuseren langs dezelfde relaties:
met een bestuursnummer (40864 → 40877, Regio College in Talland) werken beide functies net zo.

Elke aanroep geeft ``datumGeldigOp`` mee: zonder datum geeft RIO de stand van vandaag, en een vraag over een dag in het
verleden kreeg dan de relaties van vandaag. Een keten (A → B → C) wordt tot het eind gevolgd; een erkenning die al
gezien is, wordt niet nog eens gevolgd, zodat een cyclus stopt. Een bronfout gaat naar de aanroeper.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .client import get, related

_ERKENNINGEN = "erkenningen"
_OVERGANGEN = {"OVERGANG_VOLLEDIG": "volledig", "OVERGANG_GEDEELTELIJK": "gedeeltelijk"}
# Een ketting van overgangen is in RIO hooguit enkele stappen lang; dit is de rem op een kapotte registratie.
_MAX_STAPPEN = 50


@dataclass(frozen=True)
class Stap:
    """Eén overgang vanuit het gezichtspunt van de vraag.

    Bij ``opvolgers`` is ``code`` de erkenning waarin ``via`` opging; bij ``voorgangers`` is ``code`` de erkenning
    die in ``via`` opging. ``overgang`` is ``"volledig"`` of ``"gedeeltelijk"``, ``datum`` de dag van de overgang
    (jjjj-mm-dd) en ``naam`` de volledige naam van ``code`` (None als RIO de erkenning op die dag niet kent).
    """

    code: str
    naam: str | None
    overgang: str
    datum: str
    via: str


def _iso(datum: dt.date | str | None) -> str:
    if datum is None:
        return dt.date.today().isoformat()
    return datum.isoformat() if isinstance(datum, dt.date) else str(datum)


def _code(relatie: dict, kant: str) -> str:
    """De erkenningscode aan één kant: het veld ``vanErkenningId``/``naarErkenningId``, anders de link."""
    if code := relatie.get(f"{kant}ErkenningId"):
        return str(code)
    return urlparse(relatie["_links"][kant]["href"]).path.rstrip("/").rsplit("/", 1)[-1]


def _overgangen(code: str, peil: str) -> list[tuple[str, str, str, str]]:
    """De overgangen van en naar ``code`` die op ``peil`` bestaan, als (van, naar, soort, datum)."""
    uit = []
    for r in related(_ERKENNINGEN, code, "instellingsrelaties", datumGeldigOp=peil):
        soort, begin, eind = _OVERGANGEN.get(r.get("soort", "")), r.get("begindatum"), r.get("einddatum")
        if soort and begin and begin <= peil and (not eind or eind >= peil):
            uit.append((_code(r, "van"), _code(r, "naar"), soort, begin))
    return uit


def _naam(code: str, op: str) -> str | None:
    try:
        erkenning = get(_ERKENNINGEN, code, datumGeldigOp=op)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise
    return " ".join(str(erkenning.get("volledigeNaam") or "").split()) or None


def _dag_ervoor(datum: str) -> str:
    return (dt.date.fromisoformat(datum) - dt.timedelta(days=1)).isoformat()


def _sorteer(stappen: list[Stap]) -> list[Stap]:
    return sorted(stappen, key=lambda s: (s.datum, s.code, s.via))


def opvolgers(brin: str, peildatum: dt.date | str | None = None) -> list[Stap]:
    """De erkenningen waarin ``brin`` opging tot en met ``peildatum`` (standaard vandaag), ook verder in de keten.

    Leeg als ``brin`` op die dag geen overgang heeft. Gesorteerd op datum en code.
    """
    peil = _iso(peildatum)
    gezien, rij, stappen = {brin}, [brin], []
    while rij and len(stappen) < _MAX_STAPPEN:
        code = rij.pop(0)
        for van, naar, soort, datum in sorted(_overgangen(code, peil)):
            if van != code or naar in gezien:
                continue
            gezien.add(naar)
            rij.append(naar)
            stappen.append(Stap(naar, _naam(naar, peil), soort, datum, via=code))
    return _sorteer(stappen)


def voorgangers(brin: str, sinds: dt.date | str | None = None, peildatum: dt.date | str | None = None) -> list[Stap]:
    """De erkenningen die vanaf ``sinds`` (standaard: altijd) in ``brin`` opgingen, ook verder terug in de keten.

    ``peildatum`` (standaard vandaag) is de ``datumGeldigOp`` van de relaties; de naam van een voorganger is die van
    de dag vóór haar overgang, toen ze nog bestond. Gesorteerd op datum en code.
    """
    peil, vanaf = _iso(peildatum), _iso(sinds) if sinds is not None else ""
    gezien, rij, stappen = {brin}, [brin], []
    while rij and len(stappen) < _MAX_STAPPEN:
        code = rij.pop(0)
        for van, naar, soort, datum in sorted(_overgangen(code, peil)):
            if naar != code or van in gezien or datum < vanaf:
                continue
            gezien.add(van)
            rij.append(van)
            stappen.append(Stap(van, _naam(van, _dag_ervoor(datum)), soort, datum, via=code))
    return _sorteer(stappen)
