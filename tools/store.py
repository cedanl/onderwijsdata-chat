import logging
import sys
import threading
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from core.config import STORE_MAX_MB
from core.sentinels import mask_sentinels

from .canoniek import sleutel as _canonieke_sleutel
from .scopeprofiel import cbs_sectordeel

logger = logging.getLogger(__name__)

# Process-wide cache shared across all sessions — intentional, dataset loading is expensive
# and datasets are read-only (the model boundary reads a copy, #209). Not suitable for
# per-user mutable state. Bounded (#13): the keys in use order, least recently used first;
# above STORE_MAX_MB the oldest go, with their meta and sentinel cells. A conversation
# whose key went gets it back from its recipe (#472), as after a restart.
_cache: OrderedDict = OrderedDict()
# What is known about the data behind a key. Describes the source, not a session,
# so it is as shareable as the data itself.
_meta: dict = {}
# Bytes per key, measured once at put(); an alias counts 0 and goes with its original.
_grootte: dict[str, int] = {}
_MAX_BYTES = STORE_MAX_MB * 1024 * 1024
# Tools run in worker threads; the LRU order and the eviction must not interleave.
_slot = threading.RLock()

_DUO_PREFIX = "duo:"

# What a tool answers when a count, sum or total would rest on truncated data (#186).
ONVOLLEDIG = (
    "De data is afgekapt: één pagina van de bron, niet de hele bron. Daarop geen telling, "
    "som of ander totaal. Verfijn met een serverfilter bij het laden (bij CBS een nauwere selectie); "
    "voor aantallen uit RIO: gebruik DUO of CBS."
)


def rijtelling(n: int, complete: bool) -> dict:
    """Rijtelling onder een naam die past: een afgekapte pagina heeft geen totaal (#177, #186, #5)."""
    return {"totaal_rijen": n} if complete else {"opgehaalde_rijen": n, "volledig": False}


@dataclass(frozen=True)
class KeyMeta:
    """What the system knows about a dataset, as data instead of a tool message (#193)."""

    bron: str  # cbs | duo | rio
    dataset: str
    resource: str | int | None = None
    volledig: bool = True  # False: a truncated page, not the whole source (#186)
    teldefinitie: str | None = None  # what DUO counts: persons or enrolments (#172)
    periodekolom: str | None = None  # STUDIEJAAR, JAAR or the CBS time dimension (#187)
    schooljaren: tuple[int, ...] | None = None  # start years in this data; None = unknown (#187)
    instellingskolom: str | None = None  # DUO institution code column (#143)
    instellingen: tuple[str, ...] | None = None  # institution codes in this data; None = unknown (#143)
    afgeleid_van: str | None = None  # the key this one was derived from
    afronding: int | None = None  # CBS publishes the counts rounded to this unit, e.g. 10 (#352)
    vier_regel: bool = False  # the data publishes 1-4 as 4: sums are an upper bound (#406)
    vier_cellen: int | None = None  # cells published as 4 in this selection; None = whole resource
    # The load call (tool, arguments): what a snippet needs to reproduce the data (#131). Provenance, not identity.
    laad: tuple[str, dict] | None = field(default=None, compare=False)
    # How this key was derived from afgeleid_van, in words for the export (#118). Provenance, not identity.
    stap: str | None = field(default=None, compare=False)
    # The keys an own computation (run_analysis) read: its selection, which it inherits suppression from (#414).
    gelezen: tuple[str, ...] | None = field(default=None, compare=False)
    # Column -> title from the source, for axis and legend titles (CBS DataProperties, #418).
    kolomtitels: Mapping[str, str] | None = field(default=None, compare=False)
    # Getallen in deze data die een eigen berekening zelf maakte, niet uit de bron: ze blijven
    # afgekeurd in elke volgende stap op deze key of zijn afleidingen (CH-27, #456).
    scriptconstanten: tuple[int | float, ...] = field(default=(), compare=False)
    # De dag (dd-mm-jjjj) waarop deze data na een herstart opnieuw bij de bron is opgehaald (#472): haar cijfers
    # kunnen afwijken van het eerdere antwoord. Een afleiding erft het niet: wat live op deze data wordt berekend,
    # is wat dat antwoord toont. Alleen wat een recept terugzet, krijgt het. Herkomst, geen identiteit.
    herladen_op: str | None = field(default=None, compare=False)


def _bytes(value) -> int:
    """Wat een waarde in het geheugen kost: een DataFrame diep gemeten, de rest naar schatting."""
    try:
        if hasattr(value, "memory_usage"):
            return int(value.memory_usage(deep=True).sum())
    except Exception:
        pass
    return sys.getsizeof(value)


def _gebruik() -> int:
    return sum(_grootte.values())


