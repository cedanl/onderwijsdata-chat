"""Andere definities bij een vaste maat (#1256): hetzelfde getal onder de gangbare andere keuze, uit code.

Veel getallen hangen af van een keuze in de definitie: personen of inschrijvingen, met of zonder extranei, alle
vormen of alleen voltijd. Beide uitkomsten kloppen, maar de lezer zag er één ("Hoeveel mbo-studenten waren er in
2024/25?" gaf DUO 474.963 en CBS 475.460, `docs/domeinregels.md`). Hier staat per vaste maat (`tools/maten.py`)
hooguit drie andere definities, elk met een uitleg van één regel en een recept: de get_maat-argumenten die anders
zijn. Code rekent ze uit op dezelfde afbakening en zet ze onder het antwoord (`agent/controlestappen.py`); het model
kiest er niets van en ziet ze niet.

Een alternatief dat gelijk is aan het hoofdrecept, valt weg: bij een gesprek dat extranei al uitsluit, is het
alternatief de telling mét extranei. Alleen bij vorm `alle` tellen de vorm-alternatieven; een maatwissel
(personen ↔ inschrijvingen) houdt de vorm van het hoofdrecept.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from . import maten, periode

# Wijkt geen alternatief meer af dan dit (in procenten van het hoofdgetal), dan zegt de regel dat andere definities
# hetzelfde beeld geven, zonder getallen (#1256).
DREMPEL_PCT = 1.0


@dataclass(frozen=True)
class Alternatief:
    """Een andere definitie bij een vaste maat: haar naam, de uitleg in één regel en het recept."""

    naam: str  # zoals de regel haar noemt: "zonder extranei"
    uitleg: str  # één regel: wat er anders geteld wordt
    recept: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )  # de get_maat-argumenten die anders zijn
    alleen_bij_vorm_alle: bool = True  # een vorm-alternatief past niet op een recept dat zelf al een vorm koos
    tenzij: str | None = None  # valt weg als de teldefinitie van het hoofdresultaat dit noemt
    alleen_als: str | None = None  # telt alleen als de teldefinitie van het hoofdresultaat dit noemt


_VOLTIJD = Alternatief("alleen voltijd", "zonder deeltijd en duaal", {"vorm": "voltijd"})
_ZONDER_EXTRANEI = Alternatief(
    "zonder extranei",
    "zonder de examendeelnemers (extranei): wie alleen examen doet en geen onderwijs volgt",
    {"vorm": maten.ZONDER_EXTRANEI},
    tenzij="excl. extranei",
)
_MET_EXTRANEI = Alternatief(
    "met extranei",
    "met de examendeelnemers (extranei), de standaard van de tabel",
    {"vorm": maten.MET_EXTRANEI},
    alleen_als="excl. extranei",
)

ALTERNATIEVEN: dict[str, tuple[Alternatief, ...]] = {
    maten.PERSONEN_HO: (
        Alternatief(
            "inschrijvingen",
            "hoofd- én neveninschrijvingen: wie aan twee opleidingen staat ingeschreven, telt twee keer",
            {"maat": maten.INSCHRIJVINGEN_HO},
            alleen_bij_vorm_alle=False,
        ),
        _VOLTIJD,
    ),
    maten.INSCHRIJVINGEN_HO: (
        Alternatief(
            "personen",
            "elke student één keer, met alleen de hoofdinschrijving",
            {"maat": maten.PERSONEN_HO},
            alleen_bij_vorm_alle=False,
        ),
        _VOLTIJD,
    ),
    maten.EERSTEJAARS_HO: (_VOLTIJD,),
    maten.DEELNEMERS_HO_LANDELIJK: (_VOLTIJD,),
    maten.MBO_STUDENTEN: (
        Alternatief(
            "zonder extranei",
            "zonder de examendeelnemers (EX): wie alleen examen doet en geen onderwijs volgt",
            {"vorm": maten.ZONDER_EXTRANEI},
        ),
    ),
    maten.MBO_STUDENTEN_LANDELIJK: (_ZONDER_EXTRANEI, _MET_EXTRANEI),
    maten.DOORSTROOM_VMBO_MBO: (_ZONDER_EXTRANEI, _MET_EXTRANEI),
}


def _json(tekst: str) -> dict:
    try:
        parsed = json.loads(tekst)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass(frozen=True)
class Hoofdgetal:
    """Het getal onder een get_maat-resultaat waar de regel over gaat: het laatste schooljaar met een waarde."""

    waarde: float
    startjaar: int
    data_key: str


def hoofdgetal(resultaat: dict) -> Hoofdgetal | None:
    """Het laatste schooljaar met een waarde in de rijen van een get_maat-resultaat; None zonder rijen of key."""
    key, rijen = resultaat.get("data_key"), resultaat.get("rijen")
    kolom, waardekolom = resultaat.get("periodekolom"), resultaat.get("waardekolom")
    recept = resultaat.get("recept")
    recept = recept if isinstance(recept, dict) else {}
    if not isinstance(key, str) or not isinstance(rijen, list) or not kolom or not waardekolom:
        return None
    gevonden: list[tuple[int, float]] = []
    for rij in rijen:
        if not isinstance(rij, dict):
            continue
        waarde, jaar = rij.get(waardekolom), periode.startjaar(str(recept.get("bron") or ""), rij.get(kolom))
        if jaar is not None and isinstance(waarde, int | float) and not isinstance(waarde, bool):
            gevonden.append((jaar, float(waarde)))
    if not gevonden:
        return None
    jaar, waarde = max(gevonden)
    return Hoofdgetal(waarde, jaar, key)


def _args(resultaat: dict, startjaar: int) -> dict | None:
    """De get_maat-argumenten van een resultaat, voor één schooljaar; None bij geslacht of een opleiding."""
    if resultaat.get("opleiding") or resultaat.get("afleiding") or not isinstance(resultaat.get("maat"), str):
        return None
    args: dict = {"maat": resultaat["maat"], "vorm": resultaat.get("vorm") or maten.ALLE}
    instelling = resultaat.get("instelling")
    if isinstance(instelling, dict) and isinstance(instelling.get("naam"), str):
        args["instelling"] = instelling["naam"]
    elif isinstance(resultaat.get("sector"), str) and len(maten.MATEN[args["maat"]].sectoren) > 1:
        args["sector"] = resultaat["sector"]
    args["schooljaren"] = [periode.label(startjaar)]
    return args


def _geldt(alternatief: Alternatief, resultaat: dict, args: dict) -> bool:
    teldefinitie = str(resultaat.get("teldefinitie") or "")
    if alternatief.alleen_bij_vorm_alle and args["vorm"] != maten.ALLE:
        return False
    if alternatief.tenzij and alternatief.tenzij in teldefinitie:
        return False
    return not (alternatief.alleen_als and alternatief.alleen_als not in teldefinitie)


def aanroepen(resultaat_tekst: str) -> list[tuple[Alternatief, dict]]:
    """Per alternatief dat bij dit get_maat-resultaat geldt: de get_maat-argumenten op dezelfde afbakening, voor het
    schooljaar van het hoofdgetal. Leeg bij een melding, een maat zonder alternatieven of geslacht per opleiding."""
    resultaat = _json(resultaat_tekst)
    hoofd = hoofdgetal(resultaat)
    if hoofd is None or resultaat.get("maat") not in ALTERNATIEVEN:
        return []
    args = _args(resultaat, hoofd.startjaar)
    if args is None:
        return []
    uit = []
    for alternatief in ALTERNATIEVEN[resultaat["maat"]]:
        if _geldt(alternatief, resultaat, args):
            nieuw = {**args, **alternatief.recept}
            if nieuw != args:
                uit.append((alternatief, nieuw))
    return uit


def waarde_in(resultaat_tekst: str, startjaar: int) -> float | None:
    """De waarde van een get_maat-resultaat in dit schooljaar; None als het jaar of de waarde ontbreekt."""
    resultaat = _json(resultaat_tekst)
    hoofd = hoofdgetal(resultaat)
    return hoofd.waarde if hoofd is not None and hoofd.startjaar == startjaar else None


def verschil_pct(waarde: float, hoofd: float) -> float | None:
    """Het verschil van `waarde` met `hoofd` in procenten van `hoofd`, op één decimaal; None bij een hoofd van 0."""
    return round((waarde - hoofd) / hoofd * 100, 1) if hoofd else None
