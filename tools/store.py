_cache: dict = {}


def put(key: str, value) -> None:
    _cache[key] = value


def get(key: str):
    return _cache.get(key)


def list_keys() -> list[str]:
    return list(_cache.keys())


def clear() -> None:
    _cache.clear()
