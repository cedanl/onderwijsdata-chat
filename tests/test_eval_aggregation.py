"""Eval: verifieer dat de LLM server-side aggregatie gebruikt en correcte getallen rapporteert.

Draait de echte agent loop met een bekende vraag (VU Amsterdam eerstejaars bachelor)
en controleert:
1. De LLM gebruikt query_data met group_by/aggregate OF run_analysis
2. De gerapporteerde getallen matchen met de pandas ground truth

Vereist: werkende API key (ANTHROPIC_API_KEY of WILLMA_API_KEY in .env).
Draai met: uv run pytest tests/test_eval_aggregation.py -v -s
"""

import asyncio
import json
import os
import re

import pytest
from dotenv import load_dotenv

from riodata import duo

# Ground truth: bereken de werkelijke sommen met pandas
_DATASET_ID = "p02ho1ejrs"
_RESOURCE = "Eerstejaarsingeschrevenen wetenschappelijk onderwijs niveau opleiding in het domein hoger onderwijs"


def _ground_truth() -> dict[int, int]:
    df = duo.load(_DATASET_ID, _RESOURCE)
    vu = df[
        (df["INSTELLINGSNAAM_ACTUEEL"].str.lower() == "vrije universiteit amsterdam")
        & (df["TYPE_HOGER_ONDERWIJS"].str.lower() == "bachelor")
    ]
    vu_pos = vu[vu["AANTAL_EERSTEJAARS_INGESCHREVENEN"] >= 0]
    sums = vu_pos.groupby("STUDIEJAAR")["AANTAL_EERSTEJAARS_INGESCHREVENEN"].sum()
    return {int(k): int(v) for k, v in sums.items()}


load_dotenv()
_has_api_key = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("WILLMA_API_KEY"))


@pytest.mark.skipif(not _has_api_key, reason="Geen API key beschikbaar")
def test_vu_eerstejaars_uses_aggregation_and_correct_numbers():
    from agent.run import run

    events: list[dict] = []
    tool_calls: list[dict] = []

    async def emit(event: dict):
        events.append(event)
        if event.get("type") == "tool_start":
            tool_calls.append(event)

    messages = [
        {"role": "user", "content": (
            "Hoeveel eerstejaars bachelorstudenten stroomden in bij de "
            "Vrije Universiteit Amsterdam? Totaal per studiejaar, alle beschikbare jaren."
        )},
    ]

    answer = asyncio.get_event_loop().run_until_complete(
        run(messages, session={}, emit=emit)
    )

    # 1. Check: LLM moet group_by/aggregate of run_analysis gebruiken
    used_aggregation = any(
        tc.get("name") == "query_data"
        and ("group_by" in json.dumps(tc.get("input", {})))
        for tc in tool_calls
    )
    used_analysis = any(
        tc.get("name") == "run_analysis" for tc in tool_calls
    )
    assert used_aggregation or used_analysis, (
        f"LLM gebruikte geen server-side aggregatie. Tool calls: "
        f"{[tc.get('name') for tc in tool_calls]}"
    )

    # 2. Check: gerapporteerde getallen moeten matchen met ground truth
    truth = _ground_truth()
    numbers_in_answer = set(re.findall(r"\d[\d.]+", answer.replace(".", "")))

    matched = 0
    for year, expected in truth.items():
        if str(expected) in numbers_in_answer:
            matched += 1

    assert matched >= len(truth) - 1, (
        f"Slechts {matched}/{len(truth)} jaren matchen met ground truth. "
        f"Verwacht: {truth}. Antwoord bevat getallen: {numbers_in_answer}"
    )
