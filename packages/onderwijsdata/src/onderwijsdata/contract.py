"""Versieerbaar, modelonafhankelijk datasetcontract voor catalogusrecords.

Volledig offline en zonder LLM/API-key. Onbekende informatie wordt expliciet als
``{"status": "unknown"}`` weergegeven en nooit als lege lijst met de betekenis
"onmogelijk". De bestaande ``catalog()`` blijft ongewijzigd.
"""
import hashlib
import json
from functools import lru_cache

SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = (1,)
SECTOREN = ("mbo", "hbo", "wo")

SUPPORTED, UNSUPPORTED, UNKNOWN = "supported", "unsupported", "unknown"
_STATUSSEN = {SUPPORTED, UNSUPPORTED, UNKNOWN}

# Wat de package zelf kan; de chat bepaalt zelf welke tools hij toelaat.
CAPABILITIES = {
    "properties": True,
    "dimension": True,
    "definitions": True,
    "data": True,
    "validate_selection": True,
}


class DatasetNietGevonden(KeyError):
    """Het opgegeven dataset-ID komt niet exact voor in de catalogus."""


class OnbekendSchema(ValueError):
    """De gevraagde schemaversie wordt niet ondersteund."""


def _onbekend(reden: str) -> dict:
    return {"status": UNKNOWN, "reden": reden}


def _bron_records() -> list[dict]:
    from . import catalog
    return catalog(ai=True)


def _scopeprofiel(onderwijstype: list[str]) -> dict[str, str]:
    """Sectorstatus voor mbo/hbo/wo op basis van de gecureerde `onderwijstype`.

    Een tabel met alleen mbo/hbo/wo-sectoren is `supported` voor de genoemde sectoren.
    Gemengde of brede tabellen (Allen, PO/VO erbij, leeg) zijn `unknown`: pas
    toelaten als het sectordeel aantoonbaar apart selecteerbaar is (zie CBS-02/04).
    """
    types = {t.lower() for t in onderwijstype}
    in_scope = types & set(SECTOREN)
    if not types or "allen" in types:
        return {s: UNKNOWN for s in SECTOREN}
    if not in_scope:
        return {s: UNSUPPORTED for s in SECTOREN}
    if types <= set(SECTOREN):
        return {s: SUPPORTED if s in types else UNSUPPORTED for s in SECTOREN}
    return {s: UNKNOWN if s in types else UNSUPPORTED for s in SECTOREN}


# Tabellen zonder regiodimensie die toch niet over (Europees) Nederland gaan.
_ANDER_GEBIED = {"caribisch": "Caribisch Nederland"}


def _geografie(rec: dict) -> dict:
    """Territoriale dekking (welk gebied) gescheiden van regionale uitsplitsing (welke niveaus).

    Een CBS-tabel zonder regiodimensie geeft cijfers voor heel Nederland: landelijk
    is dan ondersteund, alleen regionale uitsplitsing niet. Tabellen over een ander
    gebied (Caribisch Nederland) zijn niet landelijk. Onbekende dimensies blijven onbekend.
    """
    dims = rec.get("_dimensies") or []
    niveaus = rec.get("_geo_niveau") or []
    heeft_regio = any("regio" in d.lower() or "gemeente" in d.lower() for d in dims)
    if niveaus:
        return {"status": SUPPORTED, "niveaus": list(niveaus), "regionale_uitsplitsing": True}
    if heeft_regio:
        return {"status": UNKNOWN, "niveaus": None, "regionale_uitsplitsing": True,
                "reden": "regiodimensie aanwezig, niveaus niet vastgesteld"}
    if not dims:
        return {"status": UNKNOWN, "niveaus": None, "regionale_uitsplitsing": None,
                "reden": "dimensies niet vastgesteld"}
    titel = (rec.get("bron") or "").lower()
    for term, gebied in _ANDER_GEBIED.items():
        if term in titel:
            return {"status": UNSUPPORTED, "niveaus": [], "regionale_uitsplitsing": False,
                    "dekking": gebied, "reden": f"tabel beschrijft {gebied}, niet landelijk Nederland"}
    return {"status": SUPPORTED, "niveaus": ["landelijk"], "regionale_uitsplitsing": False,
            "dekking": "Nederland"}


