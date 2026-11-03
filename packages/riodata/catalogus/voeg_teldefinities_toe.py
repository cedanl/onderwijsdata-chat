"""
voeg_teldefinities_toe.py — Voeg volledige brontekst, teldefinitie en publicatieregels
toe aan DUO-catalogusrecords.

Haalt per dataset `package_show` op van CKAN, bewaart de volledige `notes` als
`_details` en parseert er `_teldefinitie`, `_publicatieregels`, `_zoekkaart` en
`_notes_provenance` uit (zie riodata.duo_notes). Bestaande velden blijven ongemoeid.

Gebruik:
  uv run python catalogus/voeg_teldefinities_toe.py
  uv run python catalogus/voeg_teldefinities_toe.py --limit 5
"""
import argparse
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from riodata.duo_notes import details_from_pkg  # noqa: E402

RESOURCES = Path(__file__).parent.parent / "src" / "riodata" / "data" / "duo_resources.json"
CKAN = "https://onderwijsdata.duo.nl/api/3/action/package_show"


def update_duo(path: Path, limit: int | None = None) -> int:
    """Verwerk duo_resources.json. Geeft het aantal bijgewerkte entries."""
    data = json.loads(path.read_text(encoding="utf-8"))
    bijgewerkt = 0
    with httpx.Client(timeout=30) as client:
        for entry in data[:limit]:
            ckan_id = entry.get("_ckan_id")
            if not ckan_id:
                continue
            r = client.get(CKAN, params={"id": ckan_id})
            r.raise_for_status()
            body = r.json()
            if not body.get("success"):
                print(f"  ! {ckan_id}: CKAN success=false, overgeslagen")
                continue
            entry.update(details_from_pkg(body["result"]))
            status = entry["_notes_provenance"]["parse_status"]
            fouten = entry["_notes_provenance"]["parse_fouten"]
            print(f"  {ckan_id}: {status}" + (f" — {fouten}" if fouten else ""))
            bijgewerkt += 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return bijgewerkt


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    print(f"Teldefinities ophalen voor {RESOURCES}…\n")
    n = update_duo(RESOURCES, args.limit)
    print(f"\nKlaar: {n} entries bijgewerkt → {RESOURCES}")
