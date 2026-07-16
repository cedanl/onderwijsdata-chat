#!/usr/bin/env python
"""
Genereer data/sector_cluster_mapping.json op basis van actuele UWV-clusters.

Gebruik:
    uv run scripts/refresh_sector_mapping.py

Het script:
  1. Laadt alle unieke BEROEPENCLUSTER-namen uit de UWV Open Match dataset
  2. Vraagt de LLM (via litellm) welke clusters bij welke DUO-sector passen
  3. Schrijft het resultaat naar data/sector_cluster_mapping.json

Draai dit opnieuw als UWV een nieuw snapshot publiceert.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Voeg projectroot toe zodat imports werken
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import litellm
from core.config import MODEL
from riodata import uwv

OUTPUT = ROOT / "data" / "sector_cluster_mapping.json"

DUO_SECTOREN = {
    "ECONOMIE": "Economie, bedrijfskunde, recht, financiën, marketing, logistiek",
    "GEZONDHEIDSZORG": "Gezondheidszorg, verpleging, verzorging, medisch, farmacie",
    "TECHNIEK": "Techniek, ICT, bouw, elektrotechniek, werktuigbouw, data, software",
    "ONDERWIJS": "Onderwijs, pedagogiek, coaching, training",
    "GEDRAG_EN_MAATSCHAPPIJ": "Gedrag en maatschappij, psychologie, sociaal werk, HR, personeel",
    "TAAL_EN_CULTUUR": "Taal, cultuur, communicatie, media, design, journalistiek",
}


def laad_clusters() -> list[str]:
    print("UWV-data laden...", flush=True)
    df = uwv.load("latest", rec_type="Vacature")
    clusters = sorted(df["BEROEPENCLUSTER"].dropna().unique().tolist())
    print(f"  {len(clusters)} unieke beroepencluster-namen gevonden", flush=True)
    return clusters


def classificeer_via_llm(clusters: list[str]) -> dict[str, list[str]]:
    sector_blok = "\n".join(f"- {k}: {v}" for k, v in DUO_SECTOREN.items())
    cluster_blok = "\n".join(f"- {c}" for c in clusters)

    prompt = f"""Je krijgt een lijst van Nederlandse beroepencluster-namen uit de UWV Open Match dataset
en een lijst van DUO-opleidingssectoren. Bepaal voor elk beroepencluster bij welke sectoren het past.

DUO-sectoren:
{sector_blok}

Beroepencluster-namen:
{cluster_blok}

Geef je antwoord als JSON-object waarbij elke sleutel een DUO-sectorcode is (bijv. "ECONOMIE")
en de waarde een lijst van beroepencluster-namen die daarbij passen.
Een cluster mag bij meerdere sectoren horen.
Clusters die bij geen enkele sector passen, laat je weg.
Antwoord uitsluitend met het JSON-object, geen uitleg."""

    print("LLM classificeert clusters...", flush=True)
    response = litellm.completion(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=16000,
    )
    raw = response.choices[0].message.content.strip()

    # Strip eventuele markdown code fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def main() -> None:
    clusters = laad_clusters()
    mapping = classificeer_via_llm(clusters)

    # Valideer dat alle sleutels bekende sectoren zijn
    onbekend = [k for k in mapping if k not in DUO_SECTOREN]
    if onbekend:
        print(f"  Waarschuwing: onbekende sectoren genegeerd: {onbekend}", flush=True)
        for k in onbekend:
            del mapping[k]

    OUTPUT.write_text(json.dumps(mapping, indent=2, ensure_ascii=False))
    print(f"\nGeschreven naar {OUTPUT}", flush=True)
    for sector, items in sorted(mapping.items()):
        print(f"  {sector}: {len(items)} clusters", flush=True)


if __name__ == "__main__":
    main()
