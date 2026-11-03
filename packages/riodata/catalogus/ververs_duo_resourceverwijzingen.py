"""
Ververst de bestandsverwijzingen (id en url) van DUO-resources in duo_resources.json.

DUO maakt het 'controlebestand' van een dataset bij elke publicatie opnieuw aan, met een nieuwe
resource-ID en een nieuwe ``datastore/dump``-URL. De verwijzing in het snapshot geeft dan HTTP 404
terwijl het bestand zelf gewoon bestaat. Dit script zoekt die resources op naam terug in CKAN en
vervangt alleen ``id`` en ``url``.

Wat het doet (en wat niet):
- Een snapshot-resource waarvan het ID nog in CKAN staat, blijft ongemoeid.
- Een snapshot-resource waarvan het ID weg is, maar waarvan de naam precies één niet-gekoppelde
  CKAN-resource heeft, krijgt het nieuwe ID en de nieuwe URL.
- Een resource die in CKAN niet meer bestaat, en een nieuwe resource in CKAN, worden alleen gemeld.
  Toevoegen of verwijderen raakt ``_kolommen`` en de resource-schema's en is aan een
  catalogusupdate (update_duo_resource_kolommen.py), niet aan dit script.

Gebruik:
  uv run python catalogus/ververs_duo_resourceverwijzingen.py --controle   # alleen melden
  uv run python catalogus/ververs_duo_resourceverwijzingen.py              # schrijf duo_resources.json

Het enriched-bestand houdt een kopie van ``_resources`` bij (test_catalog_merge bewaakt dat die gelijk
blijft aan de catalogus); die kopie wordt hier mee bijgewerkt. De afgeleide laag (``_kolommen`` enz.)
blijft zoals ze is: de resourcenamen zijn niet veranderd.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

RESOURCES = ROOT / "src" / "riodata" / "data" / "duo_resources.json"
ENRICHED = ROOT / "src" / "riodata" / "data" / "duo_resources_enriched.json"


def ververs_resources(snapshot: list[dict], live: list[dict]) -> tuple[list[dict], dict[str, list[str]]]:
    """Geef de snapshot-resources met bijgewerkte id en url, plus meldingen per soort.

    Meldingen: ``ververst`` (naam), ``vervallen`` (snapshot-resource die CKAN niet meer kent) en
    ``nieuw`` (CKAN-resource die het snapshot niet kent).
    """
    live_ids = {r["id"] for r in live}
    snapshot_ids = {r["id"] for r in snapshot}
    nog_vrij = [r for r in live if r["id"] not in snapshot_ids]

    meldingen: dict[str, list[str]] = {"ververst": [], "vervallen": [], "nieuw": []}
    nieuwe_lijst = []
    for r in snapshot:
        if r["id"] in live_ids:
            nieuwe_lijst.append(r)
            continue
        kandidaten = [v for v in nog_vrij if v["naam"] == r["naam"]]
        if len(kandidaten) == 1:
            nog_vrij.remove(kandidaten[0])
            nieuwe_lijst.append({**r, "id": kandidaten[0]["id"], "url": kandidaten[0]["url"]})
            meldingen["ververst"].append(r["naam"])
        else:
            nieuwe_lijst.append(r)
            meldingen["vervallen"].append(r["naam"])
    meldingen["nieuw"] = [r["naam"] for r in nog_vrij]
    return nieuwe_lijst, meldingen


def main() -> int:
    from riodata import duo

    p = argparse.ArgumentParser(description="Ververs verouderde DUO-resourceverwijzingen.")
    p.add_argument("--controle", action="store_true", help="alleen melden, niets schrijven")
    args = p.parse_args()

    records = json.loads(RESOURCES.read_text(encoding="utf-8"))
    gewijzigd = 0
    for rec in records:
        nieuw, meldingen = ververs_resources(rec["_resources"], duo.resources(rec["_ckan_id"]))
        for soort, namen in meldingen.items():
            for naam in namen:
                print(f"{rec['_ckan_id']}: {soort}: {naam}")
        if meldingen["ververst"]:
            rec["_resources"] = nieuw
            gewijzigd += len(meldingen["ververst"])

    print(f"\n{gewijzigd} verwijzingen ververst")
    if gewijzigd and not args.controle:
        RESOURCES.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        _sync_enriched({r["_ckan_id"]: r["_resources"] for r in records})
        print(f"{RESOURCES.relative_to(ROOT)} en {ENRICHED.relative_to(ROOT)} geschreven")
    return 0


def _sync_enriched(resources_per_dataset: dict[str, list[dict]]) -> None:
    """Zet ``_resources`` in het enriched-bestand gelijk aan het basisbestand; verder blijft het ongemoeid."""
    tekst = ENRICHED.read_text(encoding="utf-8")
    records = json.loads(tekst)
    for rec in records:
        if rec["_ckan_id"] in resources_per_dataset:
            rec["_resources"] = resources_per_dataset[rec["_ckan_id"]]
    uit = json.dumps(records, ensure_ascii=False, indent=2) + ("\n" if tekst.endswith("\n") else "")
    ENRICHED.write_text(uit, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
