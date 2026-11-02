"""Trek de steekproef van 30 beroepenclusters voor de handmatige beoordeling van de sectormapping (#873).

`data/sector_cluster_mapping.json` is een LLM-classificatie zonder validatie. Een mens beoordeelt per cluster in de
steekproef of de sectoren kloppen (kolom `oordeel`: juist of onjuist, met een toelichting), en het aantal juist en
onjuist komt daarna als `validatie` in het manifest. De steekproef komt uit de vastgelegde clusters van de snapshot
(`tests/fixtures/uwv/beroepenclusters.json`) met een vaste seed, dus zonder netwerk en elke keer dezelfde; een test
bewaakt dat het bestand bij de mapping hoort.

    .venv/bin/python scripts/steekproef_sector_mapping.py
"""

from __future__ import annotations

import csv
import io
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.arbeidsmarkt import load_sector_cluster_map, load_sector_indeling
from scripts.uwv_testfixture import lees as snapshotclusters

BESTAND = ROOT / "docs" / "sector-cluster-steekproef.csv"
SEED = 873
AANTAL = 30
KOLOMMEN = ("beroepencluster", "hbo/wo-sectoren", "mbo-sectoren", "oordeel (juist/onjuist)", "toelichting")
_GEEN = "geen"


def steekproef() -> list[str]:
    """30 clusters uit de snapshot, met de vaste seed getrokken en alfabetisch."""
    return sorted(random.Random(SEED).sample(snapshotclusters(), AANTAL))


def _sectoren(cluster: str, indeling: str) -> str:
    per_indeling = load_sector_indeling()
    sectoren = [s for s, cs in load_sector_cluster_map().items() if cluster in cs and per_indeling.get(s) == indeling]
    return ", ".join(sorted(sectoren)) or _GEEN


def als_csv() -> str:
    """De steekproef als CSV (puntkomma, zoals de exports), met lege kolommen voor het oordeel."""
    uit = io.StringIO()
    writer = csv.writer(uit, delimiter=";", lineterminator="\n")
    writer.writerow(KOLOMMEN)
    for cluster in steekproef():
        writer.writerow((cluster, _sectoren(cluster, "hbo/wo"), _sectoren(cluster, "mbo"), "", ""))
    return uit.getvalue()


def main() -> None:
    BESTAND.write_text(als_csv(), encoding="utf-8")
    print(f"{AANTAL} clusters (seed {SEED}) naar {BESTAND}")


if __name__ == "__main__":
    main()
