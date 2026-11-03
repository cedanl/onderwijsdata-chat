"""Genereer het RIO-filtercontract uit de OpenAPI-spec (v3).

Schrijft ``src/riodata/data/rio_filtercontract.json`` en brengt de RIO-catalogusbestanden in lijn
met de spec: de queryfilters (``filters``), de sub-resources (``sub_resources``) en de
documentatielink (``documentatie``) per resource. Bestaande filters blijven staan (een hernoemd
filter krijgt op zijn plaats de nieuwe naam), ontbrekende worden achteraan toegevoegd. Een
resource die in v3 geen lijst-endpoint meer heeft, krijgt precies de filters van de sub-resource.

Gebruik:
    uv run --extra catalogus python catalogus/genereer_filtercontract.py
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "RIO_LOD_API_v3.yml"
DATA = ROOT / "src" / "riodata" / "data"
CONTRACT = DATA / "rio_filtercontract.json"
CATALOGI = ("rio_resources.json", "rio_resources_ai.json", "rio_resources_enriched.json")
# Dezelfde records, als bron voor de catalogus (data/02-prepared); blijven gelijk opgebouwd.
BRONCATALOGI = (ROOT / "data" / "02-prepared" / "rio_resources.json", ROOT / "data" / "02-prepared" / "rio_resources_ai.json")
DOCS_URL = "https://lod.onderwijsregistratie.nl/rio-api"

PAGINERING = ("page", "pageSize", "sort")

# v2 → v3: de typefilters heten op elke resource ``type``. Een catalogusfilter met de oude naam
# wordt op zijn plaats hernoemd, zodat de volgorde van de filters blijft.
HERNOEMD = {
    "erkenningtype": "type",
    "opleidingseenheidtype": "type",
    "opleidingserkenningtype": "type",
    "organisatorischeEenheidType": "type",
}


def _param(spec: dict, p: dict) -> dict:
    if "$ref" in p:
        p = spec["components"]["parameters"][p["$ref"].split("/")[-1]]
    schema = p.get("schema", {})
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
    return {
        "naam": p["name"],
        "in": p.get("in"),
        "type": schema.get("type"),
        "format": schema.get("format"),
        "enum": schema.get("enum"),
        "beschrijving": p.get("description"),
    }


def _server(spec: dict) -> str:
    return spec["servers"][0]["url"].rstrip("/")


def _versie(spec: dict) -> str:
    return str(spec["info"].get("version", "")).split(".")[0]


def bouw_contract(spec_pad: Path = SPEC, catalogus_pad: Path = DATA / "rio_resources_ai.json") -> dict:
    raw = spec_pad.read_bytes()
    spec = yaml.safe_load(raw)
    lijst: dict[str, dict] = {}
    sub: dict[str, list[tuple[str, list[dict]]]] = {}  # sub-resourcenaam → [(pad, queryparams)]
    for pad, item in spec["paths"].items():
        get = item.get("get")
        if not get:
            continue
        delen = pad.strip("/").split("/")
        params = [_param(spec, p) for p in get.get("parameters", [])]
        query = [p for p in params if p["in"] == "query"]
        if len(delen) == 1:
            lijst[delen[0]] = {
                "filters": [{**p, "bron": "openapi"} for p in query if p["naam"] not in PAGINERING],
                "paginering": [p["naam"] for p in query if p["naam"] in PAGINERING],
                # De spec geeft ``sort`` geen waarden of richting: pas vastgelegd als er een enum is.
                "sort_schema_in_spec": any(p["naam"] == "sort" and p["enum"] for p in query),
                "lijst_endpoint": True,
            }
        elif len(delen) == 3 and delen[1] == "{id}":
            sub.setdefault(delen[2], []).append((pad, query))
    resources = lijst
    # Catalogusresources zonder lijst-endpoint (sinds v3: cohorten, contactadressen,
    # onderwijslocatiegebruiken): alleen als sub-resource, met de filters van dát pad.
    catalogus = json.loads(catalogus_pad.read_text(encoding="utf-8"))
    for r in catalogus:
        naam = r["_rio_resource"]
        if naam in resources:
            continue
        paden = sub.get(naam, [])
        filters: dict[str, dict] = {}
        for _, query in paden:
            for p in query:
                if p["naam"] not in PAGINERING:
                    filters.setdefault(p["naam"], {**p, "bron": "openapi (sub-resource)"})
        resources[naam] = {
            "filters": list(filters.values()),
            "paginering": [],
            "sort_schema_in_spec": False,
            "lijst_endpoint": False,
            "via": [pad for pad, _ in paden],
        }
    for naam, res in resources.items():
        res["sub_resources"] = sorted(
            {p.strip("/").split("/")[2] for p in spec["paths"] if p.startswith(f"/{naam}/{{id}}/")}
        )
    # Filters die de catalogus noemt maar de spec niet kent: niet weggooien, wel markeren.
    # Alleen bij een lijst-endpoint; zonder lijst-endpoint volgt de catalogus de spec precies.
    for r in catalogus:
        res = resources[r["_rio_resource"]]
        if not res["lijst_endpoint"]:
            res["catalogus_zonder_spec"] = []
            continue
        in_spec = {f["naam"] for f in res["filters"]}
        res["catalogus_zonder_spec"] = [
            {"naam": n, "status": "niet in spec; live ondersteuning niet vastgesteld"}
            for n in r.get("filters", []) if HERNOEMD.get(n, n) not in in_spec
        ]
    return {
        "spec_versie": spec["info"].get("version"),
        "spec_sha256": hashlib.sha256(raw).hexdigest(),
        "server": _server(spec),
        "resources": resources,
    }


def _record_begin(tekst: str, resource: str) -> int:
    """Positie van het ``_rio_resource``-veld van één record; de velden ervóór horen bij dat record."""
    return tekst.index(f'"_rio_resource": "{resource}"')


def _vervang_lijst(tekst: str, resource: str, sleutel: str, nieuw: list[str]) -> str:
    """Vervang de lijst ``sleutel`` van één record en behoud de opmaak van het bestand."""
    anker = _record_begin(tekst, resource)
    begin = tekst.rindex(f'"{sleutel}": [', 0, anker)
    eind = tekst.index("]", begin) + 1
    oud = tekst[begin:eind]
    if "\n" in oud:
        regel_begin = tekst.rindex("\n", 0, begin) + 1
        inspring = " " * (begin - regel_begin)
        items = ",\n".join(f"{inspring}  {json.dumps(n)}" for n in nieuw)
        vervanging = f'"{sleutel}": [\n{items}\n{inspring}]' if nieuw else f'"{sleutel}": []'
    else:
        vervanging = f'"{sleutel}": ' + json.dumps(nieuw, ensure_ascii=False)
    return tekst[:begin] + vervanging + tekst[eind:]


def _vervang_documentatie(tekst: str, resource: str, doc: dict) -> str:
    """Vervang ``tekst`` en ``url`` in het ``documentatie``-blok van één record."""
    anker = _record_begin(tekst, resource)
    begin = tekst.rindex('"documentatie": {', 0, anker)
    eind = tekst.index("}", begin) + 1
    blok = tekst[begin:eind]
    for veld in ("tekst", "url"):
        blok = re.sub(rf'"{veld}": "[^"]*"', lambda m: f'"{veld}": {json.dumps(doc[veld], ensure_ascii=False)}', blok, count=1)
    return tekst[:begin] + blok + tekst[eind:]


def _hernoem(huidig: list[str]) -> list[str]:
    nieuw: list[str] = []
    for n in huidig:
        n = HERNOEMD.get(n, n)
        if n not in nieuw:
            nieuw.append(n)
    return nieuw


def documentatie(contract: dict, resource: str, versie: str) -> dict:
    res = contract["resources"][resource]
    if res["lijst_endpoint"]:
        return {"tekst": f"RIO LOD API v{versie} — {resource}", "url": f"{contract['server']}/{resource}"}
    return {"tekst": f"RIO LOD API v{versie} — {resource} (alleen als sub-resource)", "url": DOCS_URL}


def sync_catalogus(contract: dict, pad: Path) -> int:
    """Breng filters, sub_resources en documentatie van elk record in lijn met het contract.

    Filters: hernoemde namen op hun plaats, bestaande blijven staan (gemarkeerd als
    ``catalogus_zonder_spec`` als de spec ze niet kent), ontbrekende achteraan. Zonder
    lijst-endpoint precies de filters van de sub-resource. De rest van het bestand blijft gelijk.
    """
    tekst = pad.read_text(encoding="utf-8")
    versie = str(contract.get("spec_versie", "")).split(".")[0]
    gewijzigd = 0
    for r in json.loads(tekst):
        naam = r["_rio_resource"]
        spec_res = contract["resources"].get(naam)
        if spec_res is None:
            continue
        spec_namen = [f["naam"] for f in spec_res["filters"]]
        if spec_res["lijst_endpoint"]:
            huidig = _hernoem(r.get("filters", []))
            nieuw = huidig + [n for n in spec_namen if n not in huidig]
        else:
            nieuw = spec_namen
        wijzigingen = [
            (nieuw != r.get("filters", []), lambda t: _vervang_lijst(t, naam, "filters", nieuw)),
            (spec_res["sub_resources"] != r.get("sub_resources", []),
             lambda t: _vervang_lijst(t, naam, "sub_resources", spec_res["sub_resources"])),
            (documentatie(contract, naam, versie) != r.get("documentatie"),
             lambda t: _vervang_documentatie(t, naam, documentatie(contract, naam, versie))),
        ]
        if any(w for w, _ in wijzigingen):
            for w, f in wijzigingen:
                if w:
                    tekst = f(tekst)
            gewijzigd += 1
    pad.write_text(tekst, encoding="utf-8")
    return gewijzigd


def main() -> None:
    contract = bouw_contract()
    CONTRACT.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lijst = sum(1 for r in contract["resources"].values() if r["lijst_endpoint"])
    print(f"{CONTRACT.name}: spec {contract['spec_versie']}, {len(contract['resources'])} resources ({lijst} met lijst-endpoint)")
    for pad in [*(DATA / naam for naam in CATALOGI), *BRONCATALOGI]:
        print(f"{pad.relative_to(ROOT)}: {sync_catalogus(contract, pad)} records bijgewerkt")


if __name__ == "__main__":
    main()
