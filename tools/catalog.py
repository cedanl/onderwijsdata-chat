import hashlib
import json
import logging
import math
import re
import time
from functools import cache

from onderwijsdata import catalog as _cbs_catalog
from riodata import catalog as _rio_catalog

from . import cbs_meta, duo_correcties, duo_meta, instelling, scopeprofiel
from .definitie import met_voorbeeldstatus
from .schemas import TOOL_GET_ROA_BENCHMARK, TOOL_GET_UWV_VACATURES

logger = logging.getLogger(__name__)

# Leveranciers waarvoor we search_catalog actief steunen.
# "Inspectie van het Onderwijs" (2 datasets) en "SBB" (2 datasets) staan wel in de ruwe
# catalogus maar hebben geen bruikbare machineleesbare resources — hun structuur is niet
# geschikt voor de query-interfaces (search_catalog, get_*_data). Deze filtered-out state
# is intentioneel: README mag ze niet noemen, want zij zijn niet bereikbaar voor gebruikers.
SUPPORTED_LEVERANCIERS = frozenset({"RIO", "DUO", "ROA", "UWV"})

# Bronnen waarvan de chat data kan ophalen (get_cbs_data, get_duo_data, get_rio_data).
# ROA en UWV staan wel in de catalogus; zonder datatool mag het model er geen cijfers
# voor geven, en ook niet concluderen dat ze niet bestaan (#200). Twee ervan hebben
# een eigen tool (#441).
CHAT_BRONNEN = ("CBS", "DUO", "RIO")
_EIGEN_TOOL = {"uwv-open-match-data": TOOL_GET_UWV_VACATURES, "ais2030": TOOL_GET_ROA_BENCHMARK}
_NIET_OPVRAAGBAAR = {
    "opvraagbaar": False,
    "melding": (
        "Deze bron staat in de catalogus, maar is in de chat niet op te vragen: er is geen "
        "datatool voor. Noem de dataset, geef er geen cijfers voor, en zeg niet dat de bron niet bestaat."
    ),
}


# Formaten die riodata.duo.load als tabel leest. Een DUO-changelog is alleen een PDF (#408).
_TABELFORMATEN = frozenset({"CSV", "XLSX", "XLS"})
_ALLEEN_DOCUMENTATIE = {
    "opvraagbaar": False,
    "melding": (
        "Deze dataset bevat alleen documentatie (bijv. een PDF-changelog) en geen tabel: er zijn "
        "geen cijfers uit op te halen. Zoek de dataset met de data zelf."
    ),
}


def _via_chat(entry: dict) -> bool:
    return str(entry.get("leverancier", "")).upper() in CHAT_BRONNEN


def _is_tabel(resource: dict) -> bool:
    """Zonder opgegeven formaat beslist riodata bij het laden; alleen een bekend ander formaat valt af."""
    return not resource.get("format") or str(resource["format"]).upper() in _TABELFORMATEN


def _tabelbestanden(entry: dict) -> list[tuple[int, str]]:
    return [(i, r.get("naam") or "") for i, r in enumerate(entry.get("_resources") or []) if _is_tabel(r)]


def _niet_opvraagbaar(entry: dict) -> dict | None:
    """Waarom de chat geen data voor deze catalogusregel kan ophalen; None als het wel kan."""
    if tool := _EIGEN_TOOL.get(scopeprofiel.dataset_id(entry) or ""):
        return {
            "via_tool": tool,
            "melding": f"Op te vragen met {tool}; get_*_data, query_data en run_analysis werken hier niet op.",
        }
    if not _via_chat(entry):
        return _NIET_OPVRAAGBAAR
    if entry.get("_resources") and not _tabelbestanden(entry):
        return _ALLEEN_DOCUMENTATIE
    return None


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
def _cbs_alles() -> list:
    return _cbs_catalog()


@cache
def _cbs() -> list:
    """De CBS-tabellen binnen het chatprofiel mbo/hbo/wo: dezelfde regel als DUO (#355, CH-03)."""
    return [e for e in _cbs_alles() if scopeprofiel.in_scope(e)]


