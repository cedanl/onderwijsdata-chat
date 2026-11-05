import contextlib
import logging
import sys
import threading
from collections import OrderedDict
from collections.abc import Callable, Generator, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import TYPE_CHECKING

from core import actualiteit
from core.config import STORE_MAX_MB
from core.sentinels import lege_cellen, mask_sentinels

from .canoniek import sleutel as _canonieke_sleutel
from .catalog import bronetiketten

if TYPE_CHECKING:
    from .regiolocaties import Nevenlocatie

logger = logging.getLogger(__name__)

# Process-wide cache shared across all sessions — intentional, dataset loading is expensive
# and datasets are read-only (the model boundary reads a copy, #209). Not suitable for
# per-user mutable state. Bounded (#13): the keys in use order, least recently used first;
# above STORE_MAX_MB the oldest go, with their meta and sentinel cells. Bounded in time too (#864):
# a key fetched longer than actualiteit.TTL ago goes when it is read. A conversation
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
_CBS_PREFIX = "cbs:"

# Welke keys het gesprek van deze context zelf maakte (#13): de store is gedeeld over alle sessies,
# maar wat een tool over beschikbare data zegt, gaat alleen over het eigen gesprek. De chatroute zet
# per verbinding een lezer van session["data_keys"]; taken en threads van die verbinding erven hem.
_gesprek: ContextVar[Callable[[], list[str]] | None] = ContextVar("gesprek_keys", default=None)

# What a tool answers when a count, sum or total would rest on truncated data (#186).
ONVOLLEDIG = (
    "De data is afgekapt: één pagina van de bron, niet de hele bron. Daarop geen telling, "
    "som of ander totaal. Verfijn met een serverfilter bij het laden (bij CBS een nauwere selectie); "
    "voor aantallen uit RIO: gebruik DUO of CBS."
)

# What a report tells its reader about a source it holds one page of (#578). For the reader, like
# exportnoten.ONVOLLEDIG_EXPORT; ONVOLLEDIG above instructs the model. `aantal` is AFGEKAPT_AANTAL or
# empty when the row count is unknown.
AFGEKAPT = (
    "de app haalde één pagina van de bron op{aantal}, niet de hele bron; "
    "rijen buiten die pagina ontbreken in dit rapport."
)
AFGEKAPT_AANTAL = " ({rijen} rijen)"


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
    # Wanneer een momentopname (UWV, ROA) is genomen, in de woorden van de bron: "peildatum 2023-05-16",
    # "versie v20251218"; bij DUO wanneer het bestand is vervangen, "versie van 08-04-2026" (#717). Een bronregel noemt
    # het achter de titel (#577). Herkomst, geen identiteit.
    peilmoment: str | None = field(default=None, compare=False)
    # De md5 van het geladen DUO-bestand (#717): gelijk aan de hash die DUO bij het bestand vermeldt, na te rekenen met
    # md5sum. Vervangt voor DUO de eigen inhoudshash (#715). Herkomst, geen identiteit.
    bronhash: str | None = field(default=None, compare=False)
    # De dag (jjjj-mm-dd) waarop een levend register (RIO) is bevraagd, als `datumGeldigOp` (#718): dezelfde dag geeft
    # dezelfde stand, dus de snippet zet hem erin. None bij een bron die geen tijdreizen kent. Herkomst, geen identiteit.
    geldig_op: str | None = field(default=None, compare=False)
    # Wanneer de app de data bij de bron ophaalde (#864): een afgeleide key erft het van zijn ouder, want zijn data is
    # even oud. Na actualiteit.TTL verdwijnt de key bij het lezen en haalt het gesprek hem uit zijn recept opnieuw op.
    opgehaald_op: datetime = field(default_factory=lambda: actualiteit.nu(), compare=False)
    # De dag (jjjj-mm-dd) waarop de bron de tabel het laatst bijwerkte: bij CBS TableInfos.Modified, live gevraagd
    # bij het ophalen en anders uit de catalogus (#864). Herkomst, geen identiteit.
    bijgewerkt_op: str | None = field(default=None, compare=False)
    # Bevat deze lading het vo-deel van een bron over meer onderwijssoorten, als vo-context voor vervolgonderwijs
    # (#879, #880)? Per lading en niet per tabel: de poort van een latere beurt verandert de bronregel van deze niet.
    vo_context: bool = False
    # Per instelling in deze selectie met een fusie binnen haar reeks de vaste regel voor onder het antwoord (#728):
    # DUO telt de jaren vóór de fusie bij de huidige instelling. Vastgelegd bij het afleiden (dekking.van), en zo ook
    # geërfd door een som of grafiek op deze selectie. Herkomst, geen identiteit.
    fusies: tuple[str, ...] = field(default=(), compare=False)
    # De instellingen die alleen via een onderwijslocatie in het gefilterde gebied in deze selectie kwamen (#744): de
    # vaste regel onder het antwoord en de snippet lezen ze hier. Geërfd zolang de instelling in de selectie staat
    # (dekking.van). Herkomst, geen identiteit.
    nevenlocaties: "tuple[Nevenlocatie, ...]" = field(default=(), compare=False)
    # Wat de getallen van een bron met een eigen tool tellen, als vaste regels voor het Telling-blok (#956): over hoeveel
    # eenheden het sectorcijfer van DUO's verantwoording gaat, of wat fte en personen in WOPI zijn. De tool zet ze bij het
    # laden. Herkomst, geen identiteit.
    telregels: tuple[str, ...] = field(default=(), compare=False)


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
    elif key.startswith(_CBS_PREFIX) and not (meta and meta.afgeleid_van):
        # Een geladen CBS-tabel: haar lege cellen ('.') zijn onderdrukt, net als DUO -1 (#862). Een afgeleide key
        # krijgt de cellen van zijn selectie van wie hem afleidt (query_data); een leeg groepstotaal is geen broncel.
        from . import duo

        duo.record_sentinel_cells(key, lege_cellen(value))
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
        replace(parent_meta, **{"afgeleid_van": parent, "laad": None, "stap": None, **changes})
        if parent_meta
        else None,
    )


