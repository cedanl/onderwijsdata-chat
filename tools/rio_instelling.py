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
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import date
from urllib.parse import urlparse

import httpx
from riodata import fetch, get, opvolgers, related

from . import bronretry, fouten, fusies, scopeprofiel
from .catalog import catalogus_titel

# De RIO-dataset van het register; ook de bron van de regel onder het antwoord (agent/bronvermelding.py, #621).
ERKENNINGEN = "erkenningen"
# Het veld met de vaste fusiezin; agent/telling.py zet hem onder het antwoord (#728).
FUSIEMELDING = "fusiemelding"
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
# Een BRIN-code van een instelling: twee cijfers en twee letters (25LG); dan zoekt de code niet op naam (#728).
_BRIN = re.compile(r"\d{2}[A-Z]{2}")
_DEFINITIE = (
    "Instellingen en vestigingen: erkenningen met een geldige hiërarchische relatie naar het bestuur "
    "of de instelling op de peildatum, in bedrijf. Erkenningen = bestuur + instellingen + vestigingen."
)


def _naam(erkenning: dict) -> str:
    return " ".join(str(erkenning.get("volledigeNaam") or "").split())


def _code(href: str) -> str:
    return urlparse(href).path.rstrip("/").rsplit("/", 1)[-1]


def _relatiecode(relatie: dict, kant: str) -> str:
    """De erkenningscode aan één kant van een relatie: RIO v3 geeft `vanErkenningId`/`naarErkenningId`
    als veld; de link `_links.van`/`_links.naar` (met `?datumGeldigOp=`) is de terugval."""
    if code := relatie.get(f"{kant}ErkenningId"):
        return str(code)
    return _code(relatie["_links"][kant]["href"])


def _geldig(item: dict, peildatum: str) -> bool:
    """Geldig en in bedrijf op de peildatum; een relatie kent alleen begin en einde."""
    begin, eind, uit = item.get("begindatum"), item.get("einddatum"), item.get("uitBedrijfdatum")
    return (not begin or begin <= peildatum) and (not eind or eind >= peildatum) and (not uit or uit > peildatum)


def _opgeheven(item: dict, peildatum: str) -> bool:
    """Uit bedrijf of beëindigd op de peildatum: een instelling die kan zijn opgegaan in een andere (#728)."""
    eind, uit = item.get("einddatum"), item.get("uitBedrijfdatum")
    return bool((uit and uit <= peildatum) or (eind and eind < peildatum))


def _zoek_alle(naam: str, soort: str, peildatum: str) -> list[dict]:
    """Erkenningen van `soort` met `naam` in de naam, ook die uit bedrijf zijn."""
    # RIO v3: het typefilter heet `type` (v2: erkenningtype; die versie is op 19-10-2026 verwijderd, #627).
    gevonden = bronretry.haal_op_met_retry(
        "RIO", lambda: fetch(ERKENNINGEN, volledigeNaam=naam, type=soort, datumGeldigOp=peildatum)
    )
    return [e for e in gevonden if e.get("type") == soort]


def _zoek(naam: str, soort: str, peildatum: str) -> list[dict]:
    return [e for e in _zoek_alle(naam, soort, peildatum) if _geldig(e, peildatum)]


def _relaties(code: str, peildatum: str) -> list[tuple[str, str]]:
    """De geldige hiërarchische relaties van een erkenning, als (van, naar).

    Met `datumGeldigOp`: zonder datum geeft RIO de relaties van vandaag, en vond "Friesland College" op 2022-10-01 een
    bestuur zonder mbo-instelling, omdat de relatie naar 25LG op 2023-01-01 eindigde (#728).
    """
    return [
        (_relatiecode(r, "van"), _relatiecode(r, "naar"))
        # Dit endpoint pagineert niet en weigert page/pageSize (HTTP 400): related, niet fetch.
        for r in bronretry.haal_op_met_retry(
            "RIO", lambda: related(ERKENNINGEN, code, "instellingsrelaties", datumGeldigOp=peildatum)
        )
        if r.get("soort") == _HIERARCHISCH and _geldig(r, peildatum)
    ]


def _onder(code: str, peildatum: str) -> list[str]:
    return sorted({naar for van, naar in _relaties(code, peildatum) if van == code})


def _boven(code: str, peildatum: str) -> list[str]:
    return sorted({van for van, naar in _relaties(code, peildatum) if naar == code})


def _besturen_boven(instellingen: list[dict], peildatum: str) -> list[dict]:
    codes = sorted({b for i in instellingen for b in _boven(i["code"], peildatum)})
    return [e for e in _lees(codes, peildatum)[0].values() if e.get("type") == _BEVOEGD_GEZAG and _geldig(e, peildatum)]


def _in_scope_opgeheven(instellingen: list[dict], peildatum: str) -> list[dict]:
    """De mbo-, hbo- en wo-instellingen (WEB/WHW) die op de peildatum opgeheven zijn; po/vo blijft buiten (#355)."""
    return [i for i in instellingen if i.get("wet") in _WETTEN_IN_SCOPE and _opgeheven(i, peildatum)]


