import hashlib
import json
import logging
import math
import re
import time
from functools import cache

from onderwijsdata import catalog as _cbs_catalog
from riodata import catalog as _rio_catalog
from riodata import scope

from . import duo_meta, instelling

logger = logging.getLogger(__name__)

# Leveranciers waarvoor we search_catalog actief steunen.
# "Inspectie van het Onderwijs" (2 datasets) en "SBB" (2 datasets) staan wel in de ruwe
# catalogus maar hebben geen bruikbare machineleesbare resources — hun structuur is niet
# geschikt voor de query-interfaces (search_catalog, get_*_data). Deze filtered-out state
# is intentioneel: README mag ze niet noemen, want zij zijn niet bereikbaar voor gebruikers.
SUPPORTED_LEVERANCIERS = frozenset({"RIO", "DUO", "ROA", "UWV"})

# Bronnen waarvan de chat data kan ophalen (get_cbs_data, get_duo_data, get_rio_data).
# ROA en UWV staan wel in de catalogus en voeden de dashboards, maar zonder datatool
# mag het model er geen cijfers voor geven, en ook niet concluderen dat ze niet
# bestaan (#200).
CHAT_BRONNEN = ("CBS", "DUO", "RIO")
_NIET_OPVRAAGBAAR = {
    "opvraagbaar": False,
    "melding": (
        "Deze bron staat in de catalogus, maar is in de chat niet op te vragen: er is geen "
        "datatool voor. Noem de dataset, geef er geen cijfers voor, en zeg niet dat de bron niet bestaat."
    ),
}


def _via_chat(entry: dict) -> bool:
    return str(entry.get("leverancier", "")).upper() in CHAT_BRONNEN


_DETAIL_FIELDS = frozenset({"_kolommen", "_kolomtypes", "_kolomdefinities"})

# F1: Nederlandse stopwoorden + vraagwoorden die ruis veroorzaken
_STOPWOORDEN = frozenset(
    {
        "de",
        "het",
        "een",
        "en",
        "of",
        "aan",
        "bij",
        "voor",
        "in",
        "op",
        "uit",
        "met",
        "van",
        "naar",
        "is",
        "zijn",
        "ben",
        "was",
        "waren",
        "dit",
        "dat",
        "deze",
        "die",
        "hoe",
        "wat",
        "waar",
        "wanneer",
        "wie",
        "welke",
        "waarom",
        "kan",
        "mag",
        "moet",
        "wil",
        "zal",
        "zou",
        "krijgt",
        "krijgen",
        "heeft",
        "hebben",
        "dar",
        "door",
        "tot",
        "over",
        "om",
        "zonder",
    }
)

# F3: Log-damping coefficient — scales penalty for oversized entries
# Balances large-dataset bias without over-penalizing; see _length_damping_factor
_DAMPING_SCALE = 0.2

_SEARCH_KEEP_FIELDS = frozenset(
    {
        "_cbs_id",
        "_ckan_id",
        "_rio_resource",
        "_dimensies",
        "_meetwaarden",
        "_geo_niveau",
        "_perioden_formaat",
        "_periode_waarden",
        "_archief",
        "_thema",
    }
)


@cache
def _cbs() -> list:
    return _cbs_catalog()


@cache
def _rio_duo() -> list:
    """De RIO/DUO-catalogus zonder records die riodata buiten mbo/hbo/wo plaatst (#375).

    Het scopebesluit staat per record in riodata; zoeken, details en telling volgen het,
    ook bij een leverancier die de chat verder ondersteunt.
    """
    return [e for e in _rio_catalog(source="all") if not scope.buiten_scope(e)]


def _dataset_id(entry: dict) -> str:
    return entry.get("_cbs_id") or entry.get("_ckan_id") or entry.get("_rio_resource") or "?"


