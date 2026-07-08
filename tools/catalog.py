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


_SYNONYMS: dict[str, list[str]] = {
    "hbo": ["ho", "hoger beroepsonderwijs"],
    "wo": ["ho", "wetenschappelijk onderwijs"],
    "ho": ["hbo", "wo", "hoger onderwijs"],
    "studenten": ["ingeschrevenen", "deelnemers", "leerlingen"],
    "leerlingen": ["deelnemers", "studenten", "ingeschrevenen"],
    "ingeschrevenen": ["studenten", "deelnemers"],
    "instroom": ["eerstejaars", "instromende", "instromers"],
    "eerstejaars": ["instroom", "instromende"],
    "diplomering": ["gediplomeerden", "gediplomeerde", "diploma"],
    "gediplomeerden": ["diplomering", "diploma"],
    "uitval": ["vsv", "voortijdig", "schoolverlaters"],
    "vsv": ["voortijdig", "schoolverlaters", "uitval"],
    "schoolverlaters": ["vsv", "voortijdig", "uitval"],
    "prognose": ["prognoses", "verwachting", "raming"],
}


def _expand_query(words: list[str]) -> list[str]:
    expanded = list(words)
    for w in words:
        for syn in _SYNONYMS.get(w, []):
            if syn not in expanded:
                expanded.append(syn)
    return expanded


_FIELD_WEIGHTS = {
    "bron": 5,
    "tags": 4,
    "voorbeeldvragen": 3,
    "beschrijving": 2,
    "doel": 2,
    "samenvatting": 2,
    "categorie": 2,
    "onderwijstype": 2,
}
_DEFAULT_WEIGHT = 1


def _score(entry: dict, words: list[str]) -> int:
    total = 0
    scored_fields = set()
    for field, weight in _FIELD_WEIGHTS.items():
        val = entry.get(field)
        if val is None:
            continue
        text = " ".join(val) if isinstance(val, list) else str(val)
        text = text.lower()
        total += sum(weight for w in words if w in text)
        scored_fields.add(field)

    for key, val in entry.items():
        if key in scored_fields or key.startswith("_"):
            continue
        text = json.dumps(val, ensure_ascii=False).lower()
        total += sum(_DEFAULT_WEIGHT for w in words if w in text)

    return total


def search_catalog(
    query: str,
    source: str = "both",
    top_n: int = 15,
    geo_niveau: str | None = None,
) -> str:
    words = _expand_query(query.lower().split())
    active = []
    archive_fallback = []

    if source in ("cbs", "both"):
        for entry in _cbs():
            s = _score(entry, words)
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
            s = _score(entry, words)
            if s:
                if entry.get("_archief"):
                    archive_fallback.append((s, {**entry}))
                else:
                    active.append((s, {**entry}))

    if not active and not archive_fallback:
        return f"Geen resultaten gevonden voor '{query}'."

    results = active if active else archive_fallback
    results.sort(key=lambda x: -x[0])
    hits = [r for _, r in results]

    if geo_niveau:
        hits = [r for r in hits if geo_niveau in (r.get("_geo_niveau") or [])]
        if not hits:
            return (
                f"Geen datasets gevonden voor '{query}' die het niveau "
                f"'{geo_niveau}' ondersteunen. Probeer een hoger aggregatieniveau "
                f"(bijv. 'provincie' in plaats van 'gemeente')."
            )

    return json.dumps(hits[:top_n], ensure_ascii=False, separators=(",", ":"))