def _dimensie_sleutels(rec: dict) -> dict:
    sleutels = rec.get("_dimensie_sleutels")
    if not sleutels:
        return _onbekend("dimensiesleutels niet vastgelegd; alleen live te bepalen")
    return {"status": SUPPORTED, "sleutels": dict(sleutels), "bron": "DataProperties"}


def _populatie(info: dict | None) -> dict:
    p = (info or {}).get("populatie")
    if not p:
        return _onbekend("populatie niet vastgelegd")
    if p["status"] != "gevonden":
        return _onbekend("populatie niet vermeld in TableInfos")
    return {"status": SUPPORTED, "passages": p["passages"], "bron": "TableInfos"}


def _teldefinitie(rec: dict, info: dict | None) -> dict:
    """Bronpassages van de definities die bij een meetwaarde horen (term in de titel)."""
    if not info:
        return _onbekend("teldefinitie niet vastgelegd")
    titels = " ".join((m.get("title") or "") for m in _meetwaarden(rec)).lower()
    passend = [d for d in info.get("definities", []) if d["term"].lower() in titels]
    if not passend:
        return _onbekend("geen definitie van de meetwaarde in TableInfos gevonden")
    return {"status": SUPPORTED, "definities": passend, "bron": "TableInfos"}


def _methodiek(info: dict | None) -> dict:
    """Afronding, additiviteit, definitiebreuken en publicatie: bronpassages, nooit AI."""
    if not info:
        return _onbekend("TableInfos niet vastgelegd")
    return {
        "status": SUPPORTED,
        "afronding": info["afronding"],
        "additiviteit": info["additiviteit"],
        "definitiebreuken": info["definitiebreuken"],
        "publicatie": info["publicatie"],
        "methoden": info["methoden"],
        "relaties": info["relaties"],
        "verklaring_symbolen": info["bronbewijs"].get("verklaring_symbolen"),
        "verificatie": info.get("verificatie", "bron"),
    }


def _perioden(rec: dict, info: dict | None = None) -> dict:
    waarden = rec.get("_periode_waarden") or []
    codes = _onbekend("periodecodes en hiaten niet vastgelegd")
    if info and info.get("perioden", {}).get("aantal"):
        p = info["perioden"]
        codes = {"status": SUPPORTED, "aantal": p["aantal"], "codes": p["codes"],
                 "hiaten": p["hiaten"] if p["hiaten"] is not None else "niet bepaald",
                 # 'verouderd': laatste Perioden-controle mislukte; codes zijn de laatst-goede.
                 "controle": p.get("status"), "gecontroleerd_op": p.get("gecontroleerd_op")}
    return {
        "status": SUPPORTED if rec.get("_perioden_formaat") else UNKNOWN,
        "formaat": list(rec.get("_perioden_formaat") or []),
        "frequentie": rec.get("frequentie"),
        "tekst": rec.get("periode"),
        "eerste": waarden[0] if waarden else None,
        "laatste": waarden[-1] if waarden else None,
        "codes": codes,
    }


def _meetwaarden(rec: dict) -> list[dict]:
    details = rec.get("_meetwaarden_details") or {}
    return [
        {
            "key": key,
            "title": details.get(key, {}).get("title"),
            "unit": details.get(key, {}).get("unit"),
            "datatype": details.get(key, {}).get("datatype"),
            "decimals": details.get(key, {}).get("decimals"),
        }
        for key in rec.get("_meetwaarden") or []
    ]


