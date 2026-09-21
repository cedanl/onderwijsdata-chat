# Process-wide cache shared across all sessions — intentional, dataset loading is expensive
# and datasets are read-only. Not suitable for per-user mutable state.
_cache: dict = {}

_DUO_PREFIX = "duo:"


def put(key: str, value) -> None:
    # Sentinels hier maskeren en niet bij het laden: DUO-data komt ook binnen via
    # uploads, replay, tests en de afgeleide keys van query_data. Alleen op deze plek
    # is er geen route eromheen. Idempotent, dus al gemaskeerde data kost niets.
    if key.startswith(_DUO_PREFIX):
        from . import duo  # lazy: duo importeert store, dus niet bovenaan
        value, counts = duo.mask_sentinels(value)
        duo.record_sentinel_counts(key, counts)
    _cache[key] = value


def get(key: str):
    return _cache.get(key)


def list_keys() -> list[str]:
    return list(_cache.keys())


def clear() -> None:
    _cache.clear()
    from . import duo  # lazy: zie put()
    duo.clear_sentinel_counts()
