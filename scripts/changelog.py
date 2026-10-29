"""Changelog-fragmenten bij een release samenvoegen in CHANGELOG.md (#797).

    uv run python scripts/changelog.py 2.6.0 --droog              # toont de versiesectie, schrijft niets
    uv run python scripts/changelog.py 2.6.0                      # schrijft CHANGELOG.md, verwijdert de fragmenten
    uv run python scripts/changelog.py 2.6.0 --datum 2026-10-30   # standaard: vandaag

Een MR zet zijn item niet in CHANGELOG.md maar in een eigen bestand `changelog.d/<issuenummer>-<onderwerp>.md`:
een `###`-kopje met bullets, zoals de items in CHANGELOG.md. Zo raken open MR's en de merge train niet meer
hetzelfde bestand.

Bij een release komt `## X.Y.Z — <datum>` direct onder de tekst van "Niet uitgebracht", met de fragmenten op
issuenummer, hoogste bovenaan (zoals het nieuwste item tot nu toe bovenaan kwam). De volgorde hangt niet af van de
git-geschiedenis, dus de droge modus, een ondiepe clone en de echte run geven hetzelfde. Wat nog als `###`-kopje onder
"Niet uitgebracht" staat (de items van vóór #797), komt onder de fragmenten mee; de tekst vóór het eerste kopje blijft
onder "Niet uitgebracht" staan.
"""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHANGELOG = REPO / "CHANGELOG.md"
FRAGMENTEN = REPO / "changelog.d"

NIET_UITGEBRACHT = "## Niet uitgebracht"
VERSIE_RE = re.compile(r"^\d+\.\d+\.\d+$")
FRAGMENTNAAM_RE = re.compile(r"^(?P<issue>\d+)-[a-z0-9-]+\.md$")
# Een fragment hoort onder een versiekop; een kop van niveau 1 of 2 erin breekt de indeling per versie.
HOGE_KOP_RE = re.compile(r"^#{1,2} ", re.MULTILINE)


def lees_fragmenten(map_: Path) -> list[tuple[Path, str]]:
    """Elk fragment met zijn tekst: hoogste issuenummer eerst, bij een gelijk nummer op naam."""
    if not map_.is_dir():
        return []
    fragmenten = []
    for pad in map_.iterdir():
        naam = FRAGMENTNAAM_RE.match(pad.name)
        if not naam:
            raise SystemExit(f"{map_.name}/{pad.name}: geen geldige naam, verwacht <issuenummer>-<onderwerp>.md")
        fragmenten.append((-int(naam["issue"]), pad.name, pad, _fragmenttekst(pad)))
    return [(pad, tekst) for _, _, pad, tekst in sorted(fragmenten)]


def _fragmenttekst(pad: Path) -> str:
    tekst = pad.read_text(encoding="utf-8").strip()
    if not tekst.startswith("### "):
        raise SystemExit(f"{pad.parent.name}/{pad.name}: begint niet met een ###-kopje")
    if HOGE_KOP_RE.search(tekst):
        raise SystemExit(f"{pad.parent.name}/{pad.name}: bevat een kop van niveau 1 of 2; gebruik ### of dieper")
    return tekst


def voeg_samen(changelog: str, versie: str, datum: str, fragmenten: list[str]) -> tuple[str, str]:
    """De nieuwe CHANGELOG.md en de versiesectie die erin kwam."""
    if not VERSIE_RE.match(versie):
        raise SystemExit(f"{versie!r} is geen kale X.Y.Z (zonder v)")
    regels = changelog.splitlines()
    if NIET_UITGEBRACHT not in regels:
        raise SystemExit(f'CHANGELOG.md heeft geen kop "{NIET_UITGEBRACHT}"')
    if any(regel.startswith(f"## {versie} ") for regel in regels):
        raise SystemExit(f"CHANGELOG.md heeft al een kop voor {versie}")
    begin = regels.index(NIET_UITGEBRACHT) + 1
    eind = next((i for i in range(begin, len(regels)) if regels[i].startswith("## ")), len(regels))
    eerste_item = next((i for i in range(begin, eind) if regels[i].startswith("### ")), eind)
    oude_items = "\n".join(regels[eerste_item:eind]).strip()
    if not fragmenten and not oude_items:
        raise SystemExit(f'niets uit te brengen: geen fragmenten en geen items onder "{NIET_UITGEBRACHT}"')
    sectie = "\n\n".join([f"## {versie} — {datum}", *fragmenten, *([oude_items] if oude_items else [])])
    blokken = ["\n".join(regels[:eerste_item]).strip(), sectie, "\n".join(regels[eind:]).strip()]
    return "\n\n".join(blok for blok in blokken if blok) + "\n", sectie


def breng_uit(changelog: Path, map_: Path, versie: str, datum: str, *, droog: bool = False) -> None:
    fragmenten = lees_fragmenten(map_)
    nieuw, sectie = voeg_samen(changelog.read_text(encoding="utf-8"), versie, datum, [t for _, t in fragmenten])
    if droog:
        print(sectie)
        print(f"\nDroge modus: niets geschreven. Zonder --droog verdwijnen {len(fragmenten)} fragment(en):")
        for pad, _ in fragmenten:
            print(f"  {map_.name}/{pad.name}")
        return
    changelog.write_text(nieuw, encoding="utf-8")
    for pad, _ in fragmenten:
        pad.unlink()
    print(f"{changelog.name}: kop {versie} — {datum} met {len(fragmenten)} fragment(en); die zijn verwijderd.")


def _datum(tekst: str) -> str:
    return date.fromisoformat(tekst).isoformat()


def main() -> int:
    ouder = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ouder.add_argument("versie", help="de nieuwe release, kaal X.Y.Z (zonder v)")
    ouder.add_argument("--datum", type=_datum, default=date.today().isoformat(), help="JJJJ-MM-DD, standaard vandaag")
    ouder.add_argument("--droog", action="store_true", help="toon de versiesectie; schrijf en verwijder niets")
    args = ouder.parse_args()
    breng_uit(CHANGELOG, FRAGMENTEN, args.versie, args.datum, droog=args.droog)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
