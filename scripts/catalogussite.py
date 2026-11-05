#!/usr/bin/env python
"""
De bestanden van de catalogussites die niet uit een catalogusscript komen, naar `packages/onderwijsbronnen/docs/<site>/`
(#887, #910).

Gebruik:
    python scripts/catalogussite.py      # na catalogus/cbs/bouw_artefact.py en catalogus/rio/exporteer_site.py

Er zijn twee sites: `cbs` (de CBS-catalogus) en `rio` (RIO, DUO, ROA, UWV, Inspectie en SBB; de naam komt van het
oude pakket riodata). Ze staan in `packages/onderwijsbronnen/docs/cbs` en `docs/rio`, en de GitHub-mirror publiceert
ze als /catalogus/cbs/ en /catalogus/rio/ op zijn Pages-site (.github/workflows/docs.yml). Dit script doet wat de stap
"Kopieer en flatten voorbeelden" in de update-catalogus-workflow van de oude pakketrepo's deed: het voorbeelden-
manifest (`voorbeelden/<site>/manifest.json`) wordt `docs/<site>/voorbeelden.json`, elke plot en elke interpretatie uit
`voorbeelden/<site>/output` komt plat in `docs/<site>/voorbeelden/`. Een `INTERPRETATIE.md` in een submap krijgt de
naam van die map als voorvoegsel. Voor de rio-site komen daar de ROA- en UWV-catalogus bij. Kopiëren is aanvullend:
wat in `docs/` staat en niet meer in `voorbeelden/<site>/output` voorkomt, blijft staan, net als in de oude workflow.

De CI-job `catalogus:site` draait dit gepland en zet de wijzigingen in een MR (scripts/pakketbot.py).
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAKKET = ROOT / "packages" / "onderwijsbronnen"
# Per site: bestanden uit het pakket die de site daarnaast leest (pad in het pakket → naam in docs/<site>/).
EXTRA_BESTANDEN: dict[str, dict[str, str]] = {
    "cbs": {},
    "rio": {
        "src/onderwijsbronnen/roa/data/roa_resources.json": "roa_data.json",
        "src/onderwijsbronnen/uwv/data/uwv_resources.json": "uwv_data.json",
    },
}


def voorbeeldnaam(bestand: Path) -> str:
    """De platte naam in docs/<site>/voorbeelden: een kale INTERPRETATIE.md krijgt de naam van zijn map ervoor."""
    if bestand.name == "INTERPRETATIE.md":
        return f"{bestand.parent.name}_{bestand.name}"
    return bestand.name


def kopieer_voorbeelden(bron: Path, docs: Path) -> list[Path]:
    """Manifest, plots en interpretaties uit `bron` (voorbeelden/<site>) naar `docs`; geeft de geschreven bestanden."""
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


def kopieer_extra(pakket: Path, docs: Path, bestanden: dict[str, str]) -> list[Path]:
    """De extra catalogusbestanden uit het pakket naar de site."""
    geschreven = []
    for bron, naam in bestanden.items():
        doel = docs / naam
        shutil.copyfile(pakket / bron, doel)
        geschreven.append(doel)
    return geschreven


def main(pakket: Path = PAKKET) -> int:
    for site, extra in EXTRA_BESTANDEN.items():
        docs = pakket / "docs" / site
        geschreven = kopieer_voorbeelden(pakket / "voorbeelden" / site, docs) + kopieer_extra(pakket, docs, extra)
        print(f"{site}: {len(geschreven)} bestanden naar {docs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