def _record(rec: dict, info: dict | None = None) -> dict:
    cbs_id = rec["_cbs_id"]
    verrijking = rec.get("_verrijking") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": f"cbs:{cbs_id}",
        "provider": "CBS",
        "titel": rec.get("bron"),
        "bron_url": (rec.get("documentatie") or {}).get("url"),
        "aliases": [cbs_id],
        "onderwijssectoren": list(rec.get("onderwijstype") or []),
        "scopeprofiel": _scopeprofiel(rec.get("onderwijstype") or []),
        "populatie": _populatie(info),
        "meetwaarden": _meetwaarden(rec),
        "teldefinitie": _teldefinitie(rec, info),
        "methodiek": _methodiek(info),
        "dimensies": list(rec.get("_dimensies") or []),
        "dimensie_sleutels": _dimensie_sleutels(rec),
        "geografie": _geografie(rec),
        "instellingseenheden": _onbekend("instellingseenheden niet vastgelegd"),
        "perioden": _perioden(rec, info),
        "archief": {
            "gearchiveerd": bool(rec.get("_archief")),
            "opvolger": _onbekend("opvolger niet vastgelegd"),
        },
        "herkomst": {
            "laatste_update": rec.get("_laatste_update"),
            "metadata_modified": (info or {}).get("bronmeta", {}).get("metadata_modified"),
            "gecontroleerd_op": (info or {}).get("bronmeta", {}).get("gecontroleerd_op"),
            "broncheck": (info or {}).get("bronmeta", {}).get("gecontroleerd_op"),
            "catalogusbouw": None,
            "verrijkingsversie": verrijking.get("versie"),
            "inputhash": verrijking.get("inputhash"),
            "afgeleide_velden": {
                "scopeprofiel": "afgeleid uit gecureerde onderwijstype",
                "geografie": "afgeleid uit CBS-regiodimensie; zonder regiodimensie = Nederland-totaal",
                "meetwaarden": "bron (DataProperties)",
            },
        },
        "capabilities": dict(CAPABILITIES),
    }


def _check_versie(schema_version: int) -> None:
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise OnbekendSchema(
            f"schema_version {schema_version!r} niet ondersteund; kies uit {SUPPORTED_SCHEMA_VERSIONS}"
        )


def _check_sector(sector: str | None) -> None:
    if sector is not None and sector.lower() not in SECTOREN:
        raise ValueError(f"onbekende sector {sector!r}; kies uit {SECTOREN}")


def _tableinfo() -> dict[str, dict]:
    """Methodiek/periodecontext uit officiële TableInfos (cbs_tableinfo.json); leeg als afwezig."""
    from importlib.resources import files
    pad = files("onderwijsdata.data").joinpath("cbs_tableinfo.json")
    try:
        return {r["_cbs_id"]: r for r in json.loads(pad.read_text(encoding="utf-8"))}
    except FileNotFoundError:
        return {}


@lru_cache(maxsize=1)
def _alle_records() -> tuple[dict, ...]:
    info = _tableinfo()
    return tuple(_record(r, info.get(r["_cbs_id"])) for r in _bron_records())


def catalog_records(schema_version: int = SCHEMA_VERSION, sector: str | None = None) -> list[dict]:
    """Records in het contract; met ``sector`` alleen die waar de sector `supported` is.

    Dit is een kandidaatselectie op tabelniveau: een HO-tabel voor hbo+wo staat
    erin, ook als de hbo-cijfers alleen via een dimensiefilter te scheiden zijn.
    Of een concrete selectie leverbaar is, bepalen ``validate_selection``/``prepare_query``.

    Records met onbekende dekking staan niet in een sectorselectie maar in
    :func:`scope_review`.
    """
    _check_versie(schema_version)
    _check_sector(sector)
    records = [json.loads(json.dumps(r)) for r in _alle_records()]
    if sector is None:
        return records
    return [r for r in records if r["scopeprofiel"][sector.lower()] == SUPPORTED]


def scope_review(sector: str | None = None) -> list[dict]:
    """Records waarvan de dekking voor (een van) de sectoren nog `unknown` is."""
    _check_sector(sector)
    sectoren = (sector.lower(),) if sector else SECTOREN
    return [
        r for r in catalog_records()
        if any(r["scopeprofiel"][s] == UNKNOWN for s in sectoren)
        and not any(r["scopeprofiel"][s] == SUPPORTED for s in sectoren)
    ]


def get_dataset(dataset_id: str, schema_version: int = SCHEMA_VERSION) -> dict:
    """Exacte ID-resolutie: ``cbs:85423NED`` of ``85423NED`` (hoofdletterongevoelig)."""
    _check_versie(schema_version)
    sleutel = dataset_id.strip()
    if sleutel.lower().startswith("cbs:"):
        sleutel = sleutel[4:]
    for r in _alle_records():
        if r["aliases"][0].lower() == sleutel.lower():
            return json.loads(json.dumps(r))
    raise DatasetNietGevonden(dataset_id)