@cache
def catalogus_digest() -> str:
    """Korte hash over de geladen catalogus: een verschoven top-3 is zo terug te voeren op een
    andere catalogus of op een codewijziging (#344)."""
    inhoud = json.dumps([_cbs(), _rio_duo()], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(inhoud.encode()).hexdigest()[:12]


def dataset_counts() -> dict[str, int]:
    """Datasets per bron die de chat kan opvragen; bron voor startpagina, databronnenvenster en README.

    CBS telt ook gearchiveerde tabellen mee: search_catalog valt daarop terug.
    """
    rio_duo = _rio_duo()
    return {
        "CBS": len(_cbs()),
        "DUO": sum(1 for e in rio_duo if e.get("leverancier") == "DUO"),
        "RIO": sum(1 for e in rio_duo if e.get("leverancier") == "RIO"),
    }


def catalogus_telling() -> str:
    """De telling als toolresultaat: een aantal datasets komt uit code, niet uit zoekresultaten (#168)."""
    return json.dumps(
        {
            "datasets_per_bron": dataset_counts(),
            "cbs_gearchiveerd": sum(1 for e in _cbs() if e.get("_archief")),
            "toelichting": "Datasets die deze chat kan opvragen. CBS telt gearchiveerde tabellen mee.",
        },
        ensure_ascii=False,
    )


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


_SPLITSTEKENS = ".,;:!?()\"'"
_VOLZIN_MIN_WOORDEN = 6


def _woorden(query: str) -> list[str]:
    """Kleine letters, zonder leestekens ("VU?" zoekt als "vu")."""
    return [w for w in (w.strip(_SPLITSTEKENS) for w in query.lower().split()) if w]


def _volzin_hint(query: str, woorden: list[str], trefwoorden: list[str]) -> str | None:
    """Een volzin of vraag wordt als trefwoorden gezocht; zeg dat, zodat het model het afleert (#17)."""
    is_volzin = len(woorden) >= _VOLZIN_MIN_WOORDEN or query.rstrip().endswith("?")
    if not is_volzin or trefwoorden == woorden:
        return None
    return (
        f"Query genormaliseerd naar trefwoorden: '{' '.join(trefwoorden)}'. "
        "Gebruik voortaan 2 tot 4 losse trefwoorden, geen volzin of vraag."
    )


def _filter_stopwoorden(words: list[str]) -> list[str]:
    """Remove stopwoorden; fallback to all words if nothing remains."""
    filtered = [w for w in words if w not in _STOPWOORDEN]
    return filtered or words


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
    "beschrijving": 2,
    "doel": 2,
    "samenvatting": 2,
    "categorie": 2,
    "onderwijstype": 2,
}
_DEFAULT_WEIGHT = 1
# Blijft zichtbaar in het resultaat, maar scoort niet: "Niet geschikt voor gemeente" is geen treffer voor "gemeente" (#350).
_NIET_ZOEKBAAR = frozenset({"niet_geschikt_voor"})
_HISTORISCH = frozenset({"historisch", "historische", "archief", "gearchiveerd", "gearchiveerde"})


def _score(entry: dict, weighted_words: list[tuple[str, float]]) -> float:
    total = 0
    for key, val in entry.items():
        if key.startswith("_") or key in _NIET_ZOEKBAAR:
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


def geodekking(entry: dict, niveau: str) -> str:
    """Biedt de dataset dit geografische niveau: "ja", "nee" of "onbekend" (#351).

    Een lege `_geo_niveau` is alleen landelijk (#237) als de catalogus de structuur
    kent: CBS-dimensies of DUO/RIO-kolommen zonder regio. Ontbreekt het veld of de
    structuur, dan heeft niemand gekeken; dat is onbekend, niet landelijk.
    """
    niveaus = entry.get("_geo_niveau")
    if niveaus:
        return "ja" if niveau in niveaus else "nee"
    if niveaus is None or not (entry.get("_dimensies") or entry.get("_kolommen")):
        return "onbekend"
    return "ja" if niveau == "landelijk" else "nee"


def _verzamel(words: list[tuple[str, float]], source: str) -> tuple[list, list]:
    """De scorende treffers uit `source`, gesplitst in actief en archief."""
    active: list = []
    archive: list = []

    if source in ("cbs", "both"):
        for entry in _cbs():
            if s := _score(entry, words):
                (archive if entry.get("_archief") else active).append((s, {"bron": "CBS", **entry}))

    if source in ("rio", "both", "duo"):
        for entry in _rio_duo():
            if str(entry.get("leverancier", "")).upper() not in SUPPORTED_LEVERANCIERS:
                continue
            is_duo = str(entry.get("leverancier", "")).upper() == "DUO"
            if source == "duo" and not is_duo:
                continue
            if s := _score(entry, words):
                hit = {**entry} if _via_chat(entry) else {**entry, **_NIET_OPVRAAGBAAR}
                (archive if entry.get("_archief") else active).append((s, hit))

    return active, archive


def _gerangschikt(treffers: list, geo_niveau: str | None) -> tuple[list[dict], list[str]]:
    """De treffers op volgorde, en de dataset-ID's waarvan de geodekking onbekend is."""
    # Gelijke score: de dataset-ID beslist, niet de inleesvolgorde van de catalogus (#344).
    treffers = sorted(treffers, key=lambda x: (-x[0], _dataset_id(x[1])))
    hits = [r for _, r in treffers]
    if not geo_niveau:
        return hits, []
    dekking = [(r, geodekking(r, geo_niveau)) for r in hits]
    return [r for r, d in dekking if d == "ja"], [_dataset_id(r) for r, d in dekking if d == "onbekend"]


_MAX_ONBEKEND = 5


def _onbekende_dekking(ids: list[str], geo_niveau: str) -> str:
    return (
        f"Weggelaten omdat onbekend is of ze niveau '{geo_niveau}' hebben: {ids[:_MAX_ONBEKEND]}. "
        "Controleer dat met dataset_details voordat je er een kiest."
    )


