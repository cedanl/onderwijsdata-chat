"""
Voegt nieuwe CBS onderwijsdatasets toe aan de catalogus en verrijkt alle
entries met _archief en _laatste_update velden.

- _archief: true  → dataset niet meer bijgewerkt (Modified voor 2021 of Stopgezet)
- _archief: false → dataset nog actueel

Gebruik:
  uv run python catalogus/uitbreiden.py
"""
import json
import httpx
from helpers import _infer_geo_niveau, _infer_perioden_formaat, _KALENDERJAAR_THEMAS, meetwaarden_uit_properties

CATALOG     = "https://opendata.cbs.nl/ODataCatalog"
API         = "https://opendata.cbs.nl/ODataApi/OData"
DATASETS    = "data/02-prepared/cbs_datasets.json"
AI_DATASETS = "data/02-prepared/cbs_datasets_ai.json"

# Originele + nieuwe CBS onderwijsthema IDs
ALL_THEMES = [
    # Originele themes
    352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363, 364, 365,
    366, 367, 368, 369, 370, 371, 372, 373,
    # Nieuwe themes (2024+)
    376,                              # Voortijdig schoolverlaters
    480, 481, 482,                    # Onderwijs en arbeidsmarkt, VSV
    319, 320, 321, 322, 324,          # Regionaal onderwijs
    905, 906, 907, 909,               # Onderwijs, PO, VO
    912, 913, 914, 915, 916,          # MBO
    917, 918, 919, 920,               # Hoger onderwijs
    922, 924, 925, 926, 928, 929, 934,# Volwasseneneducatie, Financiering, AM, VSV
]

SECTIE_MAP = {
    "Primair onderwijs":                    ("Primair Onderwijs",                "Studentgegevens & Onderwijs"),
    "Voortgezet onderwijs":                 ("Voortgezet Onderwijs",             "Studentgegevens & Onderwijs"),
    "Middelbaar beroepsonderwijs":          ("Inschrijvingen en Studievoortgang", "Studentgegevens & Onderwijs"),
    "Hoger onderwijs":                      ("Inschrijvingen en Studievoortgang", "Studentgegevens & Onderwijs"),
    "Financiering en uitgaven onderwijs":   ("Financiële gegevens",              "Institutionele Data"),
    "Onderwijs en arbeidsmarkt":            ("Alumni en arbeidsmarkt",            "Studentgegevens & Onderwijs"),
    "Onderwijsniveau bevolking":            ("Algemene data overzichten",         "Algemene Data Overzichten"),
    "Voortijdig schoolverlaters (vsv)":     ("Alumni en arbeidsmarkt",            "Studentgegevens & Onderwijs"),
    "Voortijdig schoolverlaters (VSV)":     ("Alumni en arbeidsmarkt",            "Studentgegevens & Onderwijs"),
    "MBO'ers naar arbeidsmarkt":            ("Alumni en arbeidsmarkt",            "Studentgegevens & Onderwijs"),
    "MBO gediplomeerden naar arbeidsmarkt": ("Alumni en arbeidsmarkt",            "Studentgegevens & Onderwijs"),
    "Wetenschappelijk onderwijs (wo)":      ("Inschrijvingen en Studievoortgang", "Studentgegevens & Onderwijs"),
    "HBO en WO: deeltijd":                  ("Inschrijvingen en Studievoortgang", "Studentgegevens & Onderwijs"),
    "HBO en WO: voltijd":                   ("Inschrijvingen en Studievoortgang", "Studentgegevens & Onderwijs"),
    "MBO Studenten":                        ("Inschrijvingen en Studievoortgang", "Studentgegevens & Onderwijs"),
    "MBO gediplomeerden":                   ("Alumni en arbeidsmarkt",            "Studentgegevens & Onderwijs"),
    "MBO stromen":                          ("Inschrijvingen en Studievoortgang", "Studentgegevens & Onderwijs"),
    "MBO studievoortgang":                  ("Inschrijvingen en Studievoortgang", "Studentgegevens & Onderwijs"),
    "Vo leerlingen":                        ("Voortgezet Onderwijs",             "Studentgegevens & Onderwijs"),
    "VO leerlingen":                        ("Voortgezet Onderwijs",             "Studentgegevens & Onderwijs"),
    "Volwasseneneducatie":                  ("Inschrijvingen en Studievoortgang", "Studentgegevens & Onderwijs"),
    "Woongemeenten; leerlingen, studenten": ("Regionaal",                         "Studentgegevens & Onderwijs"),
    "Onderwijs":                            ("Algemene data overzichten",         "Algemene Data Overzichten"),
}

