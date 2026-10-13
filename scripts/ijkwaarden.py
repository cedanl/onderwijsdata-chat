#!/usr/bin/env python
"""
IJkwaarden voor de bronwaarheid-evals, rechtstreeks uit CBS, DUO en RIO (#190). Zonder LLM.

Gebruik:
    uv run python scripts/ijkwaarden.py                  # haal op en toon elk verschil met tests/e2e/ijkwaarden.json
    uv run python scripts/ijkwaarden.py --schrijf        # leg de nieuwe stand vast (verantwoord dat in de MR)
    uv run python scripts/ijkwaarden.py --alleen cbs,duo # alleen deze bronnen

Elk verschil (waarde, CBS-status, onderdrukte cellen) staat in het rapport; het script neemt nooit
stil een nieuwe waarde over. Exitcode 1 bij een verschil zonder --schrijf, en als een bron niet
antwoordt. Definities en de lijst ijkpunten: tests/ijkwaarden/README.md en harnas.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.ijkwaarden import harnas


def _argumenten(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IJkwaarden rechtstreeks uit de bronnen (#190).")
    parser.add_argument(
        "--schrijf", action="store_true", help="leg de opgehaalde stand vast in tests/e2e/ijkwaarden.json"
    )
    parser.add_argument("--alleen", default="", help="komma-gescheiden bronnen: cbs, duo, rio (standaard alle)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumenten(argv)
    bronnen = {b.strip() for b in args.alleen.split(",") if b.strip()} or None
    if bronnen and (onbekend := bronnen - set(harnas._HALERS)):
        print(f"Onbekende bron(nen): {', '.join(sorted(onbekend))}", file=sys.stderr)
        return 2

    try:
        live = harnas.haal_alles(bronnen)
    except Exception as fout:  # een bron die niet antwoordt is een meetfout, geen nieuwe stand
        print(f"Ophalen mislukt: {type(fout).__name__}: {fout}", file=sys.stderr)
        return 1

    try:
        vastgelegd = harnas.lees()["waarden"]
    except FileNotFoundError:
        vastgelegd = {}
    if bronnen:
        vastgelegd = {id: w for id, w in vastgelegd.items() if w.get("bron") in bronnen}

    verschillen = harnas.vergelijk(vastgelegd, live)
    print(f"IJkwaarden: {len(live)} opgehaald, {len(vastgelegd)} vastgelegd in {harnas.FIXTURE.relative_to(ROOT)}")
    for id, w in sorted(live.items()):
        status = f" ({w['status']})" if w.get("status") else ""
        cellen = f", {w['onderdrukte_cellen']} onderdrukte cel(len)" if w.get("onderdrukte_cellen") else ""
        print(f"  {id:<36} {w['waarde']!r}{status}{cellen}")
    if verschillen:
        print(f"\n{len(verschillen)} verschil(len) met de vastgelegde stand:")
        for v in verschillen:
            print(harnas.regel(v))
    else:
        print("\nGeen verschil met de vastgelegde stand.")

    if args.schrijf:
        if bronnen:
            # Alleen de opgehaalde bronnen vervangen; de rest blijft zoals vastgelegd.
            live = {**harnas.lees()["waarden"], **live} if harnas.FIXTURE.exists() else live
        harnas.schrijf(live)
        print(f"Vastgelegd in {harnas.FIXTURE.relative_to(ROOT)}.")
        return 0
    return 1 if verschillen else 0


if __name__ == "__main__":
    sys.exit(main())
