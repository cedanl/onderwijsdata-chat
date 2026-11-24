"""
Check alle datasets in de catalogus tegen CBS TableInfos en update _laatste_update en periode.
Schrijft alleen terug als er iets veranderd is.

`periode` is de tekst die CBS bij de tabel zet; die komt uit dezelfde aanroep als de wijzigingsdatum. Zonder deze
controle liep de tekst achter op de tabel zodra CBS een periode toevoegde (#1070). Zet CBS de tekst zelf niet bij
(de tabel heeft een nieuwere periode dan de tekst zegt), dan volgt de tekst de perioden van de tabel (`bij_tabel`).
"""
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from onderwijsbronnen.cbs import periode

CATALOGUS = Path("data/02-prepared/cbs_datasets_ai.json")


def bronvelden(tableinfo: dict) -> dict[str, str]:
    """De velden van een catalogusrecord die CBS zelf bijhoudt, uit de TableInfos-rij; een leeg veld ontbreekt."""
    velden = {
        "_laatste_update": (tableinfo.get("Modified") or "")[:10],
        "periode": (tableinfo.get("Period") or "").strip(),
    }
    return {naam: waarde for naam, waarde in velden.items() if waarde}


def werk_bij(ds: dict, velden: dict[str, str]) -> list[str]:
    """Zet de gewijzigde bronvelden in het record; geeft de namen van wat veranderde."""
    gewijzigd = [naam for naam, waarde in velden.items() if ds.get(naam) != waarde]
    ds.update({naam: velden[naam] for naam in gewijzigd})
    return gewijzigd


def fetch_bronvelden(client: httpx.Client, cbs_id: str) -> dict[str, str]:
    url = f"https://opendata.cbs.nl/ODataApi/OData/{cbs_id}/TableInfos"
    r = client.get(url, params={"$format": "json"}, timeout=30)
    r.raise_for_status()
    value = r.json().get("value", [])
    return bronvelden(value[0]) if value else {}


def fetch_periodelabels(client: httpx.Client, cbs_id: str) -> list[str]:
    url = f"https://opendata.cbs.nl/ODataApi/OData/{cbs_id}/Perioden"
    r = client.get(url, params={"$format": "json"}, timeout=30)
    r.raise_for_status()
    return [rij["Title"] for rij in r.json().get("value", []) if rij.get("Title")]


def bronvelden_van(client: httpx.Client, ds: dict) -> dict[str, str]:
    """De bronvelden van een record; de periodetekst volgt de tabel als CBS hem niet bijhoudt.

    Alleen een actuele tabel met tijddimensie: een gearchiveerde tabel krijgt geen nieuwe periode meer.
    """
    velden = fetch_bronvelden(client, ds["_cbs_id"])
    if ds.get("_archief") or "Perioden" not in (ds.get("_dimensies") or ["Perioden"]):
        return velden
    tekst = velden.get("periode") or ds.get("periode") or ""
    velden["periode"] = periode.bij_tabel(tekst, fetch_periodelabels(client, ds["_cbs_id"]))
    return {naam: waarde for naam, waarde in velden.items() if waarde}


def main():
    datasets = json.loads(CATALOGUS.read_text())
    total = len(datasets)

    updates = []
    errors = []

    with httpx.Client() as client:
        for i, ds in enumerate(datasets, 1):
            cbs_id = ds["_cbs_id"]
            print(f"[{i:3}/{total}] {cbs_id:<14}", end=" ", flush=True)
            try:
                gewijzigd = werk_bij(ds, bronvelden_van(client, ds))
                if gewijzigd:
                    updates.append((cbs_id, gewijzigd))
                    print(f"{', '.join(gewijzigd)}  ← GEWIJZIGD")
                else:
                    print(f"{ds.get('_laatste_update')}  ✓")
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
