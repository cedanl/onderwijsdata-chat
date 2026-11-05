"""Fusies van instellingen in vaste zinnen, uit de RIO-overgangen (#728). Code beslist, het model kiest niets.

Twee plekken waar een fusie stil een antwoord kleurde:
- Een oude naam of BRIN ("Friesland College", 25LG) gaf "niet gevonden". `opgegaan` zegt waarin de instelling opging,
  per welke dag en of de overgang volledig of gedeeltelijk was (`tools/rio_instelling.py`).
- DUO rekent een meerjarige reeks per instelling om naar de huidige code: Firda telt in 2021 en 2022 ook Friesland
  College mee, dat pas op 1-8-2023 in Firda opging. Een vergelijking met "Firda 2021" leek zo een gewone groei of
  krimp. `in_reeks` geeft per instelling met een fusie binnen de reeks een vaste regel; die komt bij het afleiden op de
  selectie (`dekking.van`) en zo in het Telling-blok onder het antwoord (`agent/telling.py`). Een voorganger uit po,
  vo of so (Morgen College, vmbo, in Landstede) telt niet mee in een mbo- of ho-reeks van DUO en staat er niet in
  (#937); was dat de enige voorganger binnen de reeks, dan komt er geen regel.

De voorgangers per code komen uit RIO en staan een dag in de cache (`core.actualiteit.Lading`). Een fout komt niet in
de cache; een storing geeft geen regel en een WARNING, en breekt het antwoord niet.
"""

import logging
from datetime import date

from onderwijsbronnen.rio import Stap, voorgangers

from core import actualiteit

from .scopeprofiel import wet_buiten_scope

logger = logging.getLogger(__name__)

# Boven zoveel instellingen is een selectie een ranglijst of overzicht, geen reeks per instelling: geen RIO-aanroepen.
MAX_INSTELLINGEN = 10
# DUO telt studenten en inschrijvingen per 1 oktober: de telling van startjaar J is die van 1-10-J.
_TELDAG = (10, 1)
_MAANDEN = (
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
)
_OVERGANG = {"volledig": "volledige overgang", "gedeeltelijk": "gedeeltelijke overgang"}


def nl_datum(iso: str) -> str:
    """2023-08-01 → 1 augustus 2023."""
    dag = date.fromisoformat(iso)
    return f"{dag.day} {_MAANDEN[dag.month - 1]} {dag.year}"


def _wie(naam: str | None, code: str) -> str:
    return f"{naam} ({code})" if naam else code


def opgegaan(code: str, naam: str | None, stappen: list[Stap]) -> str:
    """De zin bij een opgeheven instelling: waarin ze opging, per welke dag en hoe, elke stap van de keten."""
    namen = {code: naam, **{s.code: s.naam for s in stappen}}
    delen = [
        f"{_wie(namen.get(s.via), s.via)} is per {nl_datum(s.datum)} opgegaan in {_wie(s.naam, s.code)} "
        f"({_OVERGANG.get(s.overgang, s.overgang)})"
        for s in stappen
    ]
    return "; ".join(delen) + "."


@actualiteit.Lading
def _voorgangers(code: str, sinds: str) -> tuple[Stap, ...]:
    return tuple(voorgangers(code, sinds))


def _voorganger(stap: Stap) -> str:
    wie = _wie(stap.naam, stap.code)
    return wie if stap.overgang == "volledig" else f"{wie}, gedeeltelijk"


def _regel(code: str, naam: str, stappen: list[Stap]) -> str:
    per_dag: dict[str, list[Stap]] = {}
    for stap in stappen:
        per_dag.setdefault(stap.datum, []).append(stap)
    delen = [
        f"DUO telt de jaren vóór de fusie ({nl_datum(dag)}) bij de huidige instelling "
        f"(voorgangers: {', '.join(_voorganger(s) for s in groep)})"
        for dag, groep in sorted(per_dag.items())
    ]
    wie = _wie(naam, code) if naam != code else code
    return f"Fusie bij {wie}: " + "; ".join(delen) + "."


def in_reeks(namen: dict[str, str], schooljaren: tuple[int, ...] | None) -> tuple[str, ...]:
    """De vaste regel per instelling (code → naam) met een fusie binnen de reeks van `schooljaren`.

    Binnen de reeks: na de telling van het eerste jaar en uiterlijk op die van het laatste. Een fusie vóór de eerste
    telling (Yuverta, 1-8-2021, in een reeks vanaf 2021) verandert niets aan de reeks.
    """
    if not namen or len(namen) > MAX_INSTELLINGEN or not schooljaren or len(schooljaren) < 2:
        return ()
    begin, eind = (date(jaar, *_TELDAG).isoformat() for jaar in (min(schooljaren), max(schooljaren)))
    regels = []
    for code in sorted(namen):
        try:
            stappen = _voorgangers(code, begin)
        except Exception as e:  # een storing bij RIO breekt het antwoord niet: geen regel
            logger.warning("FUSIES_ONBEKEND code=%s fout=%s", code, type(e).__name__)
            continue
        if binnen := [s for s in stappen if begin < s.datum <= eind and not wet_buiten_scope(s.wet)]:
            regels.append(_regel(code, namen[code], binnen))
    return tuple(regels)
