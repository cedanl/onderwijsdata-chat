import json
import logging
import math
import re
import time
from functools import cache

from onderwijsdata import catalog as _cbs_catalog
from riodata import catalog as _rio_catalog

from .duo_meta import teldefinitie

logger = logging.getLogger(__name__)

# Leveranciers waarvoor we search_catalog actief steunen.
# "Inspectie van het Onderwijs" (2 datasets) en "SBB" (2 datasets) staan wel in de ruwe
# catalogus maar hebben geen bruikbare machineleesbare resources — hun structuur is niet
# geschikt voor de query-interfaces (search_catalog, get_*_data). Deze filtered-out state
# is intentioneel: README mag ze niet noemen, want zij zijn niet bereikbaar voor gebruikers.
SUPPORTED_LEVERANCIERS = frozenset({"RIO", "DUO", "ROA", "UWV"})

_DETAIL_FIELDS = frozenset({"_kolommen", "_kolomtypes", "_kolomdefinities"})

# F1: Nederlandse stopwoorden + vraagwoorden die ruis veroorzaken
_STOPWOORDEN = frozenset({
    "de", "het", "een", "en", "of", "aan", "bij", "voor", "in", "op", "uit", "met", "van", "naar",
    "is", "zijn", "ben", "was", "waren", "het", "dit", "dat", "deze", "die",
    "hoe", "wat", "waar", "wanneer", "wie", "welke", "waarom",
    "kan", "mag", "moet", "wil", "zal", "zou", "kan", "krijgt", "krijgen",
    "heeft", "hebben", "dar", "door", "tot", "over", "om", "zonder",
})

# F3: Log-damping coefficient — scales penalty for oversized entries
# Balances large-dataset bias without over-penalizing; see _length_damping_factor
_DAMPING_SCALE = 0.2

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


def dataset_counts() -> dict[str, int]:
    """Datasets per bron zoals de app ze doorzoekt; bron voor databronnenvenster en README.

    CBS telt ook gearchiveerde tabellen mee: search_catalog valt daarop terug.
    """
    rio_duo = _rio_duo()
    return {
        "CBS": len(_cbs()),
        "DUO": sum(1 for e in rio_duo if e.get("leverancier") == "DUO"),
        "RIO": sum(1 for e in rio_duo if e.get("leverancier") == "RIO"),
    }


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
    # F4: Aangevuld — deze woorden staan niet in metadata maar worden veel gezocht
    "voltijd": ["vt", "volledig", "fulltijd", "opleidingsvorm"],
    "deeltijd": ["dt", "part-time", "parttijd", "opleidingsvorm"],
    "duaal": ["du", "duale", "leerlingplek", "opleidingsvorm"],
    "opleidingsvorm": ["voltijd", "deeltijd", "duaal", "vt", "dt", "du"],
    "deelname": ["ingeschrevenen", "instroom", "deelnemers"],
    "voortgezet": ["vo", "vso", "leerlingen"],
    "basisonderwijs": ["primair", "po", "leerlingen"],
    "mbo": ["middelbaar", "beroepsonderwijs"],
}


def _filter_stopwoorden(words: list[str]) -> list[str]:
    """Remove stopwoorden; fallback to all words if nothing remains."""
    filtered = [w for w in words if w not in _STOPWOORDEN]
    return filtered if filtered else words


def _expand_query(words: list[str]) -> list[tuple[str, float]]:
    """Expand query with synonyms, weighted differently.

    F5: User words get full weight (1.0), synonyms get lower weight (0.35).
    This prevents synonyms from overfitting results.
    Example: "ingeschrevenen wo" shouldn't match "Ho-cohorten" equally well.
    """
    weighted = [(w, 1.0) for w in words]
    seen = set(words)
    for w in words:
        for syn in _SYNONYMS.get(w, []):
            if syn not in seen:
                weighted.append((syn, 0.35))
                seen.add(syn)
    return weighted


def _word_match(word: str, text: str) -> bool:
    """F2: Word boundary matching.

    Short terms (≤3 chars) need word boundaries to avoid noise (vo, po, ho, etc).
    Longer terms use prefix matching (query="instel", match="instelling").
    """
    if len(word) <= 3:
        # Word boundary required for short terms
        return bool(re.search(rf"\b{re.escape(word)}\b", text))
    else:
        # Prefix matching for longer terms
        return word in text


def _entry_size(entry: dict) -> int:
    """F3: Calculate total text length of an entry for length normalization."""
    size = 0
    for key, val in entry.items():
        if key.startswith("_"):
            continue
        if isinstance(val, list):
            size += len(" ".join(str(v) for v in val))
        elif isinstance(val, dict):
            size += len(json.dumps(val, ensure_ascii=False))
        else:
            size += len(str(val))
    return size