def gebruik() -> dict:
    """Hoeveel de store nu vasthoudt, voor logs en tests: keys, MB en de bovengrens."""
    with _slot:
        return {"keys": len(_cache), "mb": round(_gebruik() / 2**20, 1), "bovengrens_mb": _MAX_BYTES // 2**20}


def _verwijder(key: str, reden: str) -> None:
    """Haal `key` uit de store, met haar meta, sentinelcellen en elke alias op hetzelfde object."""
    from . import duo  # lazy: zie put()

    value = _cache.get(key)
    keys = [k for k, v in _cache.items() if v is value] if value is not None else [key]
    vrij = 0
    for k in keys:
        _cache.pop(k, None)
        _meta.pop(k, None)
        vrij += _grootte.pop(k, 0)
        duo.vergeet_sentinel_cells(k)
    logger.info(
        "STORE verwijderd keys=%s mb=%.1f reden=%s gebruik_mb=%.1f", keys, vrij / 2**20, reden, _gebruik() / 2**20
    )


def _ruim_op(behoud: str) -> None:
    """Boven de bovengrens gaan de langst niet gebruikte keys eruit; `behoud` (net gezet) blijft."""
    while _gebruik() > _MAX_BYTES and any(k != behoud for k in _cache):
        _verwijder(next(k for k in _cache if k != behoud), "bovengrens")
    if _grootte.get(behoud, 0) > _MAX_BYTES:
        logger.warning(
            "STORE key=%s is alleen al %.1f MB, boven de bovengrens van %d MB (STORE_MAX_MB); hij blijft, de rest niet",
            behoud,
            _grootte[behoud] / 2**20,
            _MAX_BYTES // 2**20,
        )


def put(key: str, value, meta: KeyMeta | None = None) -> None:
    # Sentinels hier maskeren en niet bij het laden: DUO-data komt ook binnen via
    # replay, tests en de afgeleide keys van query_data. Alleen op deze plek
    # is er geen route eromheen. Idempotent, dus al gemaskeerde data kost niets.
    if key.startswith(_DUO_PREFIX):
        from . import duo  # lazy: duo importeert store, dus niet bovenaan

        value, cells = mask_sentinels(value)
        duo.record_sentinel_cells(key, cells)
    with _slot:
        _cache[key] = value
        _cache.move_to_end(key)
        _grootte[key] = _bytes(value)
        if meta is None:
            _meta.pop(key, None)
        else:
            _meta[key] = meta
        _ruim_op(key)


def derive(parent: str, key: str, value, **changes) -> None:
    """Store data derived from `parent`; it inherits what is known about the parent.

    `changes` overrides what the derivation changed, such as the schooljaren of a selection.
    """
    parent_meta = _meta.get(parent)
    put(
        key,
        value,
        replace(parent_meta, **{"afgeleid_van": parent, "laad": None, "stap": None, "herladen_op": None, **changes})
        if parent_meta
        else None,
    )


def markeer_herladen(key: str, op: str | None) -> None:
    """Leg vast dat `key` opnieuw bij de bron is opgehaald (None: niet meer); de data zelf blijft zoals ze is (#472)."""
    with _slot:
        if (known := _meta.get(key)) is not None:
            _meta[key] = replace(known, herladen_op=op)


def get(key: str):
    """De data achter `key`; lezen maakt de key weer de jongste, zodat wat in gebruik is niet als eerste verdwijnt."""
    with _slot:
        value = _cache.get(key)
        if value is not None:
            _cache.move_to_end(key)
        return value


def readonly(key: str):
    """The model-boundary accessor: never returns the shared cached object itself.

    `run_analysis` executes model-written Python that may mutate whatever it reads. `get()`
    stays the fast internal route for our own, read-only code (#209).
    """
    value = get(key)
    return value.copy() if hasattr(value, "copy") else value


def meta(key: str) -> KeyMeta | None:
    return _meta.get(key)


def herkomst(key: str) -> list[str]:
    """De bron van een key en de stappen ertussen, oudste eerst: wat een export over zichzelf zegt (#118)."""
    stappen = []
    known = _meta.get(key)
    while known and known.afgeleid_van:
        stappen.append(f"selectie: {known.stap}" if known.stap else "selectie: eerdere stap")
        known = _meta.get(known.afgeleid_van)
    if known is None:
        return []
    bron = f"bron: {known.bron.upper()}, dataset {known.dataset}"
    if deel := cbs_sectordeel(known.dataset):
        bron += f", {deel}"
    if known.resource is not None:
        bron += f", resource {known.resource}"
    regels = [bron, *reversed(stappen)]
    if known.afronding:
        from .cbs_afronding import noot  # lazy: cbs_afronding importeert store

        regels.append(f"afronding: {noot(known.afronding)}")
    return regels


def volledig(key: str) -> bool:
    """True only when the key is known, on record, to rest on complete data (#210).

    Fail-closed: a key without KeyMeta is unknown, not complete. A source that is
    provably complete (e.g. a full CBS table) records that explicitly via KeyMeta
    instead of relying on the absence of metadata.
    """
    known = _meta.get(key)
    return known is not None and known.volledig


def canoniek(key: str) -> str:
    """De key in de store waar een variant als `cbs_85353NED` of `CBS:85353ned` op doelt (#331).

    Alleen een eenduidige treffer; anders blijft de key zoals hij was en meldt de tool hem onbekend.
    De spelling zelf normaliseert tools/canoniek.py (#342): hier alleen de opzoekstap.
    """
    if key in _cache:
        return key
    gezocht = _canonieke_sleutel(key)
    treffers = [k for k in _cache if k.lower() == gezocht]
    return treffers[0] if len(treffers) == 1 else key


def alias(oud: str | None, key: str) -> None:
    """Zet dezelfde data ook onder haar key van vóór de canonieke digest (#342).

    Bewaarde recepten, dashboards en exports verwijzen nog naar die oude keys; een
    herlaad- of ververs-slag die de data opnieuw afleidt, houdt ze zo werkend. Alleen
    de cache en de meta: sentinelcellen hangen aan de canonieke key.
    """
    with _slot:
        if not oud or oud == key or oud in _cache or key not in _cache:
            return
        _cache[oud] = _cache[key]
        _grootte[oud] = 0  # hetzelfde object: de bytes staan bij `key`, en de alias gaat met haar mee
        if key in _meta:
            _meta[oud] = _meta[key]


def list_keys() -> list[str]:
    with _slot:
        return list(_cache.keys())


def clear() -> None:
    from . import cbs, duo  # lazy: zie put()

    with _slot:
        _cache.clear()
        _meta.clear()
        _grootte.clear()
        duo.clear_sentinel_cells()
        cbs.clear_dimensions()
