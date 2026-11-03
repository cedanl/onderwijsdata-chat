"""
Discovery-diff: meldt CBS-tabellen onder onderwijsthema's die nog niet in de
catalogus staan, geclassificeerd op productscope (mbo/hbo/wo). De uitkomst is een
JSON-rapport voor review; er wordt niets automatisch aan de catalogus toegevoegd.

Het rapport scheidt:
  - nieuw_voor_review:   mogelijk mbo/hbo/wo-relevant (inclusief onbekend)
  - uitgesloten:         buiten scope of arbeidsmarkt-only (met motivatie)
  - bestaand:            sectorclassificatie van de bestaande records, actief vs. archief
  - bestaand_niet_gevonden: catalogusitems die de themasweep niet meer vindt
                            (informatief; verdwijnen nooit stilzwijgend)

Gebruik:
  uv run python catalogus/discovery_diff.py
  uv run python catalogus/discovery_diff.py --output pad.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from sector import classificeer_sector, is_toegelaten, ONBEKEND

ROOT = Path(__file__).parent.parent
CATALOG = "https://opendata.cbs.nl/ODataCatalog"
API = "https://opendata.cbs.nl/ODataApi/OData"
CATALOGUS = ROOT / "data/02-prepared/cbs_datasets_ai.json"
DEFAULT_OUTPUT = ROOT / "data/03-output/cbs_discovery.json"
SCHEMA_VERSIE = 1

# Themasweep: onderwijsthema's worden uit de live themahiërarchie afgeleid (eigen titel
# of die van een bovenliggend thema), niet uit een vaste ID-lijst. Zo vallen hernummerde
# of nieuwe thema's niet buiten de sweep, zoals 118 'Onderwijs' onder 'Caribisch Nederland'
# (84312NED, Caribisch NL; studenten mbo). De classificatie beslist daarna over scope.
_ONDERWIJS_THEMA = re.compile(
    r"onderwijs|\bmbo\b|\bhbo\b|\bwo\b|\bho\b|student|gediplomeerd|schoolverlat|\bvsv\b|leven ?lang", re.I)
# Gemotiveerde uitzonderingen die de titelregel mist: {id: reden}.
EXTRA_THEMA_IDS: dict[int, str] = {}
EXTRA_TABEL_IDS: dict[str, str] = {}
# CBS-miscategorisaties onder onderwijsthema's
UITGESLOTEN_THEMA_NAMEN = {"Toerisme", "Bouwen en wonen", "Hypotheken", "Prijzen"}


def selecteer_themas(themas: list[dict]) -> dict[int, str]:
    """Thema-ID → motivatie, voor elk thema dat zelf of via een voorouder over onderwijs gaat."""
    per_id = {t["ID"]: t for t in themas}

    def onderwijs_voorouder(t: dict) -> str | None:
        gezien = set()
        while t and t["ID"] not in gezien:
            gezien.add(t["ID"])
            if _ONDERWIJS_THEMA.search(t.get("Title") or ""):
                return t["Title"]
            t = per_id.get(t.get("ParentID"))
        return None

    gekozen = {}
    for t in themas:
        if t.get("Title") in UITGESLOTEN_THEMA_NAMEN:
            continue
        bron = onderwijs_voorouder(t)
        if bron:
            gekozen[t["ID"]] = f"onderwijsthema ({bron})"
    for tid, reden in EXTRA_THEMA_IDS.items():
        gekozen.setdefault(tid, f"uitzondering: {reden}")
    return gekozen


def _get(url: str, **params) -> list[dict]:
    params.setdefault("$format", "json")
    r = httpx.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()["value"]


def fetch_sweep(thema_ids: list[int] | None = None) -> tuple[dict[str, int], dict[int, str], list[int]]:
    """Tables_Themes per thema → ({tabel-ID: thema-ID}, themanamen, aangevraagde thema-ID's).

    Zonder ``thema_ids`` worden de onderwijsthema's uit de live hiërarchie gekozen.
    """
    themas = _get(f"{CATALOG}/Themes")
    namen = {r["ID"]: r["Title"] for r in themas}
    if thema_ids is None:
        thema_ids = sorted(selecteer_themas(themas))
    ids: dict[str, int] = {}
    for tid in thema_ids:
        rows = _get(f"{CATALOG}/Tables_Themes", **{"$filter": f"ThemeID eq {tid}", "$select": "TableIdentifier,ThemeID"})
        for r in rows:
            ids.setdefault(r["TableIdentifier"], tid)
    for tabel in EXTRA_TABEL_IDS:
        ids.setdefault(tabel, -1)
    namen[-1] = "uitzondering (EXTRA_TABEL_IDS)"
    return ids, namen, list(thema_ids)


def fetch_details(dataset_id: str) -> dict:
    """Titel, frequentie, periode, wijzigingsdatum en dimensietitels van één tabel."""
    info = (_get(f"{API}/{dataset_id}/TableInfos") or [{}])[0]
    props = _get(f"{API}/{dataset_id}/DataProperties")
    return {
        "titel": (info.get("Title") or "").strip(),
        "frequentie": (info.get("Frequency") or "").strip(),
        "periode": (info.get("Period") or "").strip(),
        "modified": str(info.get("Modified") or "")[:10] or None,
        "dimensies": [p["Title"].strip() for p in props if p.get("Type") in ("Dimension", "GeoDimension")],
    }


def _archief(details: dict) -> bool:
    return "stopgezet" in details["frequentie"].lower() or bool(details["modified"] and details["modified"] < "2021-01-01")


def bouw_rapport(catalogus: list[dict], sweep: dict[str, int], themanamen: dict[int, str], details: dict[str, dict],
                 aangevraagde_themas: list[int] | None = None) -> dict:
    """Pure functie: combineert catalogus, themasweep en tabeldetails tot het rapport."""
    in_catalogus = {r["_cbs_id"].upper(): r for r in catalogus}
    nieuw, uitgesloten = [], []
    for tid in sorted(i for i in sweep if i.upper() not in in_catalogus):
        d = details.get(tid)
        thema = themanamen.get(sweep[tid], "")
        if d is None:  # details niet op te halen: een thema alleen is geen bewijs
            d = {"titel": "", "frequentie": "", "periode": "", "modified": None, "dimensies": []}
            kl = {"classificatie": ONBEKEND, "sectoren": [], "arbeidsmarkt_only": False,
                  "motivatie": "tabeldetails niet op te halen; review nodig"}
        else:
            kl = classificeer_sector(d["titel"], thema, d["dimensies"])
        item = {"dataset_id": f"cbs:{tid}", "titel": d["titel"], "thema": thema, "periode": d["periode"],
                "gearchiveerd": _archief(d), "classificatie": kl["classificatie"], "sectoren": kl["sectoren"],
                "motivatie": kl["motivatie"], "arbeidsmarkt_only": kl["arbeidsmarkt_only"]}
        if is_toegelaten(kl["classificatie"]) or kl["classificatie"] == ONBEKEND:
            item["advies"] = "review"
            nieuw.append(item)
        else:
            item["advies"] = "niet_toevoegen"
            uitgesloten.append(item)

    bestaand, per_klasse = [], {}
    for r in catalogus:
        kl = classificeer_sector(r.get("bron", ""), r.get("_thema", ""), r.get("_dimensies", []))
        gecureerd = r.get("onderwijstype", [])
        # Regels en curatie spreken elkaar tegen: curatie zegt zuiver mbo/hbo/wo, regels zeggen buiten scope.
        afwijkend = (kl["classificatie"] == "buiten_scope"
                     and bool(gecureerd) and {t.upper() for t in gecureerd} <= {"MBO", "HBO", "WO"})
        bestaand.append({"dataset_id": f"cbs:{r['_cbs_id']}", "classificatie": kl["classificatie"],
                         "gecureerd_onderwijstype": gecureerd, "gearchiveerd": bool(r.get("_archief")),
                         "motivatie": kl["motivatie"], "afwijkend_van_curatie": afwijkend})
        sleutel = "historisch" if r.get("_archief") else "actief"
        per_klasse.setdefault(kl["classificatie"], {"actief": 0, "historisch": 0})[sleutel] += 1

    return {
        "schema_version": SCHEMA_VERSIE,
        "thema_ids": sorted(set(sweep.values())),
        "thema_ids_aangevraagd": sorted(aangevraagde_themas) if aangevraagde_themas is not None else None,
        "mislukte_details": sorted(f"cbs:{i}" for i in sweep if i.upper() not in in_catalogus and i not in details),
        "samenvatting": {
            "gevonden_in_sweep": len(sweep),
            "al_in_catalogus": len(sweep) - len(nieuw) - len(uitgesloten),
            "nieuw_voor_review": len(nieuw),
            "uitgesloten": len(uitgesloten),
            "uitgesloten_arbeidsmarkt_only": sum(1 for u in uitgesloten if u["arbeidsmarkt_only"]),
            "nieuw_voor_review_actief": sum(1 for n in nieuw if not n["gearchiveerd"]),
            "nieuw_voor_review_historisch": sum(1 for n in nieuw if n["gearchiveerd"]),
            "bestaand_per_classificatie": per_klasse,
            "bestaand_afwijkend_van_curatie": sum(1 for b in bestaand if b["afwijkend_van_curatie"]),
        },
        "nieuw_voor_review": nieuw,
        "uitgesloten": uitgesloten,
        "bestaand": bestaand,
        "bestaand_niet_gevonden": sorted(f"cbs:{i}" for i in (r["_cbs_id"] for r in catalogus) if i.upper() not in {s.upper() for s in sweep}),
    }


def main():
    p = argparse.ArgumentParser(description="Meld nieuwe CBS-tabellen onder onderwijsthema's ter review.")
    p.add_argument("--output", default=str(DEFAULT_OUTPUT))
    p.add_argument("--fail-on-new", action="store_true", help="exit 3 als er nieuwe tabellen voor review zijn")
    args = p.parse_args()

    catalogus = json.loads(CATALOGUS.read_text(encoding="utf-8"))
    bekend = {r["_cbs_id"].upper() for r in catalogus}
    print("Themasweep via Tables_Themes...")
    sweep, namen, themas = fetch_sweep()
    print(f"{len(themas)} onderwijsthema's uit de themahiërarchie")
    nieuw_ids = [i for i in sweep if i.upper() not in bekend]
    print(f"{len(sweep)} tabellen in sweep, {len(nieuw_ids)} niet in catalogus; details ophalen...")
    details = {}
    for n, tid in enumerate(nieuw_ids, 1):
        try:
            details[tid] = fetch_details(tid)
        except Exception as e:
            print(f"  [{n}/{len(nieuw_ids)}] {tid} FOUT: {type(e).__name__}")
    rapport = bouw_rapport(catalogus, sweep, namen, details, themas)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    s = rapport["samenvatting"]
    print(f"Review: {s['nieuw_voor_review']} (actief {s['nieuw_voor_review_actief']}), "
          f"uitgesloten: {s['uitgesloten']} → {out}")
    if args.fail_on_new and s["nieuw_voor_review"]:
        sys.exit(3)


if __name__ == "__main__":
    main()