def _besturen(naam: str, peildatum: str) -> tuple[list[dict], list[dict]]:
    """Bevoegde gezagen met deze naam; anders de besturen van instellingen met deze naam.

    Daarnaast de opgeheven instellingen met deze naam, voor de fusiemelding (#728).
    """
    if besturen := _zoek(naam, _BEVOEGD_GEZAG, peildatum):
        return besturen, []
    gevonden = _zoek_alle(naam, _INSTELLING, peildatum)
    instellingen = [i for i in gevonden if _geldig(i, peildatum)][:_MAX_INSTELLINGEN_OMHOOG]
    opgeheven = sorted(_in_scope_opgeheven(gevonden, peildatum), key=lambda i: i["code"])[:_MAX_INSTELLINGEN_OMHOOG]
    return _besturen_boven(instellingen, peildatum), opgeheven


def _per_code(code: str, peildatum: str) -> tuple[list[dict], list[dict]]:
    """De besturen van de instelling met deze BRIN-code; is ze opgeheven, dan de instelling zelf (#728)."""
    instelling = _lees([code], peildatum)[0].get(code)
    if instelling is None or instelling.get("type") != _INSTELLING:
        return [], []
    if _geldig(instelling, peildatum):
        return _besturen_boven([instelling], peildatum), []
    return [], _in_scope_opgeheven([instelling], peildatum)


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


def _lees(codes: list[str], peildatum: str) -> tuple[dict[str, dict], list[str]]:
    """De erkenningen achter `codes` op de peildatum, en de codes waarvan RIO geen object heeft (404)."""

    def een(code: str) -> tuple[str, dict | None]:
        try:
            return code, bronretry.haal_op_met_retry("RIO", lambda: get(ERKENNINGEN, code, datumGeldigOp=peildatum))
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
    gelezen, onleesbaar = _lees(_onder(code, peildatum), peildatum)
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


def _opgegaan(opgeheven: list[dict], peildatum: str) -> list[dict]:
    """Per opgeheven instelling met een overgang: waarin ze opging, als stappen en als vaste zin (#728)."""
    uit = []
    for instelling in opgeheven:
        code, naam = instelling["code"], _naam(instelling)
        stappen = bronretry.haal_op_met_retry("RIO", lambda c=code: opvolgers(c, peildatum))
        if stappen:
            uit.append(
                {
                    "code": code,
                    "naam": naam,
                    "opgegaan_in": [asdict(s) for s in stappen],
                    "zin": fusies.opgegaan(code, naam, stappen),
                }
            )
    return uit


def _zoekopdracht(naam: str, peildatum: str) -> tuple[list[dict], list[dict]]:
    """Besturen en opgeheven instellingen bij een BRIN-code of een naam."""
    if _BRIN.fullmatch(naam.upper()):
        return _per_code(naam.upper(), peildatum)
    return _besturen(naam, peildatum)


def _niet_gevonden(naam: str, peildatum: str, opgegaan: list[dict]) -> dict:
    if opgegaan:
        # Geen keuze voor het model: de zin staat vast en komt ook onder het antwoord (agent/telling.py).
        return {
            "status": "opgegaan",
            "melding": " ".join(o["zin"] for o in opgegaan)
            + " Noem dat zo; zoek de huidige instelling op met haar eigen naam als de vraag over haar gaat.",
        }
    if _BRIN.fullmatch(naam.upper()):
        melding = f"RIO kent geen mbo-, hbo- of wo-instelling met code '{naam.upper()}' op {peildatum}."
    else:
        melding = f"RIO kent geen bevoegd gezag of instelling met '{naam}' in de naam op {peildatum}."
    return {"status": "niet_gevonden", "melding": melding}


def get_rio_instelling(naam: str, peildatum: date | None = None) -> str:
    """Bestuur, instellingen en vestigingen van één onderwijsinstelling, geteld in code.

    Een naam of BRIN van een opgeheven mbo-, hbo- of wo-instelling geeft daarnaast waarin ze opging (#728).
    """
    naam = " ".join(naam.split())
    peil = (peildatum or date.today()).isoformat()
    kop = {"bron": "RIO", "catalogus_titel": catalogus_titel(ERKENNINGEN), "peildatum": peil, "gezocht": naam}
    try:
        besturen, opgeheven = _zoekopdracht(naam, peil)
        gekozen = _kies(naam, besturen)
        opgegaan = _opgegaan(opgeheven, peil)
        if not gekozen:
            uit = _niet_gevonden(naam, peil, opgegaan)
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
    if opgegaan:
        uit = {**uit, "opgegaan": opgegaan, FUSIEMELDING: " ".join(o["zin"] for o in opgegaan)}
    return json.dumps({**kop, **uit}, ensure_ascii=False, separators=(",", ":"))
