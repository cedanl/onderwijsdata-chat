"""Officiële resource-schema's per CKAN-resource (RIO-10).

Gebruik:
    uv run --extra analyse python catalogus/resource_schemas.py [--max-mb 20] [--alleen p01hoinges,...]

Schrijft ``src/riodata/data/duo_resource_schemas.json``: per dataset alle resources,
geïndexeerd op de CKAN resource-UUID (niet op naam of positie).

Per resource:

- **bronmetadata** uit ``package_show``: naam, beschrijving, formaat, MIME, grootte, hash,
  ``last_modified``, positie (alleen informatief) en ``total_record_count`` als
  ``technisch_aantal_rijen``. Dat aantal is uitsluitend een laadcontrole, geen telling van
  personen of inschrijvingen.
- **kolommen** met het officiële Datastore-veldtype (``text``, ``numeric``, ...). Zonder
  Datastore alleen de kolomnamen uit de CSV-kop, type ``onbekend``.
- **waarden**, strikt gescheiden naar methode:
  ``volledige_scan`` (hele CSV gelezen, kolommen als tekst) geeft ``domein`` en
  ``aantal_uniek``; ``steekproef`` (eerste N rijen) geeft alleen ``voorbeeldwaarden`` en
  ``volledig: false``. Een steekproef levert nooit een domein of unieke telling op.
- **inspectie**: ``ok``, ``mislukt`` (met fout), ``geen_tabel`` (pdf/png), ``alleen_kop`` of
  ``schema_conflict`` (de CSV heeft andere kolommen dan het Datastore-schema; ``fout`` noemt
  het verschil). Elke resource krijgt een status; mislukte resources worden niet weggelaten.
  Alleen ``ok`` levert een schema op waar loaders en het contract op bouwen.
- **schema_sha256** over kolomnamen en -types: verandert het schema, dan verandert de hash
  en is elke daarop gebaseerde cache ongeldig.

Codes blijven tekst: ``GEMEENTENUMMER`` ``0106`` blijft ``0106`` (Datastore-type ``text``).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
UIT = ROOT / "src" / "riodata" / "data" / "duo_resource_schemas.json"
CKAN = "https://onderwijsdata.duo.nl/api/3/action"
SCHEMA_VERSIE = 1
MAX_DOMEIN = 60  # meer unieke waarden: alleen aantal_uniek en min/max, geen domein
STEEKPROEF_RIJEN = 1000
TABEL_FORMATEN = {"CSV"}
NUMERIEK = {"numeric", "int", "int4", "int8", "float8", "float"}


def schema_hash(kolommen: list[dict]) -> str:
    payload = json.dumps([[k["naam"], k["type"]] for k in kolommen], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def datastore_kolommen(fields: list[dict]) -> list[dict]:
    """Datastore-velden zonder de technische ``_id``-kolom."""
    return [
        {"naam": f["id"], "type": f.get("type", "onbekend"), "type_bron": "datastore"}
        for f in fields
        if f.get("id") != "_id"
    ]


def sniff_sep(kop: str) -> str:
    regel = kop.lstrip("﻿").splitlines()[0] if kop.strip() else ""
    tellingen = {s: regel.count(s) for s in (",", ";", "\t", "|")}
    return max(tellingen, key=tellingen.get) if any(tellingen.values()) else ","


def _getal(v: str):
    try:
        f = float(v.replace(",", ".")) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else f


def volledige_waarden(rijen: list[dict], kolommen: list[dict]) -> dict:
    """Domein/bereik per kolom uit álle rijen (waarden als tekst gelezen)."""
    uit = {}
    for k in kolommen:
        naam = k["naam"]
        waarden = [r.get(naam) for r in rijen]
        gevuld = [w for w in waarden if w not in (None, "")]
        uniek = sorted(set(gevuld))
        info: dict = {"aantal_uniek": len(uniek), "aantal_leeg": len(waarden) - len(gevuld)}
        if len(uniek) <= MAX_DOMEIN:
            info["domein"] = uniek
        if k["type"] in NUMERIEK:
            getallen = [g for g in (_getal(w) for w in gevuld) if g is not None]
            if getallen:
                info["min"], info["max"] = min(getallen), max(getallen)
        uit[naam] = info
    return {"methode": "volledige_scan", "volledig": True, "rijen_gelezen": len(rijen), "kolommen": uit}


def steekproef_waarden(rijen: list[dict], kolommen: list[dict], n: int = 5) -> dict:
    """Voorbeeldwaarden uit een steekproef; bewust géén domein, telling of bereik."""
    uit = {}
    for k in kolommen:
        gezien: list = []
        for r in rijen:
            w = r.get(k["naam"])
            if w not in (None, "") and str(w) not in gezien:
                gezien.append(str(w))
            if len(gezien) >= n:
                break
        uit[k["naam"]] = {"voorbeeldwaarden": gezien}
    return {
        "methode": "steekproef",
        "volledig": False,
        "rijen_gelezen": len(rijen),
        "let_op": "eerste rijen van het bestand; geen volledig domein, bereik of unieke telling",
        "kolommen": uit,
    }


def lees_csv(content: bytes) -> tuple[list[str], list[dict]]:
    tekst = None
    for enc in ("utf-8-sig", "cp1252"):
        try:
            tekst = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if tekst is None:
        raise ValueError("CSV niet te decoderen als utf-8 of cp1252")
    reader = csv.DictReader(io.StringIO(tekst), delimiter=sniff_sep(tekst[:4000]))
    rijen = list(reader)
    return list(reader.fieldnames or []), rijen


def _get(client: httpx.Client, url: str, **params) -> httpx.Response:
    for poging in range(3):
        try:
            r = client.get(url, params=params or None)
            r.raise_for_status()
            return r
        except httpx.HTTPError:
            if poging == 2:
                raise
            time.sleep(2 * (poging + 1))
    raise AssertionError("onbereikbaar")


def _ckan(client: httpx.Client, actie: str, **params) -> dict:
    body = _get(client, f"{CKAN}/{actie}", **params).json()
    if not body.get("success"):
        raise RuntimeError(f"CKAN {actie}: {body.get('error')}")
    return body["result"]


def _public_url(r: dict) -> str:
    url = r.get("url", "")
    if "beheer-ggm-ckan-prd" in url:
        return f"https://onderwijsdata.duo.nl/datastore/dump/{r['id']}"
    return url


def _verschil(csv_kop: list[str], schema: list[str]) -> str:
    """Wat de CSV en het Datastore-schema van elkaar scheidt, voor ``inspectie.fout``."""
    alleen_csv = [n for n in csv_kop if n not in schema]
    alleen_schema = [n for n in schema if n not in csv_kop]
    if not alleen_csv and not alleen_schema:
        return "CSV-kop en Datastore-schema hebben dezelfde kolommen in een andere volgorde"
    return f"alleen in CSV: {alleen_csv}; alleen in Datastore: {alleen_schema}"[:300]


def inspecteer_resource(client: httpx.Client, res: dict, max_bytes: int, vandaag: str) -> dict:
    fmt = (res.get("format") or "").upper()
    uit = {
        "resource_id": res["id"],
        "naam": res.get("name", ""),
        "beschrijving": (res.get("description") or "").strip() or None,
        "positie": res.get("position"),
        "format": fmt,
        "mimetype": res.get("mimetype"),
        "grootte": res.get("size"),
        "hash": res.get("hash") or None,
        "last_modified": res.get("last_modified"),
        "url": _public_url(res),
        "datastore_actief": bool(res.get("datastore_active")),
        "technisch_aantal_rijen": res.get("total_record_count"),
        "kolommen": [],
        "schema_sha256": None,
        "waarden": None,
        "inspectie": {"status": None, "methode": None, "gecontroleerd_op": vandaag, "fout": None},
    }
    insp = uit["inspectie"]
    if fmt not in TABEL_FORMATEN:
        insp["status"] = "geen_tabel"
        return uit
    try:
        kolommen: list[dict] = []
        if uit["datastore_actief"]:
            ds = _ckan(client, "datastore_search", resource_id=res["id"], limit=STEEKPROEF_RIJEN)
            kolommen = datastore_kolommen(ds["fields"])
            steekproef = ds["records"]
        grootte = res.get("size") or 0
        if grootte and grootte <= max_bytes:
            namen, rijen = lees_csv(_get(client, uit["url"]).content)
            namen = [n for n in namen if n != "_id"]  # Datastore-dump voegt een technische _id toe
            if not kolommen:
                kolommen = [{"naam": n, "type": "onbekend", "type_bron": "csv_kop"} for n in namen]
            uit["csv_kolommen_gelijk_aan_schema"] = namen == [k["naam"] for k in kolommen]
            if not uit["csv_kolommen_gelijk_aan_schema"]:
                insp["status"] = "schema_conflict"
                insp["fout"] = _verschil(namen, [k["naam"] for k in kolommen])
            uit["csv_aantal_rijen"] = len(rijen)
            uit["waarden"] = volledige_waarden(rijen, kolommen)
            insp["methode"] = "datastore+volledige_csv" if uit["datastore_actief"] else "volledige_csv"
        elif uit["datastore_actief"]:
            uit["waarden"] = steekproef_waarden(steekproef, kolommen)
            insp["methode"] = "datastore+steekproef"
        else:
            kop = _get(client, uit["url"]).content[:4000].decode("utf-8-sig", errors="replace")
            namen = next(csv.reader(io.StringIO(kop), delimiter=sniff_sep(kop)), [])
            kolommen = [{"naam": n, "type": "onbekend", "type_bron": "csv_kop"} for n in namen]
            insp["status"] = "alleen_kop"
            insp["methode"] = "csv_kop"
        uit["kolommen"] = kolommen
        uit["schema_sha256"] = schema_hash(kolommen) if kolommen else None
        insp["status"] = insp["status"] or "ok"
    except Exception as e:  # noqa: BLE001 — elke fout wordt per resource als status vastgelegd
        insp["status"] = "mislukt"
        insp["fout"] = f"{type(e).__name__}: {e}"[:300]
    return uit


def dataset_meta(p: dict) -> dict:
    """Datasetniveau: wijzigingsdatum, titel, CKAN-groepen en DCAT-thema's (sectorbewijs)."""
    themas: list[str] = []
    for e in p.get("extras", []):
        if e.get("key") == "theme":
            waarde = e.get("value") or ""
            try:
                themas += json.loads(waarde) if waarde.startswith("[") else [waarde]
            except json.JSONDecodeError:
                themas.append(waarde)
    return {
        "metadata_modified": p.get("metadata_modified"),
        "titel": p.get("title"),
        "ckan_groepen": [g["name"] for g in p.get("groups", [])],
        "dcat_themas": [t for t in themas if t],
    }


