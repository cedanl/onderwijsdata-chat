import re
from dataclasses import dataclass, field, replace

from core.sentinels import mask_sentinels

# Process-wide cache shared across all sessions — intentional, dataset loading is expensive
# and datasets are read-only. Not suitable for per-user mutable state.
_cache: dict = {}
# What is known about the data behind a key. Describes the source, not a session,
# so it is as shareable as the data itself.
_meta: dict = {}

_DUO_PREFIX = "duo:"

# What a tool answers when a count, sum or total would rest on truncated data (#186).
ONVOLLEDIG = (
    "De data is afgekapt: één pagina van de bron, niet de hele bron. Daarop geen telling, "
    "som of ander totaal. Verfijn met een serverfilter bij het laden (bij CBS $filter of $select); "
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


def put(key: str, value, meta: KeyMeta | None = None) -> None:
    # Sentinels hier maskeren en niet bij het laden: DUO-data komt ook binnen via
    # replay, tests en de afgeleide keys van query_data. Alleen op deze plek
    # is er geen route eromheen. Idempotent, dus al gemaskeerde data kost niets.
    if key.startswith(_DUO_PREFIX):
        from . import duo  # lazy: duo importeert store, dus niet bovenaan

        value, cells = mask_sentinels(value)
        duo.record_sentinel_cells(key, cells)
    _cache[key] = value
    if meta is None:
        _meta.pop(key, None)
    else:
        _meta[key] = meta


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


def get(key: str):
    return _cache.get(key)


def readonly(key: str):
    """The model-boundary accessor: never returns the shared cached object itself.

    `run_analysis` executes model-written Python that may mutate whatever it reads. `get()`
    stays the fast internal route for our own, read-only code (#209).
    """
    value = _cache.get(key)
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
    """
    if key in _cache:
        return key
    gezocht = re.sub(r"^(cbs|duo|rio)[_/]", r"\1:", key, flags=re.IGNORECASE).lower()
    treffers = [k for k in _cache if k.lower() == gezocht]
    return treffers[0] if len(treffers) == 1 else key


def list_keys() -> list[str]:
    return list(_cache.keys())


def clear() -> None:
    _cache.clear()
    _meta.clear()
    from . import cbs, duo  # lazy: zie put()

    duo.clear_sentinel_cells()
    cbs.clear_dimensions()
