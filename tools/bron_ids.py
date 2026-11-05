"""Welke bron en welk catalogus-ID achter een ID of datasleutel zit: de enige plek in de chat (#912).

Het ID-contract `bron:id` staat in het pakket (`onderwijsbronnen.parse_bron_id`, `_kern/bron_id.py`): één
normalisatie voor alle zeven bronnen, en een kale ID die bij twee bronnen past is een fout met opties. Hier hangt de chat
eraan, achter de vlag `BRON_ID_CONTRACT` (core/config.py):

- `uit`: de herleiding van vóór #912 (`_oud_*` hieronder: voorvoegsel eraf, hoofdletterongevoelig zoeken in de
  inventaris van tools/catalog.py).
- `schaduw`: de oude herleiding bepaalt de uitkomst; de nieuwe draait ernaast en elk verschil staat in het log als
  `BRON_ID_VERSCHIL` met een telling per soort (geen gebruikerstekst: een ID dat de catalogus niet kent, staat er als
  lengte en hash). Zo is op test te tellen of het contract iets anders doet (#913).
- `aan`: het contract bepaalt de uitkomst.

Drie vragen, drie functies; ze vervangen `catalog.bron_id`, `catalog.cbs_bron_id` en `duo.bron_van`:

- `bron_id`: het catalogus-ID zonder voorvoegsel (`duo:p01hoinges`, `P01HOINGES` → `p01hoinges`);
- `cbs_tabel_id`: hetzelfde aan de toolgrens van CBS (#370), waar een ID van een andere bron blijft zoals het is;
- `bron_van`: de bron van een datasleutel uit de store (`duo:p01hoinges:4` → `duo`, `analysis:…` → `analysis`).

Een onbekend ID blijft in alle drie de modi zoals het was (zonder voorvoegsel), zodat de tool daarna zelf "onbekend"
meldt. De oude herleiding verdwijnt met de vlag, na de acceptatie op test (#913/#914); oude ID-vormen in opgeslagen
recepten blijven werken, want het contract accepteert ze allemaal (tests/test_bron_id_vormen.py).
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable

from onderwijsbronnen import BRONNEN, OnbekendBronId, bron_van_sleutel, parse_bron_id

from core import config
from core.logging_util import tekst_kenmerk

from .canoniek import zonder_bronprefix, zonder_cbs_prefix

logger = logging.getLogger(__name__)

MODI = ("uit", "schaduw", "aan")
_verschillen: Counter[str] = Counter()
_ongeldige_modus_gemeld = False


def modus() -> str:
    """De stand van de vlag; een onbekende waarde telt als `uit`, met één logregel."""
    global _ongeldige_modus_gemeld
    waarde = config.BRON_ID_CONTRACT
    if waarde in MODI:
        return waarde
    if not _ongeldige_modus_gemeld:
        _ongeldige_modus_gemeld = True
        logger.error("BRON_ID_CONTRACT onbekend (%s); kies uit %s. De chat gebruikt uit.", waarde[:20], "|".join(MODI))
    return "uit"


def verschillen() -> dict[str, int]:
    """Het aantal verschillen per soort sinds de start van het proces (alleen in de modus schaduw)."""
    return dict(_verschillen)


# --- de drie vragen ---------------------------------------------------------------------------------------------


def bron_id(dataset_id: str) -> str:
    """Het catalogus-ID achter een genamespaced of anders gespeld ID (#356, #912).

    `duo:p01hoinges`, `rio/erkenningen`, `cbs_85423ned` en `P01HOINGES` wijzen naar het ID zoals de catalogus het
    schrijft, zonder voorvoegsel. Een onbekend ID blijft zoals het is, zonder voorvoegsel.
    """
    return _volgens_modus("dataset", dataset_id, _oud_bron_id, _nieuw_bron_id)


def cbs_tabel_id(dataset_id: str) -> str:
    """Het ID van een CBS-tabel in de spelling van de catalogus (#370, #912): `cbs:85423NED`, `85423ned` → `85423NED`,
    en `71733NED` → `71733ned`, nooit `upper()`. Een ander of onbekend ID blijft zoals het is, zonder `cbs:`."""
    return _volgens_modus("cbs", dataset_id, _oud_cbs_tabel_id, _nieuw_cbs_tabel_id)


def bron_van(key: str) -> str:
    """De bron van een store-key (duo, cbs, rio, …): uit de meta, anders het voorvoegsel van de key."""
    from . import store  # hier: store importeert tools.catalog, en die deze module

    if known := store.meta(key):
        return known.bron
    return _volgens_modus("sleutel", key, _oud_bron_van, bron_van_sleutel)


# --- oud en nieuw -----------------------------------------------------------------------------------------------


def _oud_bron_id(dataset_id: str) -> str:
    from . import catalog, scopeprofiel

    kaal = zonder_bronprefix(dataset_id)
    gezocht = kaal.lower()
    for entry in (*catalog._cbs_alles(), *catalog._rio_duo_alles()):
        if isinstance(eid := scopeprofiel.dataset_id(entry), str) and eid.lower() == gezocht:
            return eid
    return kaal


def _oud_cbs_tabel_id(dataset_id: str) -> str:
    from . import catalog

    kaal = zonder_cbs_prefix(dataset_id)
    gezocht = kaal.lower()
    for entry in catalog._cbs_alles():
        if isinstance(cbs_id := entry.get("_cbs_id"), str) and cbs_id.lower() == gezocht:
            return cbs_id
    return kaal


def _oud_bron_van(key: str) -> str:
    return key.split(":", 1)[0]


def _nieuw_bron_id(dataset_id: str) -> str:
    try:
        return parse_bron_id(dataset_id).id
    except OnbekendBronId:
        return zonder_bronprefix(dataset_id)


def _nieuw_cbs_tabel_id(dataset_id: str) -> str:
    try:
        gevonden = parse_bron_id(dataset_id)
    except OnbekendBronId:
        return zonder_cbs_prefix(dataset_id)
    return gevonden.id if gevonden.bron == "cbs" else zonder_cbs_prefix(dataset_id)


# --- de modus ---------------------------------------------------------------------------------------------------


def _volgens_modus(soort: str, invoer: str, oud: Callable[[str], str], nieuw: Callable[[str], str]) -> str:
    stand = modus()
    if stand == "aan":
        return nieuw(invoer)
    uitkomst = oud(invoer)
    if stand == "schaduw":
        try:
            ander = nieuw(invoer)
        except Exception as e:  # het contract mag de chat in schaduw nooit breken; het verschil telt wel
            ander = f"<{type(e).__name__}>"
        if ander != uitkomst:
            _meld(soort, invoer, uitkomst, ander)
    return uitkomst


def _meld(soort: str, invoer: str, oud: str, nieuw: str) -> None:
    _verschillen[soort] += 1
    if soort == "sleutel":
        # Een datasleutel kan filterwaarden bevatten; alleen het voorvoegsel zegt iets over de bron.
        invoer = str(invoer).split(":", 1)[0]
    logger.warning(
        "BRON_ID_VERSCHIL soort=%s aantal=%d invoer=%s oud=%s nieuw=%s",
        soort,
        _verschillen[soort],
        _veilig(invoer),
        _veilig(oud),
        _veilig(nieuw),
    )


def _veilig(waarde: str) -> str:
    """Een ID dat de catalogus kent, een bronnaam of een foutsoort letterlijk; al het andere als lengte en hash."""
    tekst = str(waarde)
    if tekst.lower() in BRONNEN or tekst == "analysis" or (tekst.startswith("<") and tekst.endswith(">")):
        return tekst
    try:
        parse_bron_id(tekst)
    except Exception:  # onbekend of ambigu: mogelijk vrije tekst van het model
        return tekst_kenmerk(tekst, "id_")
    return tekst
