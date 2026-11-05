"""
Haalt alle CBS onderwijsdatasets op en exporteert ze als data.json
compatibel met cedanl/overzicht-landelijke-databronnen.
"""
import json
import httpx
from helpers import _infer_geo_niveau, _infer_perioden_formaat, _KALENDERJAAR_THEMAS, meetwaarden_uit_properties

CATALOG = "https://opendata.cbs.nl/ODataCatalog"
API     = "https://opendata.cbs.nl/ODataApi/OData"

# Onderwijsthema IDs in de CBS catalogus
ONDERWIJS_THEMES = [
    # Originele themes
    352, 353, 354, 355, 356, 357, 358,
    359, 360, 361, 362, 363, 364, 365,
    366, 367, 368, 369, 370, 371, 372, 373,
    # Nieuwe themes (2024+)
    376,                               # Voortijdig schoolverlaters
    480, 481, 482,                     # Onderwijs en arbeidsmarkt, VSV
    319, 320, 321, 322, 324,           # Regionaal onderwijs
    905, 906, 907, 909,                # Onderwijs, PO, VO
    912, 913, 914, 915, 916,           # MBO
    917, 918, 919, 920,                # Hoger onderwijs
    922, 924, 925, 926, 928, 929, 934, # Volwasseneneducatie, Financiering, AM, VSV
]

# CBS sectie → categorie mapping (naar data.json conventies)
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


def fetch_dataset_ids():
    """Haal alle unieke dataset-IDs op via onderwijsthema's."""
    ids_per_theme = {}
    for theme_id in ONDERWIJS_THEMES:
        rows = get(f"{CATALOG}/Tables_Themes", **{"$filter": f"ThemeID eq {theme_id}", "$select": "TableIdentifier,ThemeID"})
        for row in rows:
            ids_per_theme.setdefault(row["TableIdentifier"], theme_id)
    print(f"  {len(ids_per_theme)} unieke datasets gevonden")
    return ids_per_theme


def fetch_theme_names():
    """Haal thenaam op per theme ID."""
    rows = get(f"{CATALOG}/Themes")
    return {r["ID"]: r["Title"] for r in rows}


def fetch_table_info(dataset_id):
    """Haal metadata op voor één dataset."""
    rows = get(f"{API}/{dataset_id}/TableInfos")
    return rows[0] if rows else {}


def fetch_properties(dataset_id):
    """Haal dimensies en meetwaarden (officiële keys + details) op."""
    rows = get(f"{API}/{dataset_id}/DataProperties")
    dims = [r["Title"] for r in rows if r.get("Type") == "Dimension"]
    topics, details = meetwaarden_uit_properties(rows)
    return dims, topics, details


def to_data_json_entry(dataset_id, info, dims, topics, theme_name, details=None):
    """Converteer CBS metadata naar data.json formaat."""
    title      = info.get("Title", "").strip()
    freq       = info.get("Frequency", "").strip() or "Jaarlijks"
    period_str = info.get("Period", "").strip()
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

    archief = "stopgezet" in freq.lower() or (bool(modified) and modified < "2021-01-01")

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
        "_archief":           archief,
        "_laatste_update":    modified or None,
        "_dimensies":         dims,
        "_meetwaarden":       topics,
        "_meetwaarden_details": details,
        "_perioden_formaat":  _infer_perioden_formaat(freq, theme_name),
        "_geo_niveau":        _infer_geo_niveau(title, dims),
    }


def main():
    print("Stap 1: Dataset IDs ophalen...")
    ids_per_theme = fetch_dataset_ids()

    print("Stap 2: Themanamen ophalen...")
    theme_names = fetch_theme_names()

    entries = []
    total = len(ids_per_theme)

    print(f"Stap 3: Metadata ophalen voor {total} datasets...")
    for i, (dataset_id, theme_id) in enumerate(ids_per_theme.items(), 1):
        theme_name = theme_names.get(theme_id, "Onbekend")
        print(f"  [{i}/{total}] {dataset_id} ({theme_name})")
        try:
            info        = fetch_table_info(dataset_id)
            dims, topics, details = fetch_properties(dataset_id)
            entry       = to_data_json_entry(dataset_id, info, dims, topics, theme_name, details)
            entries.append(entry)
        except Exception as e:
            print(f"    FOUT: {e}")

    output = "data/02-prepared/cbs_datasets.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"\nKlaar: {len(entries)} entries opgeslagen in {output}")
    print("Dit bestand is compatibel met cedanl/overzicht-landelijke-databronnen/docs/data.json")


if __name__ == "__main__":
    main()
