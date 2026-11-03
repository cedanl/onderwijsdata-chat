"""Trek ``_kolommen``/``_kolomtypes``/``_kolomdefinities`` in de DUO-verrijking gelijk met
de resource-schema's (RIO-10).

Gebruik:
    uv run python catalogus/sync_kolommen.py

Bron is ``duo_resource_schemas.json`` (zie ``resource_schemas.py``), niet een steekproef
van vijf resources × 200 rijen. Alle tabelresources komen erin, ook die na de vijfde.
Types volgen de Datastore: een ``text``-kolom zoals ``GEMEENTENUMMER`` is ``tekst``
(``0106`` blijft ``0106``), nooit ``numeriek`` met een bereik.

Een type eindigt op ``; steekproef`` als de waarden niet uit een volledige scan komen;
de waarden zijn dan voorbeelden, geen domein. Alleen bij een volledige scan staan het
aantal unieke waarden en het numerieke bereik erbij.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from riodata.duo import column_definitions  # noqa: E402

DATA = ROOT / "src" / "riodata" / "data"
TOP_N = 25
NUMERIEK = {"numeric", "int", "int4", "int8", "float8", "float"}


def kolommen_en_types(schema: dict) -> tuple[dict, dict]:
    w = schema.get("waarden") or {}
    volledig = bool(w.get("volledig"))
    kolommen, types = {}, {}
    for k in schema["kolommen"]:
        info = (w.get("kolommen") or {}).get(k["naam"], {})
        numeriek = k["type"] in NUMERIEK
        basis = "numeriek" if numeriek else "tekst" if k["type"] == "text" else k["type"]
        if volledig:
            if numeriek and "min" in info:
                kolommen[k["naam"]] = f"numeriek (bereik: {info['min']}-{info['max']})"
            else:
                kolommen[k["naam"]] = list((info.get("domein") or [])[:TOP_N])
            types[k["naam"]] = f"{basis} ({info.get('aantal_uniek', 0)} waarden)"
        else:
            kolommen[k["naam"]] = list(info.get("voorbeeldwaarden") or [])
            types[k["naam"]] = f"{basis}; steekproef"
    return kolommen, types


def sync_record(record: dict, ds: dict) -> bool:
    tabellen = [r for r in ds["resources"] if r["inspectie"]["status"] == "ok" and r["kolommen"]]
    if not tabellen:
        return False
    namen: dict[str, int] = {}
    kolommen, types, alle = {}, {}, []
    for r in tabellen:
        sleutel = r["naam"]
        namen[sleutel] = namen.get(sleutel, 0) + 1
        if namen[sleutel] > 1:  # dubbele resourcenaam: maak de sleutel uniek met de UUID
            sleutel = f"{sleutel} ({r['resource_id']})"
        k, t = kolommen_en_types(r)
        kolommen[sleutel], types[sleutel] = k, t
        alle += [c for c in k if c not in alle]
    if len(tabellen) == 1:
        kolommen, types = next(iter(kolommen.values())), next(iter(types.values()))
    record["_kolommen"] = kolommen
    record["_kolomtypes"] = types
    record["_kolomdefinities"] = column_definitions(alle, record["_ckan_id"])
    return True


def main() -> int:
    snap = json.loads((DATA / "duo_resource_schemas.json").read_text(encoding="utf-8"))["datasets"]
    pad = DATA / "duo_resources_enriched.json"
    records = json.loads(pad.read_text(encoding="utf-8"))
    n = sum(sync_record(r, snap[r["_ckan_id"]]) for r in records if r.get("_ckan_id") in snap)
    pad.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{n}/{len(records)} records gelijkgetrokken met de resource-schema's → {pad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
