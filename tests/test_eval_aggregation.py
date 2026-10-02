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

import pytest
from dotenv import load_dotenv
from riodata import duo

from core.config import MODEL, get_required_api_key_env_var

from .eval_assertions import ungrounded_numbers, unpaired_years

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

# Bepaal welke API key dit MODEL nodig heeft via centrale config mapping (zie #53).
# Dit voorkomt drift: provider→key mapping staat nu op één plaats.
_required_key = get_required_api_key_env_var(MODEL)
_has_required_key = _required_key is None or os.getenv(_required_key)


@pytest.mark.skipif(
    not _has_required_key,
    reason=f"Ontbrekende API key voor {MODEL}: {_required_key or 'geen key required'}",
)
def test_vu_eerstejaars_uses_aggregation_and_correct_numbers():
    from agent.run import run

    events: list[dict] = []
    tool_calls: list[dict] = []

    async def emit(event: dict):
        events.append(event)
        if event.get("type") == "tool_start":
            tool_calls.append(event)

    messages = [
        {
            "role": "user",
            "content": (
                "Hoeveel eerstejaars bachelorstudenten stroomden in bij de "
                "Vrije Universiteit Amsterdam? Totaal per studiejaar, alle beschikbare jaren."
            ),
        },
    ]

    answer = asyncio.run(run(messages, session={}, emit=emit))

    # 1. Check: LLM moet group_by/aggregate of run_analysis gebruiken
    used_aggregation = any(
        tc.get("name") == "query_data" and ("group_by" in json.dumps(tc.get("input", {}))) for tc in tool_calls
    )
    used_analysis = any(tc.get("name") == "run_analysis" for tc in tool_calls)
    assert used_aggregation or used_analysis, (
        f"LLM gebruikte geen server-side aggregatie. Tool calls: {[tc.get('name') for tc in tool_calls]}"
    )

    # 2. Check: gerapporteerde getallen moeten matchen met ground truth
    truth = _ground_truth()

    # 2a. Paarsgewijs: jaar én waarde moeten samen voorkomen
    assert not (problems := unpaired_years(answer, truth)), problems

    # 2b. Geen ongedekte getallen: elk getal >999 moet uit tool-output komen
    tool_payloads = [
        tc.get("output") or tc.get("input", {}) for tc in events if tc.get("type") in ("tool_end", "tool_start")
    ]
    ongedekt = ungrounded_numbers(answer, tool_payloads)
    assert not ongedekt, f"Getallen zonder tool-herkomst: {ongedekt}"
