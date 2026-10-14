"""Server-side preflight op het CBS-contract, vóór de datacall (#370, AC3 en AC5).

De selectiepoort (`cbs_selectie`, #343) kijkt of een selectie volledig is. Of de tabel haar
ook kan leveren, weet het contract van de CBS-package: bestaat de code in de dimensie, komt
de periode in de tabel voor, en past de gekozen code bij de sector waarvoor het model de
tabel bevraagt. `validate_selection` toetst dat tegen de dimensietabellen van de bron (live,
in de package gecachet) en zegt per controle supported, unsupported of unknown, met
herstelopties.

Alleen `unsupported` houdt de aanroep tegen: de datacall zou geen of de verkeerde rijen geven,
en de weigering noemt wat wél kan. `unknown` laat door: bronuitval of een dimensie die het
contract niet kent is geen onvolledige selectie, en get_cbs_data meldt een lege uitkomst zelf.
"""

import logging
import re

from onderwijsdata import validate_selection
from onderwijsdata.contract import DatasetNietGevonden

from core.logging_util import foutkenmerk

from . import cbs_selectie

logger = logging.getLogger(__name__)

UNSUPPORTED = "unsupported"
# Zoveel herstelopties noemt de weigering per controle; de rest vindt het model via get_cbs_dimension.
MAX_HERSTEL = 6
_PERIODECODE = re.compile(r"^(\d{4})(SJ|JJ)00$")
_PERIODESOORT = {"SJ": "schooljaar", "JJ": "jaar"}


def _periode_eis(code: str, tijd: str) -> dict:
    """Eén periodecode als eis: schooljaar of jaar via `periode`, een andere code via de tijddimensie."""
    if m := _PERIODECODE.match(code):
        return {"periode": {"type": _PERIODESOORT[m.group(2)], "jaar": int(m.group(1))}}
    return {"dimensies": {tijd: code}}


def eisen(selectie: dict, tijd: str) -> list[dict]:
    """De eisen aan het contract, één per code: `validate_selection` toetst per dimensie één code.

    De sector gaat met elke eis mee, zodat het contract een code tegen de sector kan houden
    (`samenhang`); een selectie zonder codes vraagt alleen naar de sector.
    """
    sector = selectie.get("sector")
    basis = {"sector": sector} if sector in cbs_selectie.SECTOREN else {}
    uit: list[dict] = []
    dimensies = selectie.get("dimensies")
    for dimensie, waarde in dimensies.items() if isinstance(dimensies, dict) else ():
        codes = waarde if isinstance(waarde, list) else [waarde]
        uit += [
            {**basis, "dimensies": {dimensie: str(code).strip()}}
            for code in codes
            if code != cbs_selectie.ALLES and str(code).strip()
        ]
    periode = selectie.get("periode")
    if periode is not None and periode != cbs_selectie.ALLES:
        codes = cbs_selectie.periodecodes(periode)
        if isinstance(codes, list):
            uit += [{**basis, **_periode_eis(code, tijd)} for code in codes]
    if basis and not uit:
        uit.append(basis)
    return uit


def _contract(dataset_id: str, eis: dict) -> dict | None:
    """Eén oordeel van het contract; None als het niet kan oordelen (onbekende tabel, bronuitval)."""
    try:
        return validate_selection(dataset_id, eis, live=True)
    except DatasetNietGevonden:
        return None
    except Exception as e:
        # Bronuitval mag de laadroute niet breken; de fouttekst kan de codes van het model citeren (#502).
        logger.warning("CBS-preflight overgeslagen voor %s: %s", dataset_id, foutkenmerk(e))
        logger.debug("CBS-preflight overgeslagen voor %s", dataset_id, exc_info=e)
        return None


def _regel(check: dict) -> str:
    regel = str(check.get("reden") or f"{check.get('veld')} niet leverbaar")
    herstel = [str(h) for h in check.get("herstel") or ()]
    if herstel:
        regel += f" (wel in de tabel: {', '.join(herstel[:MAX_HERSTEL])}{', …' if len(herstel) > MAX_HERSTEL else ''})"
    return regel


def preflight(dataset_id: str, selectie: dict, col_defs: dict | None) -> str | None:
    """De weigering als het contract zegt dat de tabel deze selectie niet kan leveren; anders None."""
    tijd = cbs_selectie.dimensienamen(col_defs)[1] if col_defs else None
    redenen: list[str] = []
    for eis in eisen(selectie, tijd or cbs_selectie.TIJDDIMENSIE_FALLBACK):
        uitkomst = _contract(dataset_id, eis)
        if uitkomst is None:
            break  # geen oordeel over deze tabel: de volgende eisen krijgen er ook geen
        if uitkomst.get("status") != UNSUPPORTED:
            continue
        for check in uitkomst.get("checks") or ():
            if check.get("status") == UNSUPPORTED and (regel := _regel(check)) not in redenen:
                redenen.append(regel)
    if not redenen:
        return None
    return (
        f"Selectie voor {dataset_id} geweigerd door het CBS-contract: {'; '.join(redenen)}. "
        "Kies codes uit get_cbs_dimension en een periode die in de tabel voorkomt."
    )