@lru_cache(maxsize=1)
def _bouwmanifest() -> dict | None:
    """Manifest van het gepubliceerde artefact (cbs_manifest.json), of None als het ontbreekt."""
    from importlib.resources import files
    pad = files("onderwijsdata.data").joinpath("cbs_manifest.json")
    try:
        return json.loads(pad.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


@lru_cache(maxsize=1)
def _geleverde_hashes() -> dict[str, str]:
    from importlib.resources import files
    data_dir = files("onderwijsdata.data")
    hashes = {}
    for naam in (_bouwmanifest() or {}).get("bestanden", {}):
        hashes[naam] = hashlib.sha256(data_dir.joinpath(naam).read_bytes()).hexdigest()
    return hashes


def catalog_manifest() -> dict:
    """Welke catalogus gebruik ik werkelijk? Volledig offline, uit de geleverde bestanden.

    ``bouw`` is het manifest van het gepubliceerde artefact (revisie, aantallen,
    datadekking, bronwijziging, laatste succesvolle controle als aparte velden).
    ``consistent`` is waar als de geleverde bestanden exact bij dat manifest horen.
    """
    records = _alle_records()
    payload = json.dumps(records, sort_keys=True, ensure_ascii=False).encode("utf-8")
    bouw = _bouwmanifest()
    consistent = bool(bouw) and all(
        _geleverde_hashes().get(naam) == b["sha256"] for naam, b in bouw["bestanden"].items()
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "inhoudshash": hashlib.sha256(payload).hexdigest()[:16],
        "catalogusrevisie": bouw["catalogusrevisie"] if bouw else None,
        "aantal": len(records),
        "aantal_per_sector": {
            s: sum(1 for r in records if r["scopeprofiel"][s] == SUPPORTED) for s in SECTOREN
        },
        "aantal_review": len(scope_review()),
        "capabilities": dict(CAPABILITIES),
        "bouw": bouw,
        "consistent": consistent,
    }


def valideer_record(record: dict) -> list[str]:
    """Controleer een record tegen schema v1; retourneert foutmeldingen (leeg = geldig)."""
    fouten: list[str] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        fouten.append("schema_version onjuist")
    for veld in ("dataset_id", "provider", "titel", "bron_url"):
        if not isinstance(record.get(veld), str) or not record.get(veld):
            fouten.append(f"{veld}: verplichte tekst ontbreekt")
    if not str(record.get("dataset_id", "")).startswith("cbs:"):
        fouten.append("dataset_id moet met 'cbs:' beginnen")
    if not isinstance(record.get("aliases"), list) or not record["aliases"]:
        fouten.append("aliases ontbreken")
    profiel = record.get("scopeprofiel")
    if not isinstance(profiel, dict) or set(profiel) != set(SECTOREN) or not set(profiel.values()) <= _STATUSSEN:
        fouten.append("scopeprofiel ongeldig")
    geo = record.get("geografie") or {}
    if geo.get("status") not in _STATUSSEN:
        fouten.append("geografie.status ongeldig")
    if geo.get("status") == UNKNOWN and geo.get("niveaus") == []:
        fouten.append("geografie: onbekend mag niet als lege lijst")
    for veld in ("populatie", "teldefinitie", "instellingseenheden"):
        if not isinstance(record.get(veld), dict) or "status" not in record[veld]:
            fouten.append(f"{veld}: status ontbreekt")
    for m in record.get("meetwaarden") or []:
        if not m.get("key") or m.get("title") is None:
            fouten.append(f"meetwaarde zonder key/title: {m!r}")
    return fouten


def dimensie_sleutel(dataset_id: str, dimensie: str) -> str | None:
    """Officiële key van een dimensie (opgegeven als key of titel); live, via gecachete definities."""
    rec = get_dataset(dataset_id)
    return _dimensie_sleutel(rec["aliases"][0], dimensie)


def _dimensie_sleutel(cbs_id: str, dimensie: str) -> str | None:
    from . import client
    for key, d in client.definitions(cbs_id).items():
        if d.get("type", "").endswith("Dimension") and dimensie in (key, d.get("title")):
            return key
    return None


def dimensie_waarden(dataset_id: str, dimensie: str) -> dict[str, str]:
    """Waarden van één dimensie (key → titel); live opgehaald en gecachet.

    ``dimensie`` mag de key of de titel zijn.
    """
    rec = get_dataset(dataset_id)
    return _dimensie_cache(rec["aliases"][0], dimensie)


@lru_cache(maxsize=256)
def _dimensie_cache(cbs_id: str, dimensie: str) -> dict[str, str]:
    from . import client
    return client.dimension(cbs_id, _dimensie_sleutel(cbs_id, dimensie) or dimensie)