def _verlopen(key: str) -> bool:
    """Is de data achter `key` langer dan de TTL geleden opgehaald? Een key zonder meta heeft geen ophaalmoment."""
    known = _meta.get(key)
    return known is not None and actualiteit.verlopen(known.opgehaald_op)


def get(key: str):
    """De data achter `key`; lezen maakt de key weer de jongste, zodat wat in gebruik is niet als eerste verdwijnt.

    Een key die langer dan de TTL geleden is opgehaald, gaat eruit en geeft None (#864): zoals na verdringing haalt het
    gesprek hem uit zijn recept terug, nu met wat de bron vandaag zegt.
    """
    with _slot:
        value = _cache.get(key)
        if value is not None and _verlopen(key):
            _verwijder(key, "leeftijd")
            return None
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
    if etiket := bronetiketten(known.dataset, vo_context=known.vo_context):
        bron += f", {etiket}"
    if known.resource is not None:
        bron += f", resource {known.resource}"
    if known.peilmoment:
        # Een momentopname of editie (UWV, ROA, WOPI, de financien) zegt wanneer; DUO welke versie van het bestand.
        bron += f", {known.peilmoment}"
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


@contextlib.contextmanager
def gesprek(keys: Callable[[], list[str]]) -> Generator[None, None, None]:
    """Binnen dit blok is `keys()` de lijst data-keys van het gesprek dat deze context bedient (#13).

    Een lezer en geen lijst: de sessie vervangt haar lijst bij het openen van een ander gesprek.
    """
    token = _gesprek.set(keys)
    try:
        yield
    finally:
        _gesprek.reset(token)


def eigen_keys() -> list[str]:
    """De keys van het eigen gesprek die de store nog heeft; buiten een gesprek geen enkele (fail-closed)."""
    lezer = _gesprek.get()
    if lezer is None:
        return []
    with _slot:
        return [key for key in lezer() if key in _cache]


def clear() -> None:
    from . import cbs, duo  # lazy: zie put()

    with _slot:
        _cache.clear()
        _meta.clear()
        _grootte.clear()
        duo.clear_sentinel_cells()
        cbs.clear_dimensions()
