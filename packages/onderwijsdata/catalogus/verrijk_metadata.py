"""
Verrijkt alle CBS-entries in cbs_datasets.json met:
  _dimensies, _meetwaarden (officiële keys), _meetwaarden_details,
  _geo_niveau, _perioden_formaat

via echte CBS API-calls. Idempotent: entries die al _dimensies hebben
worden overgeslagen.

Gebruik:
  uv run python catalogus/verrijk_metadata.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from onderwijsdata import client
from helpers import meetwaarden_uit_properties

DATASETS    = Path(__file__).parent.parent / "data/02-prepared/cbs_datasets.json"
AI_DATASETS = Path(__file__).parent.parent / "data/02-prepared/cbs_datasets_ai.json"

# Dimensie-types die als "dimensie" (as) tellen — Topic en TopicGroup zijn meetwaarden
DIM_TYPES = {"Dimension", "GeoDimension", "TimeDimension"}

# Vaste volgorde van geo-niveaus in de output
GEO_VOLGORDE = ["landelijk", "corop", "provincie", "gemeente", "landsdeel"]


def bepaal_geo_niveau(dataset_id: str, props: list[dict]) -> list[str]:
    """
    Detecteer geo-niveaus via de regio-dimensie.
    Zoekt naar een property met 'regio' in de Key (case-insensitive),
    haal de sleutels op en leid niveaus af uit de key-prefixen.
    """
    # Zoek de eerste property met 'regio' in de Key
    geo_prop = next(
        (p for p in props if "regio" in p.get("Key", "").lower()),
        None,
    )
    if geo_prop is None:
        return []

    try:
        regio_keys = client.dimension(dataset_id, geo_prop["Key"])
        time.sleep(0.1)
        niveaus: set[str] = set()
        for key in regio_keys:
            if key == "NL01":
                niveaus.add("landelijk")
            elif key.startswith("GM"):
                niveaus.add("gemeente")
            elif key.startswith("PV"):
                niveaus.add("provincie")
            elif key.startswith("CR"):
                niveaus.add("corop")
            elif key.startswith("LD"):
                niveaus.add("landsdeel")
        return [n for n in GEO_VOLGORDE if n in niveaus]
    except Exception as e:
        print(f"    FOUT bij geo-dimensie ophalen ({geo_prop['Key']}): {e}")
        return []


def bepaal_perioden_formaat(dataset_id: str, dims: list[str]) -> list[str]:
    """Detecteer periode-formaat via echte CBS Perioden-dimensiewaarden."""
    if "Perioden" not in dims:
        return []
    try:
        waarden = client.dimension(dataset_id, "Perioden")
        time.sleep(0.05)
        eerste_key = next(iter(waarden), None)
        if not eerste_key:
            return []
        for fmt in ("SJ", "JJ", "KW", "MM"):
            if fmt in eerste_key:
                return [fmt]
        return []
    except Exception:
        return []


def herbereken_perioden(datasets: list[dict]) -> int:
    """
    Tweede pass: update _perioden_formaat voor entries die al verrijkt zijn
    maar nog de heuristische waarde hebben (van vóór deze fix).
    Retourneert het aantal gewijzigde entries.
    """
    kandidaten = [
        e for e in datasets
        if "_dimensies" in e and "Perioden" in e.get("_dimensies", [])
    ]
    print(f"\nFase 2: perioden-formaat herberekenen voor {len(kandidaten)} entries met Perioden-dimensie...")
    changed = 0
    for n, entry in enumerate(kandidaten, 1):
        dataset_id = entry["_cbs_id"]
        pf = bepaal_perioden_formaat(dataset_id, entry["_dimensies"])
        old = entry.get("_perioden_formaat", [])
        label = f"[{n}/{len(kandidaten)}] {dataset_id}"
        if pf != old:
            print(f"  {label}: {old} → {pf}")
            entry["_perioden_formaat"] = pf
            changed += 1
        else:
            print(f"  {label}: {pf} (ongewijzigd)")
    return changed


def verrijk_entry(entry: dict, i: int, total: int) -> bool:
    """
    Verrijk een entry via CBS API.
    Retourneert True als de entry is gewijzigd, False als overgeslagen.
    """
    dataset_id = entry["_cbs_id"]

    if "_dimensies" in entry and "_meetwaarden_details" in entry:
        print(f"[{i}/{total}] {dataset_id} (overgeslagen, al verrijkt)")
        return False

    print(f"[{i}/{total}] {dataset_id}", end="", flush=True)

    try:
        props = client.properties(dataset_id)
        time.sleep(0.1)
    except Exception as e:
        print(f" FOUT: {e}")
        # Laat _dimensies absent zodat de entry opnieuw geprobeerd wordt bij de
        # volgende run. Alleen bij succesvolle API-call (dims=[]) slaan we op.
        return False

    dims   = [p["Title"].strip() for p in props if p.get("Type") in DIM_TYPES]
    topics, details = meetwaarden_uit_properties(props)

    geo_niveau       = bepaal_geo_niveau(dataset_id, props)
    perioden_formaat = bepaal_perioden_formaat(dataset_id, dims)

    entry["_dimensies"]        = dims
    entry["_meetwaarden"]      = topics
    entry["_meetwaarden_details"] = details
    entry["_geo_niveau"]       = geo_niveau
    entry["_perioden_formaat"] = perioden_formaat

    print(f"  dims={len(dims)}, topics={len(topics)}, geo={geo_niveau}")
    return True


def main():
    with open(DATASETS, encoding="utf-8") as f:
        datasets = json.load(f)
    print(f"Catalogus geladen: {len(datasets)} entries\n")

    changed = 0
    for i, entry in enumerate(datasets, 1):
        if verrijk_entry(entry, i, len(datasets)):
            changed += 1

    print(f"\n{changed} entries bijgewerkt")

    with open(DATASETS, "w", encoding="utf-8") as f:
        json.dump(datasets, f, ensure_ascii=False, indent=2)
    print(f"Opgeslagen: {DATASETS}")

    # ── Fase 2: herbereken perioden-formaat via echte CBS API ─────────────────
    pf_changed = herbereken_perioden(datasets)
    if pf_changed:
        with open(DATASETS, "w", encoding="utf-8") as f:
            json.dump(datasets, f, ensure_ascii=False, indent=2)
        print(f"Perioden-formaat bijgewerkt voor {pf_changed} entries — {DATASETS} opgeslagen")

    # ── Propageer naar AI-JSON ────────────────────────────────────────────────
    with open(AI_DATASETS, encoding="utf-8") as f:
        ai_datasets = json.load(f)

    base_by_id = {e["_cbs_id"]: e for e in datasets}
    PROPAGEER  = ("_dimensies", "_meetwaarden", "_meetwaarden_details", "_geo_niveau", "_perioden_formaat")

    ai_changed = 0
    for entry in ai_datasets:
        base = base_by_id.get(entry["_cbs_id"])
        if not base:
            continue
        for veld in PROPAGEER:
            if veld in base:
                entry[veld] = base[veld]
        # Voeg geo-tags toe aan de tags-lijst
        geo  = base.get("_geo_niveau", [])
        tags = entry.get("tags", [])
        for geo_tag in ("corop", "provincie", "gemeente"):
            if geo_tag in geo and geo_tag not in tags:
                tags.append(geo_tag)
        entry["tags"] = tags
        ai_changed += 1

    with open(AI_DATASETS, "w", encoding="utf-8") as f:
        json.dump(ai_datasets, f, ensure_ascii=False, indent=2)
    print(f"Opgeslagen: {AI_DATASETS} ({ai_changed} entries bijgewerkt)")

    # ── Verificatie ───────────────────────────────────────────────────────────
    with_dims = [e for e in ai_datasets if e.get("_dimensies")]
    with_geo  = [e for e in ai_datasets if e.get("_geo_niveau") is not None]
    print(f"\nVerificatie:")
    print(f"  Met _dimensies:  {len(with_dims)}/{len(ai_datasets)}")
    print(f"  Met _geo_niveau: {len(with_geo)}/{len(ai_datasets)}")


if __name__ == "__main__":
    main()
