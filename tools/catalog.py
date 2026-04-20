import json

from onderwijsdata import catalog as cbs_catalog
from riodata import catalog as rio_catalog


def search_catalog(query: str, source: str = "both") -> str:
    q = query.lower()
    results = []

    if source in ("cbs", "both"):
        for entry in cbs_catalog():
            if q in json.dumps(entry, ensure_ascii=False).lower():
                results.append({"bron": "CBS", **entry})

    if source in ("rio", "both"):
        for entry in rio_catalog():
            if q in json.dumps(entry, ensure_ascii=False).lower():
                results.append({"bron": "RIO", **entry})

    if not results:
        return f"Geen resultaten gevonden voor '{query}'."

    return json.dumps(results[:10], ensure_ascii=False, indent=2)
