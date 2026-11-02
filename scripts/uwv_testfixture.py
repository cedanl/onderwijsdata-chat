"""Leg de beroepenclusters van de UWV-snapshot vast waarop de mappingtests draaien (#873).

`data/sector_cluster_mapping.json` deelt de beroepenclusters van UWV Open Match in onderwijssectoren in. Of elk cluster
uit de snapshot daarin een plaats heeft, toetst `tests/test_sector_cluster_mapping.py` zonder netwerk tegen deze lijst;
`scripts/steekproef_sector_mapping.py` trekt er de steekproef uit. Draai dit opnieuw bij een nieuwe UWV-snapshot, en
daarna `scripts/refresh_sector_mapping.py`.

    .venv/bin/python scripts/uwv_testfixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

from riodata import uwv

BESTAND = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "uwv" / "beroepenclusters.json"


def lees() -> list[str]:
    """De vastgelegde beroepenclusters van de snapshot, alfabetisch."""
    return json.loads(BESTAND.read_text(encoding="utf-8"))["clusters"]


def main() -> None:
    df = uwv.load("latest", rec_type="Vacature")
    snapshot = df.attrs.get("snapshot", {})
    inhoud = {
        "bron": "UWV Open Match, kolom BEROEPENCLUSTER van de vacatures",
        "peildatum": snapshot.get("peildatum"),
        "bron_url": snapshot.get("bron_url"),
        "sha256": snapshot.get("sha256"),
        "clusters": sorted(df["BEROEPENCLUSTER"].dropna().unique().tolist()),
    }
    BESTAND.parent.mkdir(parents=True, exist_ok=True)
    BESTAND.write_text(json.dumps(inhoud, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(inhoud['clusters'])} beroepenclusters naar {BESTAND}")


if __name__ == "__main__":
    main()
