from dataclasses import dataclass, replace

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
    "som of ander totaal. Verfijn met een serverfilter bij het laden, of gebruik DUO of CBS voor aantallen."
)


@dataclass(frozen=True)
class KeyMeta:
    """What the system knows about a dataset, as data instead of a tool message (#193)."""

    bron: str                            # cbs | duo | rio
    dataset: str
    resource: str | int | None = None
    volledig: bool = True                # False: a truncated page, not the whole source (#186)
    teldefinitie: str | None = None      # what DUO counts: persons or enrolments (#172)
    periodekolom: str | None = None      # STUDIEJAAR, JAAR or the CBS time dimension (#187)
    schooljaren: tuple[int, ...] | None = None  # start years in this data; None = unknown (#187)
    instellingskolom: str | None = None  # DUO institution code column (#143)
    instellingen: tuple[str, ...] | None = None  # institution codes in this data; None = unknown (#143)
    afgeleid_van: str | None = None      # the key this one was derived from


def put(key: str, value, meta: KeyMeta | None = None) -> None:
    # Sentinels hier maskeren en niet bij het laden: DUO-data komt ook binnen via
    # replay, tests en de afgeleide keys van query_data. Alleen op deze plek
    # is er geen route eromheen. Idempotent, dus al gemaskeerde data kost niets.
    if key.startswith(_DUO_PREFIX):
        from . import duo  # lazy: duo importeert store, dus niet bovenaan
        value, cells = duo.mask_sentinels(value)
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
    put(key, value, replace(parent_meta, afgeleid_van=parent, **changes) if parent_meta else None)


def get(key: str):
    return _cache.get(key)


def meta(key: str) -> KeyMeta | None:
    return _meta.get(key)


def volledig(key: str) -> bool:
    """False only when the key is known to rest on truncated data; unknown counts as complete."""
    known = _meta.get(key)
    return known is None or known.volledig


def list_keys() -> list[str]:
    return list(_cache.keys())


def clear() -> None:
    _cache.clear()
    _meta.clear()
    from . import cbs, duo  # lazy: zie put()
    duo.clear_sentinel_cells()
    cbs.clear_dimensions()