@cache
def _rio_duo_alles() -> list:
    return _rio_catalog(source="all")


@cache
def _rio_duo() -> list:
    """De RIO/DUO-records binnen het chatprofiel mbo/hbo/wo (#355, #375).

    Zoeken, details, telling en laden volgen deze lijst; tools/scopeprofiel.py beslist. De
    records dragen de correcties op DUO's kolombeschrijvingen (#451).
    """
    return [duo_correcties.catalogusrecord(e) for e in _rio_duo_alles() if scopeprofiel.in_scope(e)]


def _ruw_record(dataset_id: str) -> dict | None:
    """Het record uit de volledige CBS- en riodata-inventaris, ook als het buiten het profiel valt."""
    return next((e for e in [*_cbs_alles(), *_rio_duo_alles()] if scopeprofiel.dataset_id(e) == dataset_id), None)


def scope_blokkade(dataset_id: str) -> str | None:
    """Waarom een datatool `dataset_id` niet laadt; None als het binnen het profiel valt.

    Een directe ID uit de vraag of van het model omzeilt de grens niet (#355), ook niet
    bij een herstelpoging met een andere tabel (CH-03).
    """
    binnen = [*_cbs(), *_rio_duo()]
    if any(scopeprofiel.dataset_id(e) == dataset_id for e in binnen):
        return None
    if bekend := _ruw_record(dataset_id):
        logger.info("scope_blokkade id=%s buiten profiel", dataset_id)
        return json.dumps(scopeprofiel.buiten_scope_voor(bekend), ensure_ascii=False)
    logger.warning("scope_blokkade id=%s niet in de catalogus", dataset_id)
    ids = [i for e in binnen if (i := scopeprofiel.dataset_id(e)) and dataset_id.lower() in i.lower()]
    hint = f" Vergelijkbare datasets: {ids[:3]}." if ids else " Zoek de juiste dataset-ID met search_catalog."
    return f"Dataset '{dataset_id}' staat niet in de catalogus; zonder scopebesluit laadt de chat hem niet.{hint}"


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


def _is_volzin(query: str, woorden: list[str]) -> bool:
    return len(woorden) >= _VOLZIN_MIN_WOORDEN or query.rstrip().endswith("?")


def _volzin_hint(query: str, woorden: list[str], trefwoorden: list[str]) -> str | None:
    """Een volzin of vraag wordt als trefwoorden gezocht; zeg dat, zodat het model het afleert (#17)."""
    if not _is_volzin(query, woorden) or trefwoorden == woorden:
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


_REGISTERS = frozenset({"DUO", "RIO"})
# Een treffer is pas kandidaat als hij minstens één gebruikersterm raakt en, bij trefwoorden, dit deel (#351).
_MIN_AANDEEL_TERMEN = 0.5


def _geraakte_termen(entry: dict, termen: list[str]) -> set[str]:
    """De door de gebruiker genoemde termen die de treffer raakt; een synoniem is geen bewijs (#351)."""
    return {term for term in termen if _score(entry, [(term, 1.0)])}


def geodekking(entry: dict, niveau: str) -> str:
    """Biedt de dataset dit geografische niveau: "ja", "nee" of "onbekend" (#351).

    Een lege `_geo_niveau` is alleen landelijk (#237) als de catalogus de structuur
    kent: CBS-dimensies of DUO/RIO-kolommen zonder regio. Ontbreekt het veld of de
    structuur, dan heeft niemand gekeken; dat is onbekend, niet landelijk.

    Een instellingskolom (INSTELLINGSCODE) is geen geo-niveau: de instellingseenheid maakt
    een register niet regionaal of landelijk. Een DUO/RIO-register met regiokolom telt
    misschien op tot landelijk, maar zonder bewijs is dat onbekend, niet "ja" (testaudit L2).
    """
    niveaus = entry.get("_geo_niveau")
    if niveaus:
        if niveau in niveaus:
            return "ja"
        register = str(entry.get("leverancier", "")).upper() in _REGISTERS
        return "onbekend" if register and niveau == "landelijk" else "nee"
    if niveaus is None or not (entry.get("_dimensies") or entry.get("_kolommen")):
        return "onbekend"
    return "ja" if niveau == "landelijk" else "nee"


