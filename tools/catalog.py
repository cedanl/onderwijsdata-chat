import json
from functools import cache

from onderwijsdata import catalog as _cbs_catalog
from riodata import catalog as _rio_catalog


@cache
def _cbs() -> list:
    return _cbs_catalog()


@cache
def _rio_duo() -> list:
    return _rio_catalog(source="all")


def search_catalog(query: str, source: str = "both", top_n: int = 15) -> str:
    words = query.lower().split()
    scored = []

    def score(entry: dict) -> int:
        text = json.dumps(entry, ensure_ascii=False).lower()
        return sum(w in text for w in words)

    if source in ("cbs", "both"):
        for entry in _cbs():
            s = score(entry)
            if s:
                scored.append((s, {"bron": "CBS", **entry}))

    if source in ("rio", "both", "duo"):
        for entry in _rio_duo():
            is_duo = str(entry.get("leverancier", "")).upper() == "DUO"
            if source == "duo" and not is_duo:
                continue
            s = score(entry)
            if s:
                scored.append((s, {**entry}))

    if not scored:
        return f"Geen resultaten gevonden voor '{query}'."

    scored.sort(key=lambda x: -x[0])
    return json.dumps([r for _, r in scored[:top_n]], ensure_ascii=False, separators=(",", ":"))
