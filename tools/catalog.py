import json
import logging
import time
from functools import cache

from onderwijsdata import catalog as _cbs_catalog
from riodata import catalog as _rio_catalog

logger = logging.getLogger(__name__)

SUPPORTED_LEVERANCIERS = frozenset({"RIO", "DUO", "ROA", "UWV"})

_DETAIL_FIELDS = frozenset({"_kolommen", "_kolomtypes", "_kolomdefinities"})

_SEARCH_KEEP_FIELDS = frozenset({
    "_cbs_id", "_ckan_id", "_rio_resource",
    "_dimensies", "_meetwaarden", "_geo_niveau",
    "_perioden_formaat", "_periode_waarden",
    "_archief", "_thema",
})


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
    "niet_geschikt_voor": 3,
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
        if isinstance(val, list):
            text = " ".join(val)
        elif isinstance(val, dict):
            text = json.dumps(val, ensure_ascii=False)
        else:
            text = str(val)
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
    t0 = time.perf_counter()
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

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if not active and not archive_fallback:
        logger.warning("search_catalog miss query=%r source=%s geo=%s elapsed_ms=%d", query, source, geo_niveau, elapsed_ms)
        return f"Geen resultaten gevonden voor '{query}'."

    results = active if active else archive_fallback
    results.sort(key=lambda x: -x[0])
    hits = [r for _, r in results]

    if geo_niveau:
        hits = [r for r in hits if geo_niveau in (r.get("_geo_niveau") or [])]
        if not hits:
            logger.warning("search_catalog miss query=%r source=%s geo=%s (geo filter) elapsed_ms=%d", query, source, geo_niveau, elapsed_ms)
            return (
                f"Geen datasets gevonden voor '{query}' die het niveau "
                f"'{geo_niveau}' ondersteunen. Probeer een hoger aggregatieniveau "
                f"(bijv. 'provincie' in plaats van 'gemeente')."
            )

    top_ids = [
        h.get("_cbs_id") or h.get("_ckan_id") or h.get("_rio_resource") or "?"
        for h in hits[:3]
    ]
    logger.info("search_catalog query=%r source=%s geo=%s results=%d top=%s elapsed_ms=%d", query, source, geo_niveau, len(hits), top_ids, elapsed_ms)

    lean = [
        {k: v for k, v in h.items() if not k.startswith("_") or k in _SEARCH_KEEP_FIELDS}
        for h in hits[:top_n]
    ]
    return json.dumps(lean, ensure_ascii=False, separators=(",", ":"))


_DETAILS_EXTRA = frozenset({"_resources"})


def _build_details(entry: dict, dataset_id: str) -> str:
    details = {k: v for k, v in entry.items() if k in (_DETAIL_FIELDS | _DETAILS_EXTRA) and v}
    if not details:
        return json.dumps(
            {"bron": entry.get("bron", dataset_id), "melding": "Geen kolomdetails beschikbaar."},
            ensure_ascii=False,
        )
    return json.dumps(
        {"bron": entry.get("bron", dataset_id), **details},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def dataset_details(dataset_id: str) -> str:
    """Geef gedetailleerde kolominformatie voor één dataset."""
    for entry in _cbs():
        if entry.get("_cbs_id") == dataset_id:
            logger.info("dataset_details id=%s bron=CBS", dataset_id)
            return _build_details({"bron": "CBS", **entry}, dataset_id)

    for entry in _rio_duo():
        eid = entry.get("_ckan_id") or entry.get("_rio_resource")
        if eid == dataset_id:
            logger.info("dataset_details id=%s bron=%s", dataset_id, entry.get("leverancier", "RIO"))
            return _build_details(entry, dataset_id)

    logger.warning("dataset_details miss id=%s", dataset_id)
    return f"Dataset '{dataset_id}' niet gevonden in de catalogus."
