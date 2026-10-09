#!/usr/bin/env python
"""
Genereer data/sector_cluster_mapping.json op basis van actuele UWV-clusters.

Gebruik:
    uv run scripts/refresh_sector_mapping.py

Het script:
  1. Laadt alle unieke BEROEPENCLUSTER-namen uit de UWV Open Match dataset
  2. Vraagt de LLM (via litellm) per indeling (hbo/wo-onderdelen en mbo-sectoren) welke clusters bij
     welke sector passen: één aanroep per indeling, met alle sectoren van die indeling in de prompt
  3. Schrijft het resultaat naar data/sector_cluster_mapping.json: in `_manifest` de datum, de herkomst
     (een LLM-classificatie, niet van UWV) en het model (#460), in `_indelingen` welke sector bij welke
     indeling hoort, en elke sector, ook zonder clusters (#455)

Draai dit opnieuw als UWV een nieuw snapshot publiceert.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Voeg projectroot toe zodat imports werken
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import litellm
from riodata import uwv

from core.config import MODEL
from data.arbeidsmarkt import MAPPING_HERKOMST

OUTPUT = ROOT / "data" / "sector_cluster_mapping.json"

# Indeling → sector → korte omschrijving voor de prompt. De sleutels zijn `_indelingen` in de mapping:
# een test houdt ze gelijk, zodat een refresh geen sector of indeling wist (#455).
SECTOREN: dict[str, dict[str, str]] = {
    "hbo/wo": {
        "ECONOMIE": "Economie, bedrijfskunde, financiën, accountancy, marketing, logistiek",
        "GEDRAG_EN_MAATSCHAPPIJ": "Gedrag en maatschappij, psychologie, sociaal werk, HR, personeel",
        "GEZONDHEIDSZORG": "Gezondheidszorg, verpleging, verzorging, medisch, farmacie",
        "LANDBOUW_EN_NATUURLIJKE_OMGEVING": "Landbouw, veehouderij, tuinbouw, groen, bos- en natuurbeheer",
        "NATUUR": "Natuurwetenschappen, wiskunde, informatica, scheikunde, laboratoriumonderzoek",
        "ONDERWIJS": "Onderwijs, pedagogiek, coaching, training",
        "RECHT": "Recht, rechtspraak, juridische dienstverlening, fiscaliteit, openbaar bestuur",
        "SECTOROVERSTIJGEND": "Brede opleidingen: organisatieadvies, beleid, bestuur, communicatie, onderzoek",
        "TAAL_EN_CULTUUR": "Taal, cultuur, communicatie, media, design, journalistiek",
        "TECHNIEK": "Techniek, ICT, bouw, elektrotechniek, werktuigbouw, data, software",
    },
    "mbo": {
        "Afbouw, hout en onderhoud": "Schilderen, stukadoren, timmeren, meubelmaken, gebouwonderhoud",
        "Ambacht, laboratorium en gezondheidstechniek": "Ambachten, laboratorium, tandtechniek, optiek, orthopedie",
        "Bouw en infra": "Burgerlijke en utiliteitsbouw, wegenbouw, infrastructuur",
        "Economie en administratie": "Administratie, boekhouding, secretariaat, juridisch, personeelszaken",
        "Entree": "Instapniveau: eenvoudig uitvoerend werk in productie, verkoop, logistiek, schoonmaak",
        "Handel en ondernemerschap": "Verkoop, winkel, groothandel, inkoop, ondernemerschap",
        "Horeca en bakkerij": "Koken, bediening, hotel, bakkerij",
        "Informatie en communicatietechnologie": "ICT-beheer, netwerken, softwareontwikkeling, servicedesk",
        "Media en vormgeving": "Mediavormgeving, grafische techniek, audiovisueel, fotografie, mode",
        "Mobiliteit en voertuigen": "Auto-, motor- en fietstechniek, carrosserie, mobiele werktuigen",
        "Techniek en procesindustrie": "Elektrotechniek, werktuigbouw, installatietechniek, metaal, procesindustrie",
        "Toerisme en recreatie": "Reizen, toerisme, recreatie, evenementen",
        "Transport, scheepvaart en logistiek": "Wegvervoer, chauffeurs, scheepvaart, havens, logistiek, magazijn",
        "Uiterlijke verzorging": "Kapper, schoonheidsspecialist, pedicure, nagelstyling",
        "Veiligheid en sport": "Beveiliging, politie, brandweer, defensie, sport en bewegen",
        "Voedsel, natuur en leefomgeving": "Landbouw, dierverzorging, groen, voedingsindustrie, natuur en milieu",
        "Zorg en welzijn": "Verpleging, verzorging, sociaal werk, kinderopvang, gehandicaptenzorg",
    },
}


def laad_clusters() -> list[str]:
    print("UWV-data laden...", flush=True)
    df = uwv.load("latest", rec_type="Vacature")
    clusters = sorted(df["BEROEPENCLUSTER"].dropna().unique().tolist())
    print(f"  {len(clusters)} unieke beroepencluster-namen gevonden", flush=True)
    return clusters


def _prompt(indeling: str, sectoren: dict[str, str], clusters: list[str]) -> str:
    sector_blok = "\n".join(f"- {k}: {v}" for k, v in sectoren.items())
    cluster_blok = "\n".join(f"- {c}" for c in clusters)
    voorbeeld = next(iter(sectoren))
    return f"""Je krijgt een lijst van Nederlandse beroepencluster-namen uit de UWV Open Match dataset
