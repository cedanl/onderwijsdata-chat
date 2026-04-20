import json
from functools import cache

from onderwijsdata import catalog as _cbs_catalog
from riodata import catalog as _rio_catalog


@cache
def _cbs() -> list:
    return _cbs_catalog()


@cache
def _rio() -> list:
    return _rio_catalog()


def search_catalog(query: str, source: str = "both") -> str:
    q = query.lower()
    results = []

    if source in ("cbs", "both"):
        for entry in _cbs():
            if q in json.dumps(entry, ensure_ascii=False).lower():
                results.append({"bron": "CBS", **entry})

    if source in ("rio", "both"):
        for entry in _rio():
            if q in json.dumps(entry, ensure_ascii=False).lower():
                results.append({"bron": "RIO", **entry})

    if not results:
        return f"Geen resultaten gevonden voor '{query}'."

    return json.dumps(results[:10], ensure_ascii=False, separators=(",", ":"))
