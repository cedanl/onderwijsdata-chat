"""
Verrijkt _kolommen in duo_resources.json met sample-waarden per kolom.
Nieuwe structuur: {"KOLOM": ["val1", "val2", ...]} i.p.v. ["KOLOM", ...]
"""
import json
from pathlib import Path

import pandas as pd
from riodata import duo as _duo

RESOURCES = Path(__file__).parent.parent / "src/riodata/data/duo_resources.json"
N_SAMPLES = 5
MAX_ROWS = 2000  # laad max 2000 rijen voor sampling


def kolom_samples(df: pd.DataFrame) -> dict:
    result = {}
    for col in df.columns:
        vals = df[col].dropna().unique()[:N_SAMPLES].tolist()
        result[col] = [str(v) for v in vals]
    return result


def load_df(dataset_id: str, resource) -> pd.DataFrame | None:
    try:
        df = _duo.load(dataset_id, resource)
        return df.head(MAX_ROWS)
    except Exception as e:
        print(f"    FOUT laden {dataset_id!r} resource={resource!r}: {e}")
        return None


def verrijk_entry(entry: dict) -> bool:
    dataset_id = entry.get("_ckan_id")
    if not dataset_id:
        return False

    kolommen = entry.get("_kolommen")
    if kolommen is None:
        return False

    naam = entry.get("bron", dataset_id)

    if isinstance(kolommen, list):
        # Single-resource: list → dict met samples
        print(f"  {naam} (single)")
        df = load_df(dataset_id, 0)
        if df is None:
            return False
        entry["_kolommen"] = kolom_samples(df)
        return True

    if isinstance(kolommen, dict):
        # Multi-resource: dict van lists → dict van dicts met samples
        new_kolommen = {}
        for resource_naam, cols in kolommen.items():
            print(f"  {naam} / {resource_naam}")
            df = load_df(dataset_id, resource_naam)
            if df is not None:
                new_kolommen[resource_naam] = kolom_samples(df)
            else:
                # Behoud bestaande kolomnamen als fallback (zonder samples)
                new_kolommen[resource_naam] = {c: [] for c in cols}
        entry["_kolommen"] = new_kolommen
        return True

    return False


def main():
    with open(RESOURCES, encoding="utf-8") as f:
        data = json.load(f)

    print(f"{len(data)} DUO-resources laden...\n")
    changed = 0
    for entry in data:
        if verrijk_entry(entry):
            changed += 1

    with open(RESOURCES, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nKlaar: {changed}/{len(data)} entries bijgewerkt → {RESOURCES}")


if __name__ == "__main__":
    main()
