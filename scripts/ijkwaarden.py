#!/usr/bin/env python
"""
IJkwaarden voor de bronwaarheid-evals, rechtstreeks uit CBS, DUO en RIO (#190). Zonder LLM.

Gebruik:
    uv run python scripts/ijkwaarden.py                  # haal op en toon elk verschil met tests/e2e/ijkwaarden.json
    uv run python scripts/ijkwaarden.py --schrijf        # leg de nieuwe stand vast (verantwoord dat in de MR)
    uv run python scripts/ijkwaarden.py --alleen cbs,duo # alleen deze bronnen

Elk verschil (waarde, CBS-status, onderdrukte cellen) staat in het rapport; het script neemt nooit
stil een nieuwe waarde over. Exitcode 1 bij een verschil zonder --schrijf, en als een ijkpunt niet
antwoordt; de bronnen die wel antwoorden staan dan toch in het rapport (#627). Definities en de lijst
ijkpunten: tests/ijkwaarden/README.md en harnas.py.
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

    live, fouten = harnas.haal_alles(bronnen)

    try:
        vastgelegd = harnas.lees()["waarden"]
    except FileNotFoundError:
        vastgelegd = {}
    if bronnen:
        vastgelegd = {id: w for id, w in vastgelegd.items() if w.get("bron") in bronnen}
    # Wat niet antwoordde is niet "verdwenen uit de lijst": het blijft vastgelegd en buiten de vergelijking.
    vergelijkbaar = {id: w for id, w in vastgelegd.items() if id not in fouten}

    verschillen = harnas.vergelijk(vergelijkbaar, live)
    print(f"IJkwaarden: {len(live)} opgehaald, {len(vastgelegd)} vastgelegd in {harnas.FIXTURE.relative_to(ROOT)}")
    for id, w in sorted(live.items()):
        status = f" ({w['status']})" if w.get("status") else ""
        cellen = f", {w['onderdrukte_cellen']} onderdrukte cel(len)" if w.get("onderdrukte_cellen") else ""
        print(f"  {id:<36} {w['waarde']!r}{status}{cellen}")
    _meld_fouten(fouten, vastgelegd)
    if verschillen:
        print(f"\n{len(verschillen)} verschil(len) met de vastgelegde stand:")
        for v in verschillen:
            print(harnas.regel(v))
    else:
        print("\nGeen verschil met de vastgelegde stand.")

    if args.schrijf:
        if bronnen or fouten:
            # Alleen de opgehaalde ijkpunten vervangen; de rest blijft zoals vastgelegd.
            live = {**harnas.lees()["waarden"], **live} if harnas.FIXTURE.exists() else live
        harnas.schrijf(live)
        print(f"Vastgelegd in {harnas.FIXTURE.relative_to(ROOT)}.")
        return 1 if fouten else 0
    return 1 if verschillen or fouten else 0


def _meld_fouten(fouten: dict[str, str], vastgelegd: dict[str, dict]) -> None:
    """De ijkpunten die niet antwoordden, per bron, met de fout van de bron."""
    if not fouten:
        return
    print(f"\n{len(fouten)} ijkpunt(en) niet opgehaald; hun vastgelegde waarde is niet vergeleken en niet vervangen:")
    for id, fout in sorted(fouten.items()):
        bron = vastgelegd.get(id, {}).get("bron") or next((p.bron for p in harnas.IJKPUNTEN if p.id == id), "?")
        print(f"  ! {id:<36} [{bron}] {fout}")


if __name__ == "__main__":
    sys.exit(main())
