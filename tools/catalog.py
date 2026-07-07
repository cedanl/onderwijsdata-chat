import json
from functools import cache

from onderwijsdata import catalog as _cbs_catalog
from riodata import catalog as _rio_catalog

SUPPORTED_LEVERANCIERS = frozenset({"RIO", "DUO"})


@cache
def _cbs() -> list:
    return _cbs_catalog()


@cache
def _rio_duo() -> list:
    return _rio_catalog(source="all")


def search_catalog(query: str, source: str = "both", top_n: int = 15) -> str:
    words = query.lower().split()
    active = []
    archive_fallback = []

    def score(entry: dict) -> int:
        text = json.dumps(entry, ensure_ascii=False).lower()
        return sum(w in text for w in words)

    if source in ("cbs", "both"):
        for entry in _cbs():
            s = score(entry)
            if s:
                tagged = {"bron": "CBS", **entry}
                if entry.get("_archief"):
                    archive_fallback.append((s, tagged))
                else:
                    active.append((s, tagged))

    if source in ("rio", "both", "duo"):
        for entry in _rio_duo():
            if str(entry.get("leverancier", "")).upper() not in SUPPORTED_LEVERANCIERS:
                continue
            is_duo = str(entry.get("leverancier", "")).upper() == "DUO"
            if source == "duo" and not is_duo:
                continue
            s = score(entry)
            if s:
                if entry.get("_archief"):
                    archive_fallback.append((s, {**entry}))
                else:
                    active.append((s, {**entry}))

    if not active and not archive_fallback:
        return f"Geen resultaten gevonden voor '{query}'."

    results = active if active else archive_fallback
    results.sort(key=lambda x: -x[0])
    return json.dumps([r for _, r in results[:top_n]], ensure_ascii=False, separators=(",", ":"))