def _verzamel(
    words: list[tuple[str, float]], source: str, termen: list[str], aandeel: float
) -> tuple[list, list, list]:
    """De scorende treffers uit `source`: actief, archief, en te zwak voor de drempel (#351)."""
    treffers: list = []

    if source in ("cbs", "both"):
        treffers += [(s, entry, {"bron": "CBS", **entry}) for entry in _cbs() if (s := _score(entry, words))]

    if source in ("rio", "both", "duo"):
        for entry in _rio_duo():
            if str(entry.get("leverancier", "")).upper() not in SUPPORTED_LEVERANCIERS:
                continue
            is_duo = str(entry.get("leverancier", "")).upper() == "DUO"
            if source == "duo" and not is_duo:
                continue
            if s := _score(entry, words):
                treffers.append((s, entry, {**entry, **(_niet_opvraagbaar(entry) or {})}))

    # Een term die geen treffer kent (bijv. een instellingsnaam) onderscheidt niets en telt niet mee.
    geraakt = [_geraakte_termen(entry, termen) for _, entry, _ in treffers]
    nodig = max(1, math.ceil(len(set().union(*geraakt)) * aandeel))
    active: list = []
    archive: list = []
    zwak: list = []
    for (s, entry, hit), raak in zip(treffers, geraakt, strict=True):
        (zwak if len(raak) < nodig else archive if entry.get("_archief") else active).append((s, hit))
    return active, archive, zwak


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


_MAX_SUGGESTIES = 3


def _no_match(query: str, zwak: list) -> str:
    """Geen geschikte kandidaat na de drempel (#351); een miss las het model als "geen bron" (#168)."""
    melding = (
        f"no_match: Geen resultaten gevonden voor '{query}'. Dat zegt niet dat de data ontbreekt: probeer "
        "andere trefwoorden, of controleer een bekend dataset-ID met dataset_details."
    )
    ids = [i for i in map(_dataset_id, _gerangschikt(zwak, None)[0]) if i != "?"][:_MAX_SUGGESTIES]
    if not ids:
        return melding
    return (
        f"{melding} needs_clarification: deze datasets raken te weinig zoektermen en zijn geen keuze, "
        f"alleen een suggestie: {ids}. Vraag de gebruiker om verduidelijking voordat je er een laadt."
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
    # In een volzin zijn niet alle woorden criteria: daar volstaat één geraakte gebruikersterm (#351).
    aandeel = 0.0 if _is_volzin(query, query_words) else _MIN_AANDEEL_TERMEN
    words = _expand_query(filtered_words)

    # De bron kiest de code, niet het model (#334): een instellingsvraag zoekt eerst in DUO en RIO,
    # waar instellingsdata staat, en valt pas daarna terug op CBS-benchmarkdata.
    instellingsvraag = source in ("cbs", "both") and instelling.noemt_instelling(query)
    active, archive, zwak = _verzamel(words, "rio" if instellingsvraag else source, filtered_words, aandeel)
    if instellingsvraag and not (active or archive):
        active, archive, zwak = _verzamel(words, source, filtered_words, aandeel)
    historisch = bool(_HISTORISCH & set(query_words))

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if not active and not archive:
        logger.warning(
            "search_catalog miss query=%r source=%s geo=%s elapsed_ms=%d", query, source, geo_niveau, elapsed_ms
        )
        return _no_match(query, zwak)

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
        "teldefinitie_niet_gebruikt",
        "publicatieregels",
        "metadata_onbekend",
        "kolommen_steekproef",
        "catalogus_bron_gewijzigd",
        "kolomprofiel",
        "methodiek",
        "niet_geschikt_voor",
    }
)


# DUO-details blijven onder het toolbudget van de agent (agent/run.py): de hele steekproef
# duwde de kolommen van latere bestanden erbuiten (#395). Voorbeeldwaarden per kolom worden
# stapsgewijs minder, tot het past; drie laten de codering nog zien.
_DETAILS_BUDGET = 11_000
_VOORBEELDEN = (10, 5, 3)


