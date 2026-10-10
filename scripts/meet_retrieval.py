#!/usr/bin/env python
"""
Meet search_catalog op de vaste vragenset, zonder LLM en zonder netwerk (#359).

Gebruik:
    uv run python scripts/meet_retrieval.py                     # rapport, details van de ontwikkelreeks
    uv run python scripts/meet_retrieval.py --toon-test         # ook de details van de testreeks
    uv run python scripts/meet_retrieval.py --schrijf-baseline  # leg de meting vast in baseline.json

Per sector en reeks: recall@5 en MRR met 95%-interval en het verschil met baseline.json, hoe vaak
onbeantwoordbare en kritieke vragen slagen, dezelfde maten met de natuurlijke vraag als invoer,
en de latentie per zoekopdracht. Definities en release-eis: tests/retrieval_baseline/README.md.

Exitcode 1 als de meting het netwerk probeerde, of als --schrijf-baseline een kritieke vraag
als falend zou vastleggen die in de oude baseline slaagde (zonder --accepteer-kritiek).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.retrieval_baseline import harnas, rapport


def _argumenten(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieval-baseline van search_catalog (#359).")
    parser.add_argument("--toon-test", action="store_true", help="toon ook de details van de testreeks")
    parser.add_argument("--schrijf-baseline", action="store_true", help="leg de meting vast in baseline.json")
    parser.add_argument(
        "--accepteer-kritiek",
        action="store_true",
        help="schrijf de baseline ook als er een kritieke vraag bij faalt (verantwoord dat in de MR)",
    )
    return parser.parse_args(argv)


def _schrijf(gemeten: harnas.Meting, snapshot: dict, oud: dict | None, accepteer: bool) -> int:
    nieuw = rapport.baseline(gemeten, snapshot, date.today().isoformat())
    if (regressies := rapport.nieuw_falend(oud, nieuw)) and not accepteer:
        print(
            f"baseline.json niet geschreven: deze kritieke vragen falen nu en in de oude baseline niet: {regressies}. "
            "Dat is een release-blokkade; schrijf alleen met --accepteer-kritiek en verantwoord het in de MR.",
            file=sys.stderr,
        )
        return 1
    harnas.schrijf_baseline(nieuw)
    print(f"\nbaseline.json geschreven: {nieuw['gemeten_op']}, catalogus {nieuw['catalogus_digest']}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _argumenten(argv)
    gemeten = harnas.meet(harnas.laad_vragen())
    snapshot = harnas.snapshot()
    oud = harnas.laad_baseline()
    print(rapport.tekst(gemeten, oud, snapshot, toon_test=args.toon_test))
    if gemeten.netwerkpogingen:
        print(f"De meting probeerde het netwerk: {gemeten.netwerkpogingen}", file=sys.stderr)
        return 1
    if args.schrijf_baseline:
        return _schrijf(gemeten, snapshot, oud, accepteer=args.accepteer_kritiek)
    return 0


if __name__ == "__main__":
    sys.exit(main())
