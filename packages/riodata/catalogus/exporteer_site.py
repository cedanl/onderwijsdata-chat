"""
exporteer_site.py — Schrijf de catalogus voor de GitHub Pages-site vanuit riodata.catalog().

Site en package tonen daarmee dezelfde samengevoegde metadata (bronvelden uit het
basisbestand, verrijking eroverheen) in plaats van elk een eigen bestand.

Gebruik:
  uv run python catalogus/exporteer_site.py            # schrijft naar docs/
  uv run python catalogus/exporteer_site.py --out /tmp/site
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import riodata  # noqa: E402

BESTANDEN = {"data.json": "rio", "duo_data.json": "duo"}


def exporteer(out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    aantallen = {}
    for bestand, source in BESTANDEN.items():
        records = riodata.catalog(source=source)
        (out / bestand).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        aantallen[bestand] = len(records)
    return aantallen


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--out", type=Path, default=Path(__file__).parent.parent / "docs")
    args = p.parse_args()
    for bestand, n in exporteer(args.out).items():
        print(f"{args.out / bestand}: {n} records")
