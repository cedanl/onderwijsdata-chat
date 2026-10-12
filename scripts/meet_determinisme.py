#!/usr/bin/env python
"""Determinisme-scorekaart (#347): plan-invariantie, golden stand en herstelgraad.

Gebruik:
    uv run python scripts/meet_determinisme.py                   # rapport tegen gevallen.json
    uv run python scripts/meet_determinisme.py --schrijf-golden  # opnieuw meten en vastleggen

Zonder netwerk en zonder model. Een afwijking van de golden stand laat pytest
(tests/determinisme) falen; vastleggen is een expliciete stap die de MR verantwoordt.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.determinisme import harnas


def _regel(geval: dict, golden: dict | None) -> str:
    status = "✓"
    if geval["unieke_digests"] != 1:
        status = f"✗ {geval['unieke_digests']} digests"
    elif golden is not None and geval["plan_digest"] != golden.get("plan_digest"):
        status = f"✗ golden {golden.get('plan_digest')}"
    return f"  {geval['id']:<24} {geval['plan_digest']}  {status}  — {geval['toelichting']}"


def main() -> int:
    schrijf = "--schrijf-golden" in sys.argv
    kaart = harnas.schrijf_golden() if schrijf else harnas.scorekaart()
    try:
        golden = {geval["id"]: geval for geval in harnas.golden()["gevallen"]}
    except FileNotFoundError:
        golden = {}

    print(
        f"Determinisme-scorekaart {kaart['gemeten_op']} — prompt {kaart['prompt_hash']}, model {kaart['model']}, schema {kaart['schema_digest']}"
    )
    print(f"Plan-invariantie over {kaart['varianten_per_geval']} spellingen per geval:")
    for geval in kaart["gevallen"]:
        print(_regel(geval, golden.get(geval["id"])))
    herstel = kaart["herstel"]
    print(
        f"Periodeherstel (#342) op {herstel['sample']} gevallen: "
        f"{herstel['herstel']} gerepareerd, {herstel['weigering']} geweigerd, {herstel['geen']} ongemoeid."
    )
    stand = harnas.golden()
    if not schrijf and stand.get("prompt_hash") != kaart["prompt_hash"]:
        print(
            f"Let op: golden stand gemeten bij prompt {stand.get('prompt_hash')}, nu {kaart['prompt_hash']} (informatief)."
        )
    if schrijf:
        print(f"Golden stand vastgelegd in {harnas.GOLDEN}.")
    afwijkend = [g["id"] for g in kaart["gevallen"] if g["unieke_digests"] != 1]
    print(json.dumps({"afwijkend": afwijkend}, ensure_ascii=False)) if afwijkend else None
    return 1 if afwijkend else 0


if __name__ == "__main__":
    raise SystemExit(main())