def _per_resource(entry: dict, veld: str) -> dict[str, dict] | None:
    """Het veld per resourcenaam, als de catalogus het zo indeelt; anders None."""
    waarde = entry.get(veld)
    namen = {r.get("naam") for r in entry.get("_resources") or []}
    per_naam = isinstance(waarde, dict) and waarde and set(waarde) <= namen
    return waarde if per_naam and all(isinstance(v, dict) for v in waarde.values()) else None


def _resource_kolommen(entry: dict) -> dict[str, list[str]]:
    """Kolomnamen per resourcenaam uit de catalogus; leeg als die niet per bestand is ingedeeld."""
    per = _per_resource(entry, "_kolomtypes") or _per_resource(entry, "_kolommen") or {}
    return {naam: list(kolommen) for naam, kolommen in per.items()}


def _ingekort(kolommen, maximum: int):
    """Voorbeeldlijsten van ten hoogste `maximum` waarden, met het aantal dat weg is."""
    if isinstance(kolommen, dict):
        return {k: _ingekort(v, maximum) for k, v in kolommen.items()}
    if isinstance(kolommen, list) and len(kolommen) > maximum:
        weg = len(kolommen) - maximum + 1
        return [*kolommen[: maximum - 1], f"… (+{weg} meer in de steekproef)"]
    return kolommen


def _duo_details(entry: dict, dataset_id: str) -> str:
    """_build_details met zo veel voorbeeldwaarden als binnen _DETAILS_BUDGET past."""
    for maximum in _VOORBEELDEN:
        tekst = _build_details({**entry, "_kolommen": _ingekort(entry.get("_kolommen"), maximum)}, dataset_id)
        if len(tekst) <= _DETAILS_BUDGET:
            break
    return tekst


def _build_details(entry: dict, dataset_id: str) -> str:
    details = {k: v for k, v in entry.items() if k in (_DETAIL_FIELDS | _DETAILS_EXTRA) and v}
    if defs := details.get("_kolomdefinities"):
        # Voorbeelden in de glossary zijn geen gesloten lijst (#430).
        details["_kolomdefinities"] = {k: met_voorbeeldstatus(v) for k, v in defs.items()}
    if details.get("_resources"):
        # De index is wat get_duo_data(dataset, resource) verwacht (#173); de kolomnamen per
        # bestand staan vóór de voorbeeldlijsten, zodat het model het juiste bestand kiest. De
        # download-url laadt het model nooit zelf en kostte bij veel bestanden het budget (#395).
        kolommen = _resource_kolommen(entry)
        details["_resources"] = [
            {
                "index": i,
                **{k: v for k, v in r.items() if k != "url"},
                **({"kolommen": kolommen[r["naam"]]} if r.get("naam") in kolommen else {}),
            }
            for i, r in enumerate(details["_resources"])
        ]
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


def genoemde_datasets(tekst: str) -> list[str]:
    """Dataset-ID's uit de catalogus die letterlijk in de tekst staan, zoals in een vraag (#396)."""
    ids = {_dataset_id(e) for e in [*_cbs(), *_rio_duo()]} - {"?"}
    return [i for i in sorted(ids) if re.search(rf"(?<![\w-]){re.escape(i)}(?![\w-])", tekst, re.IGNORECASE)]


def leverancier(dataset_id: str) -> str | None:
    """De bron van een catalogus-ID ("CBS", "DUO", "RIO", ...); None als de catalogus het ID niet kent."""
    if any(e.get("_cbs_id") == dataset_id for e in _cbs()):
        return "CBS"
    entry = next((e for e in _rio_duo() if _dataset_id(e) == dataset_id), {})
    return str(entry.get("leverancier", "")).upper() or None


def catalogus_titel(dataset_id: str) -> str:
    """Menselijke titel (bron-veld) uit de catalogus voor een dataset-ID.

    Zoekt in de CBS- én de RIO/DUO-catalogus. Valt terug op de dataset-ID zelf
    als de dataset niet (meer) in de catalogus staat.
    """
    for entry in _cbs():
        if entry.get("_cbs_id") == dataset_id:
            return entry.get("bron") or dataset_id
    for entry in _rio_duo():
        if scopeprofiel.dataset_id(entry) == dataset_id:
            return entry.get("bron") or dataset_id
    return dataset_id