ONDERWIJSTYPE_MAP = {
    "Primair onderwijs":                    ["PO"],
    "Voortgezet onderwijs":                 ["VO"],
    "Vo leerlingen":                        ["VO"],
    "VO leerlingen":                        ["VO"],
    "Middelbaar beroepsonderwijs":          ["MBO"],
    "MBO Studenten":                        ["MBO"],
    "MBO gediplomeerden":                   ["MBO"],
    "MBO stromen":                          ["MBO"],
    "MBO studievoortgang":                  ["MBO"],
    "MBO'ers naar arbeidsmarkt":            ["MBO"],
    "MBO gediplomeerden naar arbeidsmarkt": ["MBO"],
    "Hoger onderwijs":                      ["HBO", "WO"],
    "Wetenschappelijk onderwijs (wo)":      ["WO"],
    "HBO en WO: deeltijd":                  ["HBO", "WO"],
    "HBO en WO: voltijd":                   ["HBO", "WO"],
    "Financiering en uitgaven onderwijs":   ["Allen"],
    "Onderwijs en arbeidsmarkt":            ["Allen"],
    "Onderwijsniveau bevolking":            ["Allen"],
    "Voortijdig schoolverlaters (vsv)":     ["Allen"],
    "Voortijdig schoolverlaters (VSV)":     ["Allen"],
    "Volwasseneneducatie":                  ["Allen"],
    "Woongemeenten; leerlingen, studenten": ["Allen"],
    "Onderwijs":                            ["Allen"],
}


def get(url, **params):
    params.setdefault("$format", "json")
    r = httpx.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("value", r.json())


def is_archief(modified: str, freq: str) -> bool:
    if "stopgezet" in freq.lower():
        return True
    return bool(modified) and modified < "2021-01-01"


def build_entry(dataset_id, info, dims, topics, theme_name, details=None):
    title      = info.get("Title", "").strip()
    period_str = info.get("Period", "").strip()
    freq       = info.get("Frequency", "").strip() or "Jaarlijks"
    modified   = str(info.get("Modified", ""))[:10]

    details = details or {}
    doel_parts = [title]
    if dims:
        doel_parts.append(f"Uitgesplitst naar: {', '.join(dims[:4])}.")
    if topics:
        titels = [details.get(k, {}).get("title", k) for k in topics[:3]]
        doel_parts.append(f"Meetwaarden: {', '.join(titels)}.")

    categorie, sectie = SECTIE_MAP.get(theme_name, ("Algemene data overzichten", "Algemene Data Overzichten"))
    onderwijstype     = ONDERWIJSTYPE_MAP.get(theme_name, ["Allen"])

    return {
        "leverancier":      "CBS",
        "bron":             title,
        "periode":          period_str,
        "onderwijstype":    onderwijstype,
        "doel":             " ".join(doel_parts),
        "frequentie":       freq,
        "categorie":        categorie,
        "sectie":           sectie,
        "documentatie": {
            "tekst": f"CBS Open Data {dataset_id}",
            "url":   f"https://opendata.cbs.nl/ODataApi/OData/{dataset_id}",
        },
        "repositories":       [],
        "publieke_producten": [],
        "_cbs_id":            dataset_id,
        "_thema":             theme_name,
        "_archief":           is_archief(modified, freq),
        "_laatste_update":    modified or None,
        "_dimensies":         dims,
        "_meetwaarden":       topics,
        "_meetwaarden_details": details,
        "_perioden_formaat":  _infer_perioden_formaat(freq, theme_name),
        "_geo_niveau":        _infer_geo_niveau(title, dims),
    }


def fetch_modified_bulk(ids: list) -> dict:
    """Haal Modified en Frequency op voor een lijst dataset-IDs via de catalogus."""
    result = {}
    batch_size = 20
    for i in range(0, len(ids), batch_size):
        batch = ids[i : i + batch_size]
        filter_str = " or ".join(f"Identifier eq '{tid}'" for tid in batch)
        try:
            rows = get(
                f"{CATALOG}/Tables",
                **{"$filter": filter_str, "$select": "Identifier,Modified,Frequency"},
            )
            for r in rows:
                result[r["Identifier"]] = r
        except Exception as e:
            print(f"  Waarschuwing: bulk ophalen mislukt voor batch {i}: {e}")
    return result


