_KEY = "_data_cache"
_fallback: dict = {}


def _cache() -> dict:
    try:
        import chainlit as cl
        return cl.user_session.get(_KEY) or {}
    except Exception:
        return _fallback


def _set_cache(cache: dict) -> None:
    try:
        import chainlit as cl
        cl.user_session.set(_KEY, cache)
    except Exception:
        _fallback.update(cache)


def put(key: str, value) -> None:
    cache = _cache()
    cache[key] = value
    _set_cache(cache)


def get(key: str):
    return _cache().get(key)


def list_keys() -> list[str]:
    return list(_cache().keys())


