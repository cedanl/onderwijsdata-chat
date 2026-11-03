"""Versieerbaar, modelonafhankelijk datasetcontract voor alle zes bronnen (RIO-03).

Afgestemd op ``onderwijsdata.contract`` (CBS-03): dezelfde functienamen
(``catalog_records``, ``get_dataset``, ``catalog_manifest``, ``scope_review``,
``valideer_record``), dezelfde statussen en dezelfde ``scopeprofiel``-vorm. Daarnaast
``get_resource`` voor resources met een stabiele ID.

Volledig offline. Onbekende informatie is expliciet ``{"status": "unknown"}``, nooit een
lege lijst met de betekenis "onmogelijk". ``riodata.catalog()`` blijft ongewijzigd.

IDs:

- dataset: ``<provider>:<bron-ID>``, bijv. ``duo:p01hoinges``, ``rio:onderwijslocaties``,
  ``roa:ais2030``, ``uwv:uwv-open-match-data``, ``sbb:crebolijst``, ``inspectie:oordelen``.
  De bron-ID zonder voorvoegsel blijft als alias bruikbaar.
- resource: de officiële ID van de bron als die er is (CKAN-UUID, Dataverse file-ID,
  SBB output-ID), anders een beheerde semantische ID (``id_soort`` zegt welke). Positie in
  een lijst is nooit de ID.

Sectoren: ``scopeprofiel`` geeft per mbo/hbo/wo ``supported``/``unsupported``/``unknown``.
``supported`` met ``sectorselectie[sector].verplicht`` betekent: alleen met die
filter/resourcekeuze. ``ho_breed`` staat apart: HO-breed is niet hetzelfde als hbo of wo.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache

from .duo_notes import zoekkaart_tijd

SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = (1,)
SECTOREN = ("mbo", "hbo", "wo")
PROVIDERS = ("rio", "duo", "roa", "uwv", "inspectie", "sbb")

SUPPORTED, UNSUPPORTED, UNKNOWN = "supported", "unsupported", "unknown"
_STATUSSEN = {SUPPORTED, UNSUPPORTED, UNKNOWN}

# Wat de package per bron kan; de chat bepaalt zelf wat hij opvraagbaar maakt.
_CAPABILITIES = {
    "rio": ["api_read"],
    "duo": ["tabular_read"],
    "roa": ["tabular_read"],
    "uwv": ["tabular_read"],
    "inspectie": ["tabular_read"],
    "sbb": ["tabular_read"],
}

# Kolomnamen die als koppelsleutel bekend zijn (prefix-match, hoofdletterongevoelig).
_JOIN_SLEUTELS = (
    ("INSTELLINGSCODE", "brin"),
    ("BRIN", "brin"),
    ("CREBO", "crebo"),
    ("CROHO", "croho"),
    ("OPLEIDINGSCODE", "opleidingscode (crebo of croho)"),
    ("GEMEENTENUMMER", "cbs_gemeentecode"),
    ("GEMEENTECODE", "cbs_gemeentecode"),
)
# ID-formaat per RIO-resource. De v2-spec legde ze vast in het pad-parameter ``id`` van
# ``/{resource}/{id}``; de v3-spec (RIO_LOD_API_v3.yml) noemt geen formaten meer, maar de API
# valideert ze nog wel (GGM-003) en de records dragen ze (test_rio_id_formaten_gelijk_aan_de_spec,
# tests/test_rio_live.py). Alleen drie zijn een UUID; een opleidings-ID als
# '1002O5001-SBB-MIDDENKADEROPLEIDING' is opaak.
_RIO_ID_FORMATEN = {
    "aangeboden-opleidingen": "uuid",
    "examenlicenties": "uuid",
    "onderwijslicenties": "uuid",
    "organisatorische-eenheden": r"\d{3}[A-Z]{1}\d{3}",
    "onderwijslocaties": r"\d{3}X\d{3}",
}
_PERIODEKOLOMMEN = ("STUDIEJAAR", "SCHOOLJAAR", "JAAR", "PEILJAAR", "EXAMENJAAR", "PROGNOSEJAAR")
_HBO = re.compile(r"\bhoger beroepsonderwijs\b|\bhbo\b", re.I)
_WO = re.compile(r"\bwetenschappelijk onderwijs\b|\bwo\b", re.I)


class DatasetNietGevonden(KeyError):
    """Het opgegeven dataset-ID komt niet voor in de catalogus."""


class AmbigueDataset(ValueError):
    """Een ID zonder voorvoegsel past bij meer dan één bron; ``opties`` noemt ze."""

    def __init__(self, bericht: str, opties: list[str]):
        super().__init__(bericht)
        self.opties = opties


class OnbekendSchema(ValueError):
    """De gevraagde schemaversie wordt niet ondersteund."""


def _onbekend(reden: str, **extra) -> dict:
    return {"status": UNKNOWN, "reden": reden, **extra}


# ── bronrecords ───────────────────────────────────────────────────────────────

def _bron_id(rec: dict) -> tuple[str, str]:
    lev = (rec.get("leverancier") or "").lower()
    if lev == "rio":
        return "rio", rec["_rio_resource"]
    if lev == "duo":
        return "duo", rec["_ckan_id"]
    if lev == "roa":
        return "roa", rec["_roa_id"]
    if lev == "uwv":
        return "uwv", rec.get("_uwv_id") or rec["_ckan_id"]
    if lev.startswith("inspectie"):
        return "inspectie", rec["_inspectie_id"]
    if lev == "sbb":
        return "sbb", rec["_sbb_id"]
    raise ValueError(f"onbekende leverancier {rec.get('leverancier')!r}")


def _types(rec: dict) -> set[str]:
    return {str(t).lower() for t in (rec.get("onderwijstype") or [])}


_BVE = "Beroepsonderwijs_en_volwasseneneducatie_bve"
_ANDERE_SECTOREN = re.compile(r"\b(po|vo|so|vavo|nfo|ho|hbo|wo|basisonderwijs|voortgezet)\b", re.I)


def _duo_types(rec: dict, snapshot: dict | None) -> tuple[set[str], str]:
    """Sector van een DUO-dataset en het bewijs ervoor.

    Zonder CKAN-groep valt de catalogus terug op ``Allen``. Het DCAT-thema bve plus een
    titel die alleen mbo noemt is wél bronbewijs voor mbo; verder wordt niets geraden.
    """
    types = _types(rec)
    if types and "allen" not in types:
        return types, "CKAN-groep"
    snap = snapshot or {}
    titel = snap.get("titel") or rec.get("bron") or ""
    if (any(t.endswith(_BVE) for t in snap.get("dcat_themas", []))
            and re.search(r"\bmbo\b", titel, re.I) and not _ANDERE_SECTOREN.search(titel)):
        return {"mbo"}, "DCAT-thema bve en titel"
    themas = snap.get("dcat_themas", [])
    if themas and all(re.search(r"Voortgezet_onderwijs|Primair_onderwijs|Basisonderwijs", t) for t in themas):
        return {"vo"}, "DCAT-thema po/vo"
    return types, "catalogus (onderwijstype)"


def _rijselectie(schema: dict | None) -> dict:
    """hbo/wo-rijfilter uit een volledig gescande kolom met precies die waarden."""
    w = (schema or {}).get("waarden") or {}
    if not w.get("volledig"):
        return {}
    for kolom, info in w["kolommen"].items():
        domein = info.get("domein") or []
        laag = {str(x).lower(): x for x in domein}
        if domein and set(laag) == {"hbo", "wo"}:
            return {s: {"soort": "rijen", "kolom": kolom, "waarde": laag[s], "bron": "volledige scan"}
                    for s in ("hbo", "wo")}
    return {}


# ── resources ────────────────────────────────────────────────────────────────

def _duo_resource_sector(naam: str, types: set[str]) -> str | None:
    """Sector van één DUO-resource: uit de datasetsector, of hbo/wo uit de resourcenaam."""
    if types == {"mbo"}:
        return "mbo"
    if types == {"ho"}:
        hbo, wo = bool(_HBO.search(naam)), bool(_WO.search(naam))
        if hbo != wo:
            return "hbo" if hbo else "wo"
        return "ho"
    return None


def _schema_samenvatting(schema: dict | None) -> dict:
    if not schema:
        return _onbekend("geen schema in de snapshot")
    insp = schema["inspectie"]
    if insp["status"] != "ok":
        return {"status": UNKNOWN, "inspectie": insp["status"], "reden": insp.get("fout") or insp["status"]}
    return {
        "status": SUPPORTED,
        "inspectie": "ok",
        "aantal_kolommen": len(schema["kolommen"]),
        "kolommen": [k["naam"] for k in schema["kolommen"]],
        "schema_sha256": schema["schema_sha256"],
        "waarden": (schema.get("waarden") or {}).get("methode"),
        "bron": "CKAN Datastore" if schema["datastore_actief"] else "CSV-kop",
    }


def _duo_resources(rec: dict) -> list[dict]:
    from .duo import _schema_snapshot
    snapshot = _schema_snapshot()["datasets"].get(rec["_ckan_id"])
    types, _ = _duo_types(rec, snapshot)
    if snapshot:
        bronlijst = [(r["resource_id"], r["naam"], r["format"], r) for r in snapshot["resources"]]
    else:
        bronlijst = [(r["id"], r["naam"], r.get("format", ""), None) for r in rec.get("_resources") or []]
    uit = []
    for rid, naam, fmt, schema in bronlijst:
        tabel = fmt.upper() == "CSV"
        sector = _duo_resource_sector(naam, types)
        uit.append({
            "resource_id": rid,
            "id_soort": "ckan_uuid",
            "naam": naam,
            "format": fmt.upper(),
            "sector": sector,
            **({"rijselectie": rij} if sector == "ho" and (rij := _rijselectie(schema)) else {}),
            "capabilities": ["tabular_read"] if tabel else ["metadata_only"],
            "schema": _schema_samenvatting(schema) if tabel else {"status": UNSUPPORTED, "reden": "geen tabel"},
        })
    return uit


def _overige_resources(provider: str, rec: dict) -> list[dict]:
    if provider == "rio":
        return [{
            "resource_id": rec["_rio_resource"], "id_soort": "rio_api_resource", "naam": rec.get("bron"),
            "format": "JSON (API)", "sector": None, "capabilities": ["api_read"],
            "schema": _onbekend("live API; zie riodata.filtercontract() voor filters"),
        }]
    if provider == "uwv":
        us = rec.get("_schema")
        schema = ({"status": SUPPORTED, "kolommen": us["kolommen"], "aantal_kolommen": len(us["kolommen"]),
                   "rec_types": {k: {"opleidingsniveau": v["opleidingsniveau"],
                                     "kolommen_altijd_leeg": v["kolommen_altijd_leeg"]}
                                 for k, v in us["rec_types"].items()},
                   "laatste_peildatum": us["laatste_peildatum"], "bron": "inhoudelijke validatie (RIO-06)"}
                  if us else _onbekend("schema niet vastgelegd; uwv.load() controleert basisvorm"))
        return [{
            "resource_id": "snapshot", "id_soort": "semantisch",
            "naam": "Historische snapshot (uwv.resources() voor de beschikbare peildata)",
            "format": "ZIP/CSV", "sector": None, "capabilities": ["tabular_read"],
            "schema": schema,
        }]
    uit = []
    for r in rec.get("_resources") or []:
        fmt = (r.get("format") or ("CSV" if provider == "roa" else "")).upper()
        if provider == "roa":
            rid, soort = str(r["file_id"]), "dataverse_file_id"
        elif provider == "sbb":
            rid, soort = str(r["output_id"]), "sbb_output_id"
        else:
            rid, soort = r["naam"], "semantisch"
        cap = ["xml_download"] if fmt == "XML" else ["tabular_read"]
        rs = r.get("schema")
        schema = ({"status": SUPPORTED, "kolommen": rs["kolommen"], "aantal_kolommen": len(rs["kolommen"]),
                   **{k: rs.get(k) for k in ("editie", "meest_recente_editie", "granulariteit", "dataverse_sha1")},
                   "bron": "inhoudelijke validatie (RIO-06)"}
                  if rs else _onbekend("schema niet vastgelegd"))
        uit.append({
            "resource_id": rid, "id_soort": soort, "naam": r["naam"], "format": fmt,
            "sector": "mbo" if _types(rec) == {"mbo"} else None, "capabilities": cap,
            "schema": schema,
        })
    return uit


# ── sectoren ─────────────────────────────────────────────────────────────────

def _scope_uit_types(types: set[str]) -> dict[str, str]:
    """Zelfde regel als CBS-03; ``ho`` geeft hbo/wo ``unknown`` (HO-breed is geen hbo/wo)."""
    if not types or "allen" in types:
        return {s: UNKNOWN for s in SECTOREN}
    eigen = {"mbo": "mbo" in types, "hbo": bool(types & {"hbo", "ho"}), "wo": bool(types & {"wo", "ho"})}
    if not any(eigen.values()):
        return {s: UNSUPPORTED for s in SECTOREN}
    gemengd = bool(types - {"mbo", "hbo", "wo", "ho"})
    uit = {}
    for s in SECTOREN:
        if not eigen[s]:
            uit[s] = UNSUPPORTED
        elif gemengd or (s in ("hbo", "wo") and "ho" in types and s not in types):
            uit[s] = UNKNOWN
        else:
            uit[s] = SUPPORTED
    return uit


def _sectoren(provider: str, rec: dict, resources: list[dict]) -> tuple[dict, dict, dict]:
    """``(scopeprofiel, ho_breed, sectorselectie)``."""
    types = _types(rec)
    selectie: dict = {}
    scope_beslissing = rec.get("_scope") or {}
    if scope_beslissing.get("mbo_hbo_wo") == "buiten_scope":
        reden = scope_beslissing.get("reden")
        return ({s: UNSUPPORTED for s in SECTOREN},
                {"status": UNSUPPORTED, "reden": reden}, {"besluit": scope_beslissing})

    if provider == "rio":
        from ._filtercontract import typewaarden
        profiel = {s: UNKNOWN for s in SECTOREN}
        ho = _onbekend("geen sectorfilter in de spec")
        for sector, sleutel in (("mbo", "mbo"), ("ho", "ho")):
            try:
                waarden = typewaarden(rec["_rio_resource"], sleutel)
            except ValueError:
                waarden = []
            if waarden:
                selectie[sector] = {"soort": "filter", "filter": _typefilter(rec["_rio_resource"]),
                                    "waarden": waarden, "verplicht": True, "bron": "OpenAPI-enum"}
                if sector == "mbo":
                    profiel["mbo"] = SUPPORTED
                else:
                    ho = {"status": SUPPORTED, "verplicht_filter": True}
        if "ho" in selectie:
            for s in ("hbo", "wo"):
                selectie[s] = {"soort": "niet_beschikbaar",
                               "reden": "RIO-typefilters kennen alleen HO (hbo en wo samen)"}
        return profiel, ho, selectie

    if provider == "duo" and resources:
        per: dict[str, list] = {}
        rijen: dict[str, list] = {}
        for r in resources:
            if r["sector"]:
                per.setdefault(r["sector"], []).append(r["resource_id"])
            for s, sel in (r.get("rijselectie") or {}).items():
                rijen.setdefault(s, []).append({"resource_id": r["resource_id"], **sel})
        if per:
            profiel = {}
            for s in SECTOREN:
                if s not in per and s in rijen:
                    profiel[s] = SUPPORTED
                    selectie[s] = {"soort": "rijen", "selecties": rijen[s], "verplicht": True}
                elif s in per:
                    profiel[s] = SUPPORTED
                    verplicht = len(per[s]) < len([r for r in resources if "tabular_read" in r["capabilities"]])
                    selectie[s] = {"soort": "resources", "resource_ids": per[s], "verplicht": verplicht,
                                   "bron": "datasetsector" if s == "mbo" else "resourcenaam"}
                elif s in ("hbo", "wo") and "ho" in per:
                    profiel[s] = UNKNOWN
                    selectie[s] = {"soort": "niet_vastgesteld",
                                   "reden": "HO-resources zonder hbo/wo-splitsing in naam of schema"}
                else:
                    profiel[s] = UNSUPPORTED
            ho = ({"status": SUPPORTED, "resource_ids": per["ho"]} if "ho" in per
                  else {"status": SUPPORTED, "via": "hbo- en wo-resources samen"} if {"hbo", "wo"} <= set(per)
                  else {"status": UNSUPPORTED} if "mbo" in per and len(per) == 1 else _onbekend("niet vastgesteld"))
            return profiel, ho, selectie

    profiel = _scope_uit_types(types if provider != "duo" else _duo_types(rec, None)[0])
    if any(v == SUPPORTED for v in profiel.values()) and len(resources) > 0:
        for s, v in profiel.items():
            if v == SUPPORTED:
                selectie[s] = {"soort": "integraal", "verplicht": False, "bron": "gecureerde onderwijstype"}
    ho = ({"status": SUPPORTED} if "ho" in types and not (types - {"ho", "hbo", "wo"})
          else {"status": UNSUPPORTED} if profiel["hbo"] == profiel["wo"] == UNSUPPORTED
          else _onbekend("HO-dekking niet vastgesteld"))
    return profiel, ho, selectie


def _typefilter(resource: str) -> str | None:
    from ._filtercontract import filters
    for naam, f in filters(resource).items():
        if f.get("enum") and naam.lower().endswith("type"):
            return naam
    return None


# ── inhoudelijke velden ──────────────────────────────────────────────────────

def _teldefinitie(rec: dict) -> dict:
    td = rec.get("_teldefinitie")
    prov = rec.get("_notes_provenance") or {}
    if not td or prov.get("parse_status") not in (None, "ok"):
        return _onbekend("teldefinitie niet vastgelegd")
    if not td.get("teleenheid") and not td.get("selectie"):
        return _onbekend("teleenheid niet in de bron gevonden", selectie=td.get("selectie"))
    return {"status": SUPPORTED, **td, "bron": "CKAN notes"}


def _maat(rec: dict) -> dict:
    td = rec.get("_teldefinitie") or {}
    if td.get("teleenheid"):
        return {"status": SUPPORTED, "eenheid": td["teleenheid"], "bron": "CKAN notes"}
    return _onbekend("maat/eenheid niet vastgelegd")


def _populatie(rec: dict) -> dict:
    td = rec.get("_teldefinitie") or {}
    if td.get("inschrijvingstype") or td.get("ontdubbelingsdomein"):
        return {"status": SUPPORTED, "inschrijvingstype": td.get("inschrijvingstype"),
                "ontdubbelingsdomein": td.get("ontdubbelingsdomein"), "peildatum": td.get("peildatum"),
                "bron": "CKAN notes"}
    return _onbekend("populatie niet vastgelegd")


def _geografie(rec: dict) -> dict:
    niveaus = rec.get("_geo_niveau")
    if niveaus:
        return {"status": SUPPORTED, "niveaus": list(niveaus), "regionale_uitsplitsing": True}
    return {"status": UNKNOWN, "niveaus": None, "regionale_uitsplitsing": None,
            "reden": "geografische niveaus niet vastgesteld"}


def _alle_kolommen(resources: list[dict]) -> list[str]:
    gezien: list[str] = []
    for r in resources:
        for k in (r["schema"].get("kolommen") or []):
            if k not in gezien:
                gezien.append(k)
    return gezien


def _rio_id_formaat(resource: str) -> str:
    """``uuid``, een patroon of ``opaak``: wat een consument mag aannemen over het ID."""
    return _RIO_ID_FORMATEN.get(resource, "opaak")


def _join_sleutels(provider: str, rec: dict, resources: list[dict]) -> dict:
    if provider == "rio":
        # Een RIO-ID koppelt alleen binnen zijn eigen resource.
        resource = rec["_rio_resource"]
        sleutel = {"veld": "id", "sleutel": f"rio:{resource}", "formaat": _rio_id_formaat(resource)}
        return {"status": SUPPORTED, "sleutels": [sleutel], "bron": "RIO LOD API v2 (OpenAPI-spec)"}
    kolommen = _alle_kolommen(resources)
    if not kolommen:
        return _onbekend("kolommen niet vastgelegd")
    sleutels = []
    for k in kolommen:
        for prefix, sleutel in _JOIN_SLEUTELS:
            if k.upper().startswith(prefix):
                sleutels.append({"kolom": k, "sleutel": sleutel})
                break
    return {"status": SUPPORTED, "sleutels": sleutels, "bron": "kolomnamen in de schema-snapshot"}


def _instellingseenheden(provider: str, resources: list[dict]) -> dict:
    kolommen = [k for k in _alle_kolommen(resources) if k.upper().startswith(("INSTELLINGSCODE", "BRIN"))]
    if kolommen:
        return {"status": SUPPORTED, "kolommen": kolommen, "eenheid": "instelling (BRIN-code)"}
    if provider == "duo" and _alle_kolommen(resources):
        return {"status": UNSUPPORTED, "reden": "geen instellingscodekolom in de resources"}
    return _onbekend("instellingseenheden niet vastgelegd")


def _tijdsdekking(provider: str, rec: dict) -> dict:
    uit = {"tekst": rec.get("periode"), "frequentie": rec.get("frequentie")}
    if rec.get("_tijd"):
        return {"status": SUPPORTED, **uit, "claims": rec["_tijd"], "bron": "CKAN notes (gecontroleerd)"}
    if provider == "duo":
        from .duo import _schema_snapshot
        ds = _schema_snapshot()["datasets"].get(rec["_ckan_id"]) or {}
        per_resource = {}
        for r in ds.get("resources", []):
            w = r.get("waarden") or {}
            if not w.get("volledig"):
                continue
            for k in r["kolommen"]:
                info = w["kolommen"].get(k["naam"], {})
                if k["naam"].upper() in _PERIODEKOLOMMEN and "domein" in info:
                    per_resource[r["resource_id"]] = {"kolom": k["naam"], "waarden": info["domein"]}
                    break
        if per_resource:
            return {"status": SUPPORTED, **uit, "per_resource": per_resource,
                    "bron": "volledige scan van de periodekolom", "let_op": "waarnemingsperiode; geen prognosehorizon"}
    return {"status": UNKNOWN, **uit, "reden": "catalogustekst niet tegen de data gecontroleerd"}


def _beperkingen(rec: dict) -> list[dict]:
    uit = []
    for res in rec.get("_resources") or []:
        for b in (res.get("schema") or {}).get("beperkingen") or []:
            uit.append({**b, "resource": res.get("naam")})
    ngv = rec.get("niet_geschikt_voor")
    for tekst in ([ngv] if isinstance(ngv, str) else ngv or []):
        uit.append({"tekst": tekst, "bron": "annotatie"})
    for regel in rec.get("_publicatieregels") or []:
        uit.append({"tekst": regel.get("bronpassage") or json.dumps(regel, ensure_ascii=False),
                    "soort": regel.get("type"), "bron": "CKAN notes"})
    return uit


# ── record ───────────────────────────────────────────────────────────────────

def _record(rec: dict) -> dict:
    provider, bron_id = _bron_id(rec)
    resources = _duo_resources(rec) if provider == "duo" else _overige_resources(provider, rec)
    profiel, ho, selectie = _sectoren(provider, rec, resources)
    caps = sorted({c for r in resources for c in r["capabilities"]}) or list(_CAPABILITIES[provider])
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": f"{provider}:{bron_id}",
        "provider": rec.get("leverancier"),
        "titel": rec.get("bron"),
        "bron_url": (rec.get("documentatie") or {}).get("url"),
        "aliases": [bron_id],
        "onderwijssectoren": list(rec.get("onderwijstype") or []),
        "scopeprofiel": profiel,
        "ho_breed": ho,
        "sectorselectie": selectie,
        "onderwerpen": list(rec.get("tags") or []),
        "populatie": _populatie(rec),
        "teldefinitie": _teldefinitie(rec),
        "maat": _maat(rec),
        "geografie": _geografie(rec),
        "instellingseenheden": _instellingseenheden(provider, resources),
        "tijdsdekking": _tijdsdekking(provider, rec),
        "join_sleutels": _join_sleutels(provider, rec, resources),
        "beperkingen": _beperkingen(rec),
        "resources": resources,
        "herkomst": {
            "verrijking_status": rec.get("_verrijking_status"),
            "notes": rec.get("_notes_provenance"),
            "afgeleide_velden": {
                "scopeprofiel": "gecureerde onderwijstype, RIO-typefilter (spec) of DUO-resourcenaam",
                "join_sleutels": "kolomnamen",
                "tijdsdekking": "CKAN notes of volledige scan; anders onbekend",
            },
        },
        "capabilities": caps,
    }


def _compact(r: dict) -> dict:
    """Zoekkaart: zonder resource-schema's en beperkingsteksten (die via get_dataset).

    Werkt op een diepe kopie: de kaart deelt niets met de gecachete records (#390 A4).
    """
    r = _kopie(r)
    uit = {k: v for k, v in r.items() if k not in ("resources", "beperkingen", "herkomst")}
    tijd = r["tijdsdekking"]
    if "per_resource" in tijd:
        alle = sorted({w for x in tijd.pop("per_resource").values() for w in x["waarden"]})
        tijd["waarden"] = alle
    if "claims" in tijd:
        # De volledige claims (bronzinnen) via get_dataset; de kaart houdt historie en prognose apart (#390 A5).
        tijd["kaart"] = zoekkaart_tijd(tijd.pop("claims"))
    uit["teldefinitie"] = {k: v for k, v in r["teldefinitie"].items() if k != "uitsluitingen"}
    uit["resources"] = [
        {k: res[k] for k in ("resource_id", "naam", "format", "sector", "capabilities")}
        for res in r["resources"]
    ]
    uit["aantal_beperkingen"] = len(r["beperkingen"])
    return uit


def _check_versie(schema_version: int) -> None:
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise OnbekendSchema(
            f"schema_version {schema_version!r} niet ondersteund; kies uit {SUPPORTED_SCHEMA_VERSIONS}"
        )


def _check_sector(sector: str | None) -> None:
    if sector is not None and sector.lower() not in SECTOREN:
        raise ValueError(f"onbekende sector {sector!r}; kies uit {SECTOREN}")


@lru_cache(maxsize=1)
def _alle_records() -> tuple[dict, ...]:
    from . import catalog
    return tuple(_record(r) for r in catalog(source="all"))


def _kopie(r: dict) -> dict:
    return json.loads(json.dumps(r))


def catalog_records(schema_version: int = SCHEMA_VERSION, sector: str | None = None,
                    provider: str | None = None, compact: bool = True) -> list[dict]:
    """Records in het contract. Met ``sector`` alleen die waar de sector ``supported`` is.

    ``compact`` (standaard) laat resource-schema's en beperkingsteksten weg; die geeft
    :func:`get_dataset`. Records met onbekende dekking staan niet in een sectorselectie
    maar in :func:`scope_review`. Let op ``sectorselectie[sector].verplicht``: dan is de
    sector alleen leverbaar met die filter of resourcekeuze.
    """
    _check_versie(schema_version)
    _check_sector(sector)
    if provider is not None and provider.lower() not in PROVIDERS:
        raise ValueError(f"onbekende provider {provider!r}; kies uit {PROVIDERS}")
    records = [
        r for r in _alle_records()
        if (sector is None or r["scopeprofiel"][sector.lower()] == SUPPORTED)
        and (provider is None or r["dataset_id"].startswith(provider.lower() + ":"))
    ]
    return [_compact(r) if compact else _kopie(r) for r in records]


def scope_review(sector: str | None = None) -> list[dict]:
    """Records waarvan de dekking voor (een van) de sectoren nog ``unknown`` is."""
    _check_sector(sector)
    sectoren = (sector.lower(),) if sector else SECTOREN
    return [
        r for r in catalog_records()
        if any(r["scopeprofiel"][s] == UNKNOWN for s in sectoren)
        and not any(r["scopeprofiel"][s] == SUPPORTED for s in sectoren)
    ]


def get_dataset(dataset_id: str, schema_version: int = SCHEMA_VERSION) -> dict:
    """Exacte ID-resolutie: ``duo:p01hoinges`` of de alias ``p01hoinges``.

    Een alias die bij meer dan één provider voorkomt geeft ``AmbigueDataset``.
    """
    _check_versie(schema_version)
    sleutel = dataset_id.strip().lower()
    for r in _alle_records():
        if r["dataset_id"].lower() == sleutel:
            return _kopie(r)
    treffers = [r for r in _alle_records() if any(a.lower() == sleutel for a in r["aliases"])]
    if len(treffers) == 1:
        return _kopie(treffers[0])
    if treffers:
        opties = [r["dataset_id"] for r in treffers]
        raise AmbigueDataset(f"'{dataset_id}' past bij {opties}; gebruik het volledige ID", opties)
    raise DatasetNietGevonden(dataset_id)


def get_resource(dataset_id: str, resource: int | str) -> dict:
    """Eén resource met (voor DUO) het volledige schema uit de snapshot.

    ``resource``: de stabiele ``resource_id`` (aanbevolen), een index, exacte naam of
    unieke naam-substring. Een ambigue substring geeft ``AmbigueResource`` met opties.
    """
    from ._resolutie import kies
    ds = get_dataset(dataset_id)
    items = [{**r, "id": r["resource_id"]} for r in ds["resources"]]
    gekozen = kies(items, resource, ds["dataset_id"], id_key="id")
    gekozen.pop("id")
    gekozen["dataset_id"] = ds["dataset_id"]
    if ds["dataset_id"].startswith("duo:"):
        from .duo import resource_schemas
        for s in resource_schemas(ds["aliases"][0]):
            if s["resource_id"] == gekozen["resource_id"]:
                gekozen["schema_details"] = s
    return gekozen


def catalog_manifest() -> dict:
    """Welke catalogus gebruik ik werkelijk? Volledig offline."""
    from . import __version__
    from .duo import _schema_snapshot
    records = _alle_records()
    payload = json.dumps(records, sort_keys=True, ensure_ascii=False).encode("utf-8")
    snap = _schema_snapshot()
    return {
        "schema_version": SCHEMA_VERSION,
        "package_versie": __version__,
        "inhoudshash": hashlib.sha256(payload).hexdigest()[:16],
        "aantal": len(records),
        "aantal_per_provider": {p: sum(1 for r in records if r["dataset_id"].startswith(p + ":")) for p in PROVIDERS},
        "aantal_per_sector": {s: sum(1 for r in records if r["scopeprofiel"][s] == SUPPORTED) for s in SECTOREN},
        "aantal_review": len(scope_review()),
        "duo_resource_schemas": {
            "gegenereerd_op": snap.get("gegenereerd_op"),
            "schema_versie": snap.get("schema_versie"),
        },
        "capabilities": _CAPABILITIES,
    }


def valideer_record(record: dict) -> list[str]:
    """Controleer een record tegen schema v1; retourneert foutmeldingen (leeg = geldig)."""
    fouten: list[str] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        fouten.append("schema_version onjuist")
    for veld in ("dataset_id", "provider", "titel"):
        if not isinstance(record.get(veld), str) or not record.get(veld):
            fouten.append(f"{veld}: verplichte tekst ontbreekt")
    if str(record.get("dataset_id", "")).split(":")[0] not in PROVIDERS:
        fouten.append("dataset_id moet met een provider-voorvoegsel beginnen")
    if not isinstance(record.get("aliases"), list) or not record["aliases"]:
        fouten.append("aliases ontbreken")
    profiel = record.get("scopeprofiel")
    if not isinstance(profiel, dict) or set(profiel) != set(SECTOREN) or not set(profiel.values()) <= _STATUSSEN:
        fouten.append("scopeprofiel ongeldig")
    if (record.get("ho_breed") or {}).get("status") not in _STATUSSEN:
        fouten.append("ho_breed.status ongeldig")
    geo = record.get("geografie") or {}
    if geo.get("status") not in _STATUSSEN:
        fouten.append("geografie.status ongeldig")
    if geo.get("status") == UNKNOWN and geo.get("niveaus") == []:
        fouten.append("geografie: onbekend mag niet als lege lijst")
    for veld in ("populatie", "teldefinitie", "maat", "instellingseenheden", "tijdsdekking", "join_sleutels"):
        if not isinstance(record.get(veld), dict) or record[veld].get("status") not in _STATUSSEN:
            fouten.append(f"{veld}: status ontbreekt of ongeldig")
    ids = [r.get("resource_id") for r in record.get("resources") or []]
    if len(ids) != len(set(ids)) or not all(ids):
        fouten.append("resource_id's ontbreken of zijn niet uniek")
    if not record.get("capabilities"):
        fouten.append("capabilities ontbreken")
    return fouten