def bouw(ids: list[str] | None, max_bytes: int, vorige: dict | None = None) -> dict:
    vandaag = dt.date.today().isoformat()
    datasets = dict((vorige or {}).get("datasets", {}))
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        pkgs = _ckan(client, "package_search", rows=1000)["results"]
        for p in pkgs:
            if ids and p["name"] not in ids:
                continue
            print(f"{p['name']} ({len(p['resources'])} resources)", file=sys.stderr)
            datasets[p["name"]] = {
                **dataset_meta(p),
                "resources": [inspecteer_resource(client, r, max_bytes, vandaag) for r in p["resources"]],
            }
    return {
        "schema_versie": SCHEMA_VERSIE,
        "gegenereerd_op": vandaag,
        "bron": CKAN,
        "max_volledige_scan_bytes": max_bytes,
        "datasets": dict(sorted(datasets.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-mb", type=float, default=20)
    ap.add_argument("--alleen", default="", help="komma-gescheiden CKAN-IDs (rest blijft behouden)")
    args = ap.parse_args()
    ids = [i for i in args.alleen.split(",") if i] or None
    vorige = json.loads(UIT.read_text(encoding="utf-8")) if ids and UIT.exists() else None
    data = bouw(ids, int(args.max_mb * 1_000_000), vorige)
    UIT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    statussen: dict[str, int] = {}
    for d in data["datasets"].values():
        for r in d["resources"]:
            statussen[r["inspectie"]["status"]] = statussen.get(r["inspectie"]["status"], 0) + 1
    print(f"{len(data['datasets'])} datasets; inspectiestatus: {statussen} → {UIT}", file=sys.stderr)
    return 1 if statussen.get("mislukt") else 0


if __name__ == "__main__":
    sys.exit(main())