def _length_damping_factor(entry: dict, reference_size: int = 5000) -> float:
    """F3: Log-damping for large entries.

    Large entries (RIO registers) have more text, thus more random matches.
    Apply logarithmic dampening: log(size/ref) to penalize oversized entries.
    Reference size ~5000 chars (typical stat dataset).
    """
    size = _entry_size(entry)
    if size <= reference_size:
        return 1.0
    # Gentle log damping: avoid over-penalizing large datasets
    # Example: 47x larger → log(47) ≈ 3.85 → divide by ~1.77 → 56% penalty
    return 1.0 / (1.0 + math.log(size / reference_size) * _DAMPING_SCALE)


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


def _score(entry: dict, weighted_words: list[tuple[str, float]]) -> float:
    total = 0
    for key, val in entry.items():
        if key.startswith("_"):
            continue

        # Determine field weight: explicit weight or default
        field_weight = _FIELD_WEIGHTS.get(key, _DEFAULT_WEIGHT)

        # Convert to text
        if isinstance(val, list):
            text = " ".join(val)
        elif isinstance(val, dict):
            text = json.dumps(val, ensure_ascii=False)
        else:
            text = str(val)
        text = text.lower()

        # F5: Weight word by its user/synonym weight, multiplied by field weight
        total += sum(field_weight * word_weight for w, word_weight in weighted_words if _word_match(w, text))

    # F3: Apply length damping factor
    damping = _length_damping_factor(entry)
    return total * damping


def search_catalog(
    query: str,
    source: str = "both",
    top_n: int = 15,
    geo_niveau: str | None = None,
) -> str:
    t0 = time.perf_counter()
    query_words = query.lower().split()
    # F1: Filter stopwoorden
    filtered_words = _filter_stopwoorden(query_words)
    words = _expand_query(filtered_words)
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

    results = active or archive_fallback
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


_DETAILS_EXTRA = frozenset({"_resources", "teldefinitie"})


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


def catalogus_titel(dataset_id: str) -> str:
    """Menselijke titel (bron-veld) uit de catalogus voor een dataset-ID.

    Zoekt in de CBS- én de RIO/DUO-catalogus. Valt terug op de dataset-ID zelf
    als de dataset niet (meer) in de catalogus staat.
    """
    for entry in _cbs():
        if entry.get("_cbs_id") == dataset_id:
            return entry.get("bron") or dataset_id
    for entry in _rio_duo():
        if (entry.get("_ckan_id") or entry.get("_rio_resource")) == dataset_id:
            return entry.get("bron") or dataset_id
    return dataset_id


def rio_filters(resource: str) -> list[str]:
    """De serverfilters die een RIO-resource accepteert, uit de catalogus; leeg als onbekend."""
    for entry in _rio_duo():
        if entry.get("_rio_resource") == resource:
            return list(entry.get("filters") or [])
    return []


def catalogus_laatste_update(dataset_id: str) -> str | None:
    """Laatste update datum uit de catalogus voor een CBS dataset-ID.

    Geeft ISO-datestring (bv '2026-04-14') of None als dataset niet gevonden.
    """
    for entry in _cbs():
        if entry.get("_cbs_id") == dataset_id:
            return entry.get("_laatste_update")
    return None


def resource_titel(dataset_id: str, resource: int | str = 0) -> str | None:
    """Resourcenaam uit de catalogus voor een DUO/RIO dataset.

    Volgt dezelfde selectielogica als het laden zelf: index (int) of
    naam-substring (str). Geeft None als er geen resources zijn of niet gevonden.
    """
    for entry in _rio_duo():
        if (entry.get("_ckan_id") or entry.get("_rio_resource")) == dataset_id:
            resources = entry.get("_resources") or []
            if not resources:
                return None
            try:
                if isinstance(resource, int):
                    if resource >= len(resources):
                        return None
                    return resources[resource].get("naam")
                matches = [r for r in resources if resource.lower() in (r.get("naam") or "").lower()]
                return matches[0].get("naam") if matches else None
            except Exception:
                return None
    return None


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
            if entry.get("leverancier") == "DUO":
                # Het moment waarop het model tussen bijv. p01 en p03 kiest (#172).
                entry = {**entry, "teldefinitie": teldefinitie(dataset_id)}
            return _build_details(entry, dataset_id)

    logger.warning("dataset_details miss id=%s", dataset_id)
    return f"Dataset '{dataset_id}' niet gevonden in de catalogus."
