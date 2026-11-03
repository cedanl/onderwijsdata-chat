"""
Fix #4 — Voeg _geo_niveau toe aan DUO- en RIO-entries.

Gebruik:
  uv run python catalogus/update_geo_niveau.py

Werking:
  - Leest src/riodata/data/duo_resources.json
  - Bepaalt per entry de geografische granulariteitsniveaus op basis van _kolommen
  - Schrijft _geo_niveau terug en vult tags aan
  - Doet hetzelfde voor rio_resources_ai.json (handmatig gekende niveaus)
"""
from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Pure helper (testbaar zonder I/O)
# ---------------------------------------------------------------------------

def _derive_geo_niveau(kolommen: list[str]) -> list[str]:
    """Leid geografische niveaus af uit een lijst kolomnamen.

    Regels (case-insensitive):
      - Begint met GEMEENTE, of bevat GEMEENTENAAM of GEMEENTECODE → 'gemeente'
      - Begint met PROVINCIE, of bevat PROVINCIENAAM → 'provincie'
      - Begint met COROP → 'corop'

    Returns:
        Gesorteerde lijst met unieke niveaus die aanwezig zijn in de kolommen.
        Volgorde: gemeente, provincie, corop (als aanwezig).
    """
    gevonden: list[str] = []

    for kol in kolommen:
        ku = kol.upper()

        if (ku.startswith("GEMEENTE")
                or "GEMEENTENAAM" in ku
                or "GEMEENTECODE" in ku):
            if "gemeente" not in gevonden:
                gevonden.append("gemeente")

        if ku.startswith("PROVINCIE") or "PROVINCIENAAM" in ku:
            if "provincie" not in gevonden:
                gevonden.append("provincie")

        if ku.startswith("COROP"):
            if "corop" not in gevonden:
                gevonden.append("corop")

    # Vaste volgorde voor consistentie
    volgorde = ["gemeente", "provincie", "corop"]
    return [n for n in volgorde if n in gevonden]


# ---------------------------------------------------------------------------
# RIO-niveaus (handmatig, op basis van bekende API-structuur)
# ---------------------------------------------------------------------------

RIO_GEO_NIVEAU: dict[str, list[str]] = {
    "organisatorische-eenheden":      [],          # geen geo-dimensie
    "erkenningen":                     [],
    "contactadressen":                 [],          # plaatsnaam/postcode, maar geen gemeente-kolom
    "onderwijslocaties":               [],          # GPS/postcode, maar geen gemeente-kolom
    "onderwijslocatiegebruiken":       ["gemeente"],# koppeling bevat adres/postcode op gemeenteniveau
    "aangeboden-opleidingen":          [],
    "aangeboden-opleiding-cohorten":   [],
    "opleidingen":                     [],
    "opleidingsfasen":                 [],
    "opleidingsgroepen":               [],
    "opleidingsonderdelen":            [],
    "opleidingserkenningen":           [],
    "onderwijslicenties":              [],
    "examenlicenties":                 [],
}


# ---------------------------------------------------------------------------
# Update-functies
# ---------------------------------------------------------------------------

def _update_tags(tags: list[str], geo_niveaus: list[str]) -> list[str]:
    """Vul tags aan met gevonden geo-niveaus als ze nog ontbreken."""
    for niveau in geo_niveaus:
        if niveau not in tags:
            tags.append(niveau)
    return tags


def update_duo(path: Path) -> int:
    """Verwerk duo_resources.json: voeg _geo_niveau toe. Geeft het aantal gewijzigde entries."""
    data: list[dict] = json.loads(path.read_text(encoding="utf-8"))

    gewijzigd = 0
    for entry in data:
        kolommen = entry.get("_kolommen", [])
        if isinstance(kolommen, list):
            niveaus = _derive_geo_niveau(kolommen)
        elif isinstance(kolommen, dict):
            # Multi-resource: aggregeer over alle resources
            alle_kols: list[str] = []
            for kols in kolommen.values():
                alle_kols.extend(kols)
            niveaus = _derive_geo_niveau(alle_kols)
        else:
            niveaus = []

        oud = entry.get("_geo_niveau")
        entry["_geo_niveau"] = niveaus
        entry["tags"] = _update_tags(entry.get("tags") or [], niveaus)

        if oud != niveaus:
            gewijzigd += 1

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return gewijzigd


def update_rio(path: Path) -> int:
    """Verwerk rio_resources_ai.json: voeg _geo_niveau toe. Geeft het aantal gewijzigde entries."""
    data: list[dict] = json.loads(path.read_text(encoding="utf-8"))

    gewijzigd = 0
    for entry in data:
        rio_resource = entry.get("_rio_resource", "")
        niveaus = RIO_GEO_NIVEAU.get(rio_resource, [])

        oud = entry.get("_geo_niveau")
        entry["_geo_niveau"] = niveaus
        entry["tags"] = _update_tags(entry.get("tags") or [], niveaus)

        if oud != niveaus:
            gewijzigd += 1

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return gewijzigd


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = Path(__file__).parent.parent / "src" / "riodata" / "data"

    duo_path = root / "duo_resources.json"
    rio_path = root / "rio_resources_ai.json"

    n_duo = update_duo(duo_path)
    print(f"DUO: {n_duo} entries bijgewerkt → {duo_path}")

    n_rio = update_rio(rio_path)
    print(f"RIO: {n_rio} entries bijgewerkt → {rio_path}")