def bron_titel(dataset_id: str) -> str:
    """De titel in een bronregel: de catalogustitel met het deel dat de chat laadt (CH-45).
    Net als catalogus_titel het kale ID als de catalogus de dataset niet kent."""
    titel = catalogus_titel(dataset_id)
    deel = scopeprofiel.cbs_sectordeel(dataset_id)
    return f"{titel}, {deel}" if deel and titel != dataset_id else titel


def bron_naam(dataset_id: str) -> str:
    """'85368NED (<titel>, alleen mbo)'; het kale ID als de catalogus de dataset niet kent."""
    titel = bron_titel(dataset_id)
    return dataset_id if titel == dataset_id else f"{dataset_id} ({titel})"


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


def _duo_entry(dataset_id: str) -> dict:
    return next((e for e in _rio_duo() if e.get("_ckan_id") == dataset_id), {})


def tabelbestanden(dataset_id: str) -> list[tuple[int, str]]:
    """(index, naam) van de bestanden van een DUO-dataset die als tabel te laden zijn (#408).

    Uit de catalogus, zonder download; leeg als de catalogus de bestanden niet kent.
    """
    return _tabelbestanden(_duo_entry(dataset_id))


def is_documentbestand(dataset_id: str, resource: int) -> bool:
    """De catalogus kent dit bestand als iets anders dan een tabel, bijv. een PDF-changelog (#408).

    Een index die de catalogus niet kent, beoordeelt riodata bij het laden: de catalogus
    kan achterlopen op de bron.
    """
    bestanden = _duo_entry(dataset_id).get("_resources") or []
    return 0 <= resource < len(bestanden) and not _is_tabel(bestanden[resource])


def resources_met_kolom(dataset_id: str, kolom: str) -> list[tuple[int, str]]:
    """(index, naam) van de resources van een DUO-dataset die de kolom hebben of noemen.

    Geen downloads: de kolomlijst per bestand uit de catalogus (#395), of de naam
    (#173): "OPLEIDINGSVORM" vindt "…inclusief opleidingsvorm…".
    """
    for entry in _rio_duo():
        if (entry.get("_ckan_id") or entry.get("_rio_resource")) == dataset_id:
            kolommen = {naam: {k.lower() for k in ks} for naam, ks in _resource_kolommen(entry).items()}
            return [
                (i, r["naam"])
                for i, r in enumerate(entry.get("_resources") or [])
                if r.get("naam")
                and (kolom.lower() in r["naam"].lower() or kolom.lower() in kolommen.get(r["naam"], set()))
            ]
    return []


def dataset_details(dataset_id: str) -> str:
    """Geef gedetailleerde kolominformatie voor één dataset."""
    for entry in _cbs():
        if entry.get("_cbs_id") == dataset_id:
            logger.info("dataset_details id=%s bron=CBS", dataset_id)
            # Afronding en dubbeltelling vóór het model optelt of verklaart (#383).
            return _build_details({"bron": "CBS", **entry, **cbs_meta.metadata(dataset_id)}, dataset_id)

    for entry in _rio_duo():
        eid = entry.get("_ckan_id") or entry.get("_rio_resource")
        if eid == dataset_id:
            logger.info("dataset_details id=%s bron=%s", dataset_id, entry.get("leverancier", "RIO"))
            if reden := _niet_opvraagbaar(entry):
                return json.dumps({"bron": entry.get("bron", dataset_id), **reden}, ensure_ascii=False)
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
                return _duo_details(entry, dataset_id)
            return _build_details(entry, dataset_id)

    if buiten := _ruw_record(dataset_id):
        # Bekend maar buiten het profiel: zeg waarom, anders leest het model 'bestaat niet' (#355, #396).
        return json.dumps(scopeprofiel.buiten_scope_voor(buiten), ensure_ascii=False)
    logger.warning("dataset_details miss id=%s", dataset_id)
    return f"Dataset '{dataset_id}' niet gevonden in de catalogus."
