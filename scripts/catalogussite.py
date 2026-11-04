#!/usr/bin/env python
"""
De bestanden van de catalogussites die niet uit een catalogusscript komen, naar `packages/<pakket>/docs/` (#887).

Gebruik:
    python scripts/catalogussite.py      # na catalogus/bouw_artefact.py (cbs) en catalogus/exporteer_site.py (rio)

De sites zelf (index.html, data.json, ...) staan in `packages/onderwijsdata/docs` en `packages/riodata/docs`. De
GitHub-mirror publiceert ze als /catalogus/cbs/ en /catalogus/rio/ op zijn Pages-site (.github/workflows/docs.yml).
Dit script doet wat de stap "Kopieer en flatten voorbeelden" in de update-catalogus-workflow van de oude pakketrepo's
deed: het voorbeeldenmanifest wordt `docs/voorbeelden.json`, elke plot en elke interpretatie uit `voorbeelden/output`
komt plat in `docs/voorbeelden/`. Een `INTERPRETATIE.md` in een submap krijgt de naam van die map als voorvoegsel.
Voor riodata komen daar de ROA- en UWV-catalogus bij. Kopiëren is aanvullend: wat in `docs/` staat en niet meer in
`voorbeelden/output` voorkomt, blijft staan, net als in de oude workflow.

De CI-job `catalogus:site` draait dit gepland en zet de wijzigingen in een MR (scripts/pakketbot.py).
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAKKETTEN = ROOT / "packages"
# Per pakket: bestanden uit het pakket die de site daarnaast leest (pad in het pakket → naam in docs/).
EXTRA_BESTANDEN: dict[str, dict[str, str]] = {
    "onderwijsdata": {},
    "riodata": {
        "src/riodata/data/roa_resources.json": "roa_data.json",
        "src/riodata/data/uwv_resources.json": "uwv_data.json",
    },
}


def voorbeeldnaam(bestand: Path) -> str:
    """De platte naam in docs/voorbeelden: een kale INTERPRETATIE.md krijgt de naam van zijn map ervoor."""
    if bestand.name == "INTERPRETATIE.md":
        return f"{bestand.parent.name}_{bestand.name}"
    return bestand.name


def kopieer_voorbeelden(pakket: Path) -> list[Path]:
    """Manifest, plots en interpretaties van een pakket naar zijn docs/; geeft de geschreven bestanden terug."""
    bron, docs = pakket / "voorbeelden", pakket / "docs"
    doelmap = docs / "voorbeelden"
    doelmap.mkdir(parents=True, exist_ok=True)
    geschreven = [docs / "voorbeelden.json"]
    shutil.copyfile(bron / "manifest.json", geschreven[0])
    uitvoer = bron / "output"
    for bestand in sorted([*uitvoer.rglob("*.png"), *uitvoer.rglob("*INTERPRETATIE.md")]):
        doel = doelmap / voorbeeldnaam(bestand)
        shutil.copyfile(bestand, doel)
        geschreven.append(doel)
    return geschreven


def kopieer_extra(pakket: Path, bestanden: dict[str, str]) -> list[Path]:
    """De extra catalogusbestanden van een pakket naar zijn docs/."""
    geschreven = []
    for bron, naam in bestanden.items():
        doel = pakket / "docs" / naam
        shutil.copyfile(pakket / bron, doel)
        geschreven.append(doel)
    return geschreven


def main(pakketten: Path = PAKKETTEN) -> int:
    for naam, extra in EXTRA_BESTANDEN.items():
        pakket = pakketten / naam
        geschreven = kopieer_voorbeelden(pakket) + kopieer_extra(pakket, extra)
        print(f"{naam}: {len(geschreven)} bestanden naar {pakket / 'docs'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
