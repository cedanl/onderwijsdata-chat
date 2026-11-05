"""
Check alle datasets in de catalogus tegen CBS TableInfos en update _laatste_update.
Schrijft alleen terug als er iets veranderd is.
"""
import json
import sys
from pathlib import Path

import httpx

CATALOGUS = Path("data/02-prepared/cbs_datasets_ai.json")


def fetch_modified(client: httpx.Client, cbs_id: str) -> str | None:
    url = f"https://opendata.cbs.nl/ODataApi/OData/{cbs_id}/TableInfos"
    r = client.get(url, params={"$format": "json"}, timeout=30)
    r.raise_for_status()
    value = r.json().get("value", [])
    if not value:
        return None
    return value[0].get("Modified", "")[:10]


def main():
    datasets = json.loads(CATALOGUS.read_text())
    total = len(datasets)

    updates = []
    errors = []

    with httpx.Client() as client:
        for i, ds in enumerate(datasets, 1):
            cbs_id = ds["_cbs_id"]
            huidig = ds.get("_laatste_update")
            print(f"[{i:3}/{total}] {cbs_id:<14}", end=" ", flush=True)
            try:
                nieuw = fetch_modified(client, cbs_id)
                if nieuw and nieuw != huidig:
                    ds["_laatste_update"] = nieuw
                    updates.append((cbs_id, huidig, nieuw))
                    print(f"{huidig or '???'} → {nieuw}  ← GEWIJZIGD")
                else:
                    print(f"{huidig}  ✓")
            except Exception as e:
                errors.append((cbs_id, str(e)))
                print(f"FOUT: {e}")

    print(f"\n{'='*50}")
    print(f"Totaal:     {total}")
    print(f"Gewijzigd:  {len(updates)}")
    print(f"Fouten:     {len(errors)}")

    if updates:
        CATALOGUS.write_text(json.dumps(datasets, ensure_ascii=False, indent=2))
        print(f"\nGeschreven naar {CATALOGUS}")
    else:
        print("\nNiets gewijzigd — geen schrijfactie.")

    if errors:
        print("\nFouten:")
        for cbs_id, msg in errors:
            print(f"  {cbs_id}: {msg}")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
