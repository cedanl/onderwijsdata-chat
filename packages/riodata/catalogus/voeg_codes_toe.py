"""
voeg_codes_toe.py — Voeg _codes legenda toe aan DUO-catalogusrecords.

Dit script voegt een `_codes` veld toe aan entries in duo_resources.json voor
datasets waarvan de numerieke kolomcodes zijn geverifieerd vanuit DUO-documentatie.

Bronnen:
- Functiemix codeboek: https://onderwijsdata.duo.nl/dataset/functiemix
- WEB art. 7.2.2 (MBO-kwalificatieniveaus 1-4)
"""

import json
from pathlib import Path

RESOURCES = Path(__file__).parent.parent / "src" / "riodata" / "data" / "duo_resources.json"

# Bekende code-mappings per dataset (gematcht op 'bron'-veld).
# Alleen opgenomen wanneer geverifieerd via DUO-documentatie of wetgeving.
BEKENDE_CODES: dict[str, dict[str, dict[str, str]]] = {
    # --- Functiemix (bron: DUO functiemix README / codeboek) ---
    "Functiemix": {
        "ONDERWIJSSECTOR": {
            "1": "PO",
            "2": "VO",
            "3": "MBO",
            "4": "HBO",
        },
        "EENPITTER": {
            "0": "nee",
            "1": "ja",
        },
        "RANDSTAD": {
            "0": "nee",
            "1": "ja",
        },
        "CATEGORIE_BESTUUROMVANG": {
            "1": "klein",
            "2": "middel",
            "3": "groot",
        },
        "VERTICALE_SCHOLENGEMEENSCHAP": {
            "0": "nee",
            "1": "ja",
        },
    },
    # --- MBO-niveau codes (bron: WEB art. 7.2.2, Wet Educatie en Beroepsonderwijs) ---
    "Instromende mbo-studenten": {
        "NIVEAU": {
            "1": "Entreeopleiding",
            "2": "Basisberoepsopleiding",
            "3": "Vakberoepsopleiding",
            "4": "Middenkaderopleiding/Specialistenopleiding",
        },
    },
    "Mbo-studenten per instelling": {
        "NIVEAU": {
            "1": "Entreeopleiding",
            "2": "Basisberoepsopleiding",
            "3": "Vakberoepsopleiding",
            "4": "Middenkaderopleiding/Specialistenopleiding",
        },
    },
    "Mbo-studenten per sectorkamer en leerweg": {
        "NIVEAU": {
            "1": "Entreeopleiding",
            "2": "Basisberoepsopleiding",
            "3": "Vakberoepsopleiding",
            "4": "Middenkaderopleiding/Specialistenopleiding",
        },
    },
}


def main() -> None:
    with open(RESOURCES, encoding="utf-8") as f:
        data: list[dict] = json.load(f)

    changed = 0
    for entry in data:
        bron = entry.get("bron", "")
        if bron in BEKENDE_CODES:
            codes = BEKENDE_CODES[bron]
            entry["_codes"] = codes
            print(f"  {bron}: {list(codes.keys())}")
            changed += 1

    with open(RESOURCES, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\n{changed} entries bijgewerkt")


if __name__ == "__main__":
    main()