def main():
    # ── 1. Bestaande catalogus laden ──────────────────────────────────────────
    with open(DATASETS) as f:
        existing = json.load(f)
    existing_ids = {e["_cbs_id"] for e in existing}
    print(f"Bestaande catalogus: {len(existing)} datasets")

    # ── 2. Alle thema-IDs doorlopen ───────────────────────────────────────────
    print("Themanamen ophalen...")
    theme_names = {r["ID"]: r["Title"] for r in get(f"{CATALOG}/Themes")}

    print("Dataset-IDs ophalen via alle onderwijsthema's...")
    ids_per_theme: dict[str, int] = {}
    for theme_id in ALL_THEMES:
        rows = get(
            f"{CATALOG}/Tables_Themes",
            **{"$filter": f"ThemeID eq {theme_id}", "$select": "TableIdentifier,ThemeID"},
        )
        for row in rows:
            ids_per_theme.setdefault(row["TableIdentifier"], theme_id)

    # Filter niet-onderwijs thema's (CBS miscategorisaties)
    EXCLUDE_THEMES = {"Toerisme", "Bouwen en wonen", "Hypotheken", "Prijzen"}
    ids_per_theme = {
        tid: theme_id for tid, theme_id in ids_per_theme.items()
        if theme_names.get(theme_id, "") not in EXCLUDE_THEMES
    }

    new_ids = [tid for tid in ids_per_theme if tid not in existing_ids]
    print(f"Gevonden: {len(ids_per_theme)} via thema's | Nieuw: {len(new_ids)}")

    # ── 3. Nieuwe datasets ophalen ────────────────────────────────────────────
    new_entries = []
    for i, dataset_id in enumerate(new_ids, 1):
        theme_id   = ids_per_theme[dataset_id]
        theme_name = theme_names.get(theme_id, "Onderwijs")
        print(f"  [{i:3}/{len(new_ids)}] {dataset_id:<15} ({theme_name})")
        try:
            info_rows = get(f"{API}/{dataset_id}/TableInfos")
            info      = info_rows[0] if info_rows else {}
            props     = get(f"{API}/{dataset_id}/DataProperties")
            dims      = [r["Title"] for r in props if r.get("Type") == "Dimension"]
            topics, details = meetwaarden_uit_properties(props)
            new_entries.append(build_entry(dataset_id, info, dims, topics, theme_name, details))
        except Exception as e:
            print(f"    FOUT: {e}")

    # ── 4. Bestaande entries bijwerken met _archief / _laatste_update ─────────
    print(f"\nModified-datums ophalen voor {len(existing)} bestaande entries...")
    modified_map = fetch_modified_bulk(list(existing_ids))

    updated = 0
    for entry in existing:
        if "_archief" not in entry or "_laatste_update" not in entry:
            cbs_info = modified_map.get(entry["_cbs_id"], {})
            modified = str(cbs_info.get("Modified", ""))[:10]
            freq     = cbs_info.get("Frequency", entry.get("frequentie", ""))
            entry["_archief"]        = is_archief(modified, freq)
            entry["_laatste_update"] = modified or None
            updated += 1

    print(f"  {updated} entries bijgewerkt")

    # ── 5. Samenvoegen en opslaan ─────────────────────────────────────────────
    all_entries = existing + new_entries

    with open(DATASETS, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)

    archief_count = sum(1 for e in all_entries if e.get("_archief"))
    print(f"\ncbs_datasets.json:")
    print(f"  Totaal:  {len(all_entries)}")
    print(f"  Actueel: {len(all_entries) - archief_count}")
    print(f"  Archief: {archief_count}")

    # ── 6. cbs_datasets_ai.json bijwerken ─────────────────────────────────────
    with open(AI_DATASETS) as f:
        ai_existing = json.load(f)

    # Bouw lookup voor bestaande AI-data
    ai_by_id = {e["_cbs_id"]: e for e in ai_existing}

    # Voeg _archief/_laatste_update en nieuwe metadata toe aan bestaande AI-entries
    for entry in ai_existing:
        src = next((e for e in existing if e["_cbs_id"] == entry["_cbs_id"]), None)
        if src:
            entry["_archief"]     = src.get("_archief", False)
            entry["_laatste_update"] = src.get("_laatste_update")
            entry["_dimensies"]        = src.get("_dimensies", [])
            entry["_meetwaarden"]      = src.get("_meetwaarden", [])
            entry["_meetwaarden_details"] = src.get("_meetwaarden_details", {})
            entry["_perioden_formaat"] = src.get("_perioden_formaat", [])
            entry["_geo_niveau"]       = src.get("_geo_niveau", [])
            geo = src.get("_geo_niveau", [])
            tags = entry.get("tags", [])
            for geo_tag in ("corop", "provincie", "gemeente"):
                if geo_tag in geo and geo_tag not in tags:
                    tags.append(geo_tag)
            entry["tags"] = tags

    # Voeg stubs toe voor nieuwe entries (zonder AI-verrijking nog)
    stubs_added = 0
    for entry in new_entries:
        if entry["_cbs_id"] not in ai_by_id:
            ai_existing.append(entry)  # stub: geen samenvatting/tags/voorbeeldvragen
            stubs_added += 1

    with open(AI_DATASETS, "w", encoding="utf-8") as f:
        json.dump(ai_existing, f, ensure_ascii=False, indent=2)

    print(f"\ncbs_datasets_ai.json:")
    print(f"  Totaal:       {len(ai_existing)}")
    print(f"  Stubs (geen AI nog): {stubs_added}")
    print(f"\nDone. Draai nu 'uv run python catalogus/catalogus_ai.py submit' voor AI-verrijking.")


if __name__ == "__main__":
    main()