def search_catalog(
    query: str,
    source: str = "both",
    top_n: int = 15,
    geo_niveau: str | None = None,
) -> str:
    t0 = time.perf_counter()
    query_words = _woorden(query)
    # F1: Filter stopwoorden
    filtered_words = _filter_stopwoorden(query_words)
    hint = _volzin_hint(query, query_words, filtered_words)
    words = _expand_query(filtered_words)

    # De bron kiest de code, niet het model (#334): een instellingsvraag zoekt eerst in DUO en RIO,
    # waar instellingsdata staat, en valt pas daarna terug op CBS-benchmarkdata.
    instellingsvraag = source in ("cbs", "both") and instelling.noemt_instelling(query)
    active, archive = _verzamel(words, "rio" if instellingsvraag else source)
    if instellingsvraag and not (active or archive):
        active, archive = _verzamel(words, source)
    historisch = bool(_HISTORISCH & set(query_words))

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if not active and not archive:
        logger.warning(
            "search_catalog miss query=%r source=%s geo=%s elapsed_ms=%d", query, source, geo_niveau, elapsed_ms
        )
        # Een gemiste zoekopdracht las het model als "geen geschikte bron" (#168).
        return (
            f"Geen resultaten gevonden voor '{query}'. Dat zegt niet dat de data ontbreekt: probeer "
            "andere trefwoorden, of controleer een bekend dataset-ID met dataset_details."
        )

    # Archief is reserve, maar pas na de relevantiefilters: een actieve treffer die daarop
    # afvalt mag een passende archieftreffer niet blokkeren (#350). Een expliciet historische vraag gaat direct naar het archief.
    primair, reserve = (archive, active) if historisch else (active, archive)
    hits, onbekend = _gerangschikt(primair, geo_niveau)
    if not hits:
        hits, onbekend_reserve = _gerangschikt(reserve, geo_niveau)
        onbekend += onbekend_reserve

    if geo_niveau and not hits and onbekend:
        return f"Geen datasets gevonden voor '{query}' die zeker niveau '{geo_niveau}' hebben. " + _onbekende_dekking(
            onbekend, geo_niveau
        )
    if geo_niveau and not hits:
        logger.warning(
            "search_catalog miss query=%r source=%s geo=%s (geo filter) elapsed_ms=%d",
            query,
            source,
            geo_niveau,
            elapsed_ms,
        )
        return (
            f"Geen datasets gevonden voor '{query}' die het niveau "
            f"'{geo_niveau}' ondersteunen. Probeer een hoger aggregatieniveau "
            f"(bijv. 'provincie' in plaats van 'gemeente')."
        )

    top_ids = [_dataset_id(h) for h in hits[:3]]
    logger.info(
        "search_catalog query=%r source=%s geo=%s results=%d top=%s elapsed_ms=%d",
        query,
        source,
        geo_niveau,
        len(hits),
        top_ids,
        elapsed_ms,
    )

    lean = [{k: v for k, v in h.items() if not k.startswith("_") or k in _SEARCH_KEEP_FIELDS} for h in hits[:top_n]]
    if hint:
        lean.append({"melding": hint})
    if geo_niveau and onbekend:
        lean.append({"melding": _onbekende_dekking(onbekend, geo_niveau)})
    return json.dumps(lean, ensure_ascii=False, separators=(",", ":"))


_DETAILS_EXTRA = frozenset(
    {
        "_resources",
        "teldefinitie",
        "publicatieregels",
        "metadata_onbekend",
        "kolommen_steekproef",
        "catalogus_bron_gewijzigd",
        "kolomprofiel",
    }
)


def _build_details(entry: dict, dataset_id: str) -> str:
    details = {k: v for k, v in entry.items() if k in (_DETAIL_FIELDS | _DETAILS_EXTRA) and v}
    if details.get("_resources"):
        # De index is wat get_duo_data(dataset, resource) verwacht (#173).
        details["_resources"] = [{"index": i, **r} for i, r in enumerate(details["_resources"])]
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


def resources_met_kolom(dataset_id: str, kolom: str) -> list[tuple[int, str]]:
    """(index, naam) van de resources van een DUO-dataset waarvan de naam de kolom noemt (#173).

    Alleen namen, geen downloads: "OPLEIDINGSVORM" vindt "…inclusief opleidingsvorm…".
    """
    for entry in _rio_duo():
        if (entry.get("_ckan_id") or entry.get("_rio_resource")) == dataset_id:
            return [
                (i, r["naam"])
                for i, r in enumerate(entry.get("_resources") or [])
                if r.get("naam") and kolom.lower() in r["naam"].lower()
            ]
    return []


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
            if not _via_chat(entry):
                return json.dumps({"bron": entry.get("bron", dataset_id), **_NIET_OPVRAAGBAAR}, ensure_ascii=False)
            if entry.get("leverancier") == "DUO":
                from . import duo  # lazy: duo importeert catalog

                # Het moment waarop het model tussen bijv. p01 en p03 kiest (#172), en
                # vóór het filtert ziet wat er per kolom in zit (#362).
                entry = {
                    **entry,
                    **duo_meta.metadata(entry),
                    **duo_meta.kolomdekking(entry),
                    "kolomprofiel": duo.geladen_profielen(dataset_id),
                }
            return _build_details(entry, dataset_id)

    logger.warning("dataset_details miss id=%s", dataset_id)
    return f"Dataset '{dataset_id}' niet gevonden in de catalogus."