en de opleidingssectoren van de indeling {indeling}. Bepaal voor elk beroepencluster bij welke sectoren het past.

Sectoren ({indeling}):
{sector_blok}

Beroepencluster-namen:
{cluster_blok}

Geef je antwoord als JSON-object waarbij elke sleutel precies een sectornaam uit de lijst hierboven is
(bijv. "{voorbeeld}") en de waarde een lijst van beroepencluster-namen die daarbij passen.
Een cluster mag bij meerdere sectoren horen.
Clusters die bij geen enkele sector passen, laat je weg.
Antwoord uitsluitend met het JSON-object, geen uitleg."""


def lees_antwoord(raw: str) -> dict[str, list[str]]:
    """Het JSON-object uit het antwoord van het model, ook binnen markdown code fences."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].removeprefix("json")
    return json.loads(raw.strip())


def classificeer_via_llm(indeling: str, sectoren: dict[str, str], clusters: list[str]) -> dict[str, list[str]]:
    print(f"LLM classificeert clusters voor {indeling}...", flush=True)
    response = litellm.completion(
        model=MODEL,
        messages=[{"role": "user", "content": _prompt(indeling, sectoren, clusters)}],
        max_tokens=16000,
    )
    inhoud = response.choices[0].message.content
    if not inhoud:
        raise RuntimeError(f"Het model gaf geen antwoord voor {indeling}")
    return lees_antwoord(inhoud)


def onbekende_sectoren(per_indeling: dict[str, dict[str, list[str]]]) -> list[str]:
    """Sectoren uit de antwoorden die hun indeling niet kent; bouw_mapping laat ze weg."""
    return sorted(s for i, antwoord in per_indeling.items() for s in antwoord if s not in SECTOREN[i])


def onbekende_clusters(per_indeling: dict[str, dict[str, list[str]]], clusters: list[str]) -> list[str]:
    """Clusternamen uit de antwoorden die UWV niet kent; bouw_mapping laat ze weg."""
    bekend = set(clusters)
    return sorted({c for antwoord in per_indeling.values() for cs in antwoord.values() for c in cs if c not in bekend})


def bouw_mapping(
    kop: dict[str, str], per_indeling: dict[str, dict[str, list[str]]], clusters: list[str]
) -> dict[str, Any]:
    """Het mappingbestand: `_manifest`, `_indelingen` en elke sector, een lege lijst als het model er
    niets bij zette. Onbekende sectoren en clusters die UWV niet kent, vallen weg."""
    bekend = set(clusters)
    per_sector = {
        sector: [c for c in per_indeling.get(indeling, {}).get(sector, []) if c in bekend]
        for indeling, sectoren in SECTOREN.items()
        for sector in sectoren
    }
    return {"_manifest": kop, "_indelingen": {i: list(s) for i, s in SECTOREN.items()}, **per_sector}


def manifest() -> dict[str, str]:
    """Wanneer, waarvan en door welk model de mapping gemaakt is; de tool toont herkomst, versie en model."""
    return {
        "bijgewerkt": date.today().isoformat(),
        "bron": "UWV Open Match, momentopname mei 2023 (BEROEPENCLUSTER)",
        "script": "scripts/refresh_sector_mapping.py",
        "herkomst": MAPPING_HERKOMST,
        "model": MODEL,
    }


def main(output: Path = OUTPUT) -> None:
    clusters = laad_clusters()
    per_indeling = {i: classificeer_via_llm(i, s, clusters) for i, s in SECTOREN.items()}
    if onbekend := onbekende_sectoren(per_indeling):
        print(f"  Waarschuwing: onbekende sectoren genegeerd: {onbekend}", flush=True)
    if onbekend := onbekende_clusters(per_indeling, clusters):
        print(f"  Waarschuwing: onbekende clusters genegeerd: {onbekend}", flush=True)

    mapping = bouw_mapping(manifest(), per_indeling, clusters)
    output.write_text(json.dumps(mapping, indent=2, ensure_ascii=False))
    print(f"\nGeschreven naar {output}", flush=True)
    for indeling, sectoren in SECTOREN.items():
        for sector in sectoren:
            print(f"  {indeling} · {sector}: {len(mapping[sector])} clusters", flush=True)


if __name__ == "__main__":
    main()
