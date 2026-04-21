import chainlit as cl

_KEY = "_data_cache"


def put(key: str, value) -> None:
    cache = cl.user_session.get(_KEY) or {}
    cache[key] = value
    cl.user_session.set(_KEY, cache)


def get(key: str):
    return (cl.user_session.get(_KEY) or {}).get(key)


def list_keys() -> list[str]:
    return list((cl.user_session.get(_KEY) or {}).keys())
