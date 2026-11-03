"""
Fix #3 — Sla per-resource _kolommen op voor multi-resource DUO datasets.

Gebruik:
  uv run python catalogus/update_duo_resource_kolommen.py

Werking:
  - Leest src/riodata/data/duo_resources.json
  - Voor entries met meerdere resources: download de CSV-headers via Range-request
  - Bouwt een dict {resource_naam: [col1, col2, ...]} voor multi-resource entries
  - Single-resource entries: _kolommen blijft een list (backwards-compatible)
  - Schrijft duo_resources.json terug

Fallback bij netwerkfouten: de bestaande _kolommen lijst wordt als placeholder
gebruikt voor resource 0; overige resources krijgen [] als placeholder.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Pure helpers (testbaar zonder netwerk)
# ---------------------------------------------------------------------------

def _parse_csv_header(tekst: str) -> list[str]:
    """Parseer de eerste rij van een CSV-tekstfragment als kolomnamen.

    Ondersteunt komma, puntkomma en tab als separator. Strips aanhalingstekens
    en UTF-8 BOM van kolomnamen.
    """
    if not tekst or not tekst.strip():
        return []

    # Verwijder UTF-8 BOM als aanwezig
    tekst = tekst.lstrip("﻿")

    # Eerste niet-lege regel
    lines = [l for l in tekst.splitlines() if l.strip()]
    if not lines:
        return []

    first_line = lines[0]

    # Detecteer separator: puntkomma, tab of komma
    for sep in (";", "\t", ","):
        if sep in first_line:
            reader = csv.reader(io.StringIO(first_line), delimiter=sep)
            try:
                header = next(reader)
                return [col.strip().strip('"').strip("'") for col in header if col.strip()]
            except StopIteration:
                return []

    # Geen separator gevonden: één kolom
    return [first_line.strip().strip('"')]


def _build_kolommen_dict(
    resources: list[dict],
    fetched_kolommen: dict[str, list[str]],
    fallback: list[str],
) -> dict[str, list[str]]:
    """Bouw de _kolommen-dict voor een multi-resource entry.

    Args:
        resources:         lijst van resource-dicts met tenminste 'naam'
        fetched_kolommen:  dict resource_naam → kolomlijst (resultaat van netwerk)
        fallback:          bestaande _kolommen lijst (voor resource 0 als fallback)

    Returns:
        Dict resource_naam → kolomlijst.
        - Als een resource in fetched_kolommen staat: gebruik die kolommen.
        - Als resource 0 NIET in fetched_kolommen staat: gebruik fallback.
        - Overige niet-opgehaalde resources krijgen [] als placeholder.
    """
    result: dict[str, list[str]] = {}
    for i, resource in enumerate(resources):
        naam = resource["naam"]
        if naam in fetched_kolommen:
            result[naam] = fetched_kolommen[naam]
        elif i == 0:
            result[naam] = list(fallback)
        else:
            result[naam] = []
    return result


# ---------------------------------------------------------------------------
# Netwerk-helpers
# ---------------------------------------------------------------------------

def _fetch_csv_header(url: str, client: httpx.Client, retries: int = 2) -> list[str]:
    """Haal de CSV-headerrij op via een Range-request (eerste 2000 bytes)."""
    for poging in range(retries + 1):
        try:
            resp = client.get(url, headers={"Range": "bytes=0-2000"})
            resp.raise_for_status()
            return _parse_csv_header(resp.text)
        except (httpx.HTTPError, httpx.RequestError) as exc:
            if poging == retries:
                print(f"    [WARN] ophalen mislukt: {url!r}: {exc}", file=sys.stderr)
                return []
            time.sleep(1)
    return []


def _fetch_all_headers(
    resources: list[dict],
    client: httpx.Client,
    max_resources: int = 50,
) -> dict[str, list[str]]:
    """Haal CSV-headers op voor alle resources in de lijst."""
    resultaat: dict[str, list[str]] = {}
    for resource in resources[:max_resources]:
        if resource.get("format", "").upper() not in ("CSV", ""):
            continue
        naam = resource["naam"]
        url = resource.get("url", "")
        if not url:
            continue
        kolommen = _fetch_csv_header(url, client)
        resultaat[naam] = kolommen
    return resultaat


# ---------------------------------------------------------------------------
# Update-functie
# ---------------------------------------------------------------------------

def update_duo(path: Path, gebruik_netwerk: bool = True) -> tuple[int, int]:
    """Verwerk duo_resources.json.

    Returns:
        (aantal_multi_bijgewerkt, aantal_single_ongewijzigd)
    """
    data: list[dict] = json.loads(path.read_text(encoding="utf-8"))

    multi_bijgewerkt = 0
    single_count = 0

    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for entry in data:
            resources: list[dict] = entry.get("_resources", [])
            kolommen_huidig = entry.get("_kolommen", [])

            if len(resources) <= 1:
                # Single-resource: _kolommen blijft een list — geen wijziging
                single_count += 1
                continue

            # Multi-resource: bouw dict-structuur op
            ckan_id = entry.get("_ckan_id", "onbekend")
            print(f"  {ckan_id}: {len(resources)} resources ophalen…")

            if gebruik_netwerk:
                fetched = _fetch_all_headers(resources, client)
            else:
                fetched = {}

            fallback = kolommen_huidig if isinstance(kolommen_huidig, list) else []
            entry["_kolommen"] = _build_kolommen_dict(resources, fetched, fallback)
            multi_bijgewerkt += 1

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return multi_bijgewerkt, single_count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    gebruik_netwerk = "--offline" not in sys.argv

    root = Path(__file__).parent.parent / "src" / "riodata" / "data"
    duo_path = root / "duo_resources.json"

    print(f"Modus: {'netwerk' if gebruik_netwerk else 'offline (fallback)'}")
    multi, single = update_duo(duo_path, gebruik_netwerk=gebruik_netwerk)
    print(f"\nKlaar: {multi} multi-resource entries bijgewerkt, {single} single-resource ongewijzigd")
    print(f"Uitvoer: {duo_path}")
