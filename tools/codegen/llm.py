"""LLM-based code generation and cleanup."""

from __future__ import annotations

import json
import logging

import litellm

from .prompts import ANALYSIS_CODE_SYSTEM, CLEANUP_SYSTEM, SKIP_TOOLS
from .templates import is_upload_turn, plot_config_only


async def cleanup_turn_calls(
    turn: dict,
    model: str,
    extra_litellm_kwargs: dict,
) -> list[dict]:
    """Return a filtered list of tool calls with exploratory failures removed."""
    raw = [tc for tc in turn.get("tool_calls", []) if tc.get("name") not in SKIP_TOOLS]
    if len(raw) <= 1:
        return raw

    indexed = []
    for i, tc in enumerate(raw):
        try:
            args = json.loads(tc.get("arguments", "{}"))
        except Exception:
            args = {}
        indexed.append({"i": i, "naam": tc["name"], "args": args})

    user_msg = (
        f"Vraag: {turn.get('question', '')[:300]}\n"
        f"Antwoord: {(turn.get('answer') or '')[:500]}\n\n"
        f"Aanroepen:\n{json.dumps(indexed, ensure_ascii=False, indent=2)}"
    )

    try:
        response = await litellm.acompletion(
            model=model,
            max_tokens=150,
            num_retries=2,
            messages=[
                {"role": "system", "content": CLEANUP_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            **extra_litellm_kwargs,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        indices = json.loads(text)
        if isinstance(indices, list) and all(isinstance(i, int) for i in indices):
            kept = [raw[i] for i in sorted(set(indices)) if 0 <= i < len(raw)]
            if kept:
                return kept
    except Exception:
        logging.debug("codegen cleanup LLM call failed, keeping all tool calls", exc_info=True)

    return raw


def _strip_fences(code: str) -> str:
    if not code.startswith("```"):
        return code
    lines = code.splitlines()
    start = 1
    end = len(lines)
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].strip() == "```":
            end = i
            break
    return "\n".join(lines[start:end]).strip()


async def generate_analysis_code(
    turn: dict,
    model: str,
    extra_litellm_kwargs: dict,
) -> str | None:
    """Generate reproducible pandas/plotly code for a turn with create_plot.

    The 'data' array from create_plot is intentionally NOT passed to the LLM.
    Passing it causes hardcoded values instead of real data-retrieval code.
    Only chart configuration is passed so the LLM knows what to build but must
    derive all values dynamically.

    Returns Python source as a string, or None on failure.
    """
    tool_calls = turn.get("tool_calls", [])
    plot_calls = [tc for tc in tool_calls if tc.get("name") == "create_plot"]
    if not plot_calls:
        return None

    plot_configs = plot_config_only(plot_calls)
    upload = is_upload_turn(tool_calls)
    data_calls = [
        tc for tc in tool_calls
        if tc.get("name") not in SKIP_TOOLS | {"create_plot"}
    ]

    if upload:
        filenames: set[str] = set()
        upload_query_calls = []
        for tc in data_calls:
            if tc.get("name") == "query_data":
                try:
                    args = json.loads(tc.get("arguments", "{}"))
                except Exception:
                    args = {}
                data_key = args.get("data_key", "")
                if data_key.startswith("upload:"):
                    filenames.add(data_key[len("upload:"):].split(":")[0])
                    upload_query_calls.append(args)

        if not filenames:
            return None

        filename = next(iter(filenames))
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"

        parts = [
            f"Geüpload bestand: {filename} (extensie: {ext})",
            "",
            f"Vraag: {turn.get('question', '')[:400]}",
            f"Antwoord: {(turn.get('answer') or '')[:600]}",
            "",
            "query_data aanroepen (filters en kolomselectie die werden gebruikt):",
            json.dumps(upload_query_calls, ensure_ascii=False, indent=2),
            "",
            "Grafiekconfiguratie (maak deze grafiek — data DYNAMISCH ophalen uit het bestand):",
            json.dumps(plot_configs, ensure_ascii=False, indent=2),
            "",
            "VERBODEN: schrijf geen enkele hardgecodeerde lijst of dict met data.",
            "Genereer standalone Python code die:",
            "1. Het bestand laadt met pandas",
            "2. De filters en kolomselectie uit query_data toepast",
            "3. Aggregaties uitvoert die passen bij de grafiekconfiguratie",
            "4. De grafiek maakt met plotly.express",
            "Voeg 'import pandas as pd' en 'import plotly.express as px' toe (geen tools-import).",
        ]
    else:
        api_calls_repr = []
        for tc in data_calls:
            try:
                args = json.loads(tc.get("arguments", "{}"))
            except Exception:
                args = {}
            api_calls_repr.append({"tool": tc["name"], "args": args})

        parts = [
            f"Vraag: {turn.get('question', '')[:400]}",
            f"Antwoord: {(turn.get('answer') or '')[:600]}",
            "",
            "API tool calls die werden uitgevoerd (roep deze opnieuw aan om verse data op te halen):",
            json.dumps(api_calls_repr, ensure_ascii=False, indent=2),
            "",
            "Grafiekconfiguratie (maak deze grafiek — data DYNAMISCH ophalen via de API calls):",
            json.dumps(plot_configs, ensure_ascii=False, indent=2),
            "",
            "VERBODEN: schrijf geen enkele hardgecodeerde lijst of dict met data.",
            "Genereer Python code die:",
            "1. De API tool calls uitvoert (importeer via 'from tools import ...')",
            "2. JSON-resultaten parsed naar DataFrames:",
            "   query_data   → df = pd.DataFrame(json.loads(result)['rijen'])",
            "   get_cbs_data → df = pd.DataFrame(json.loads(result)['value'])",
            "   get_rio_data → df = pd.DataFrame(json.loads(result))",
            "3. Numerieke kolommen omzet met pd.to_numeric(..., errors='coerce')",
            "4. Benodigde transformaties uitvoert (hernoemen, groeperen, samenvoegen, berekeningen)",
            "   Afleidbaar uit de antwoordtekst, de API-filters en de grafiekconfiguratie",
            "5. De grafiek maakt met plotly.express",
            "Voeg 'import json', 'import pandas as pd' en 'import plotly.express as px' toe.",
        ]

    try:
        response = await litellm.acompletion(
            model=model,
            max_tokens=1500,
            num_retries=2,
            messages=[
                {"role": "system", "content": ANALYSIS_CODE_SYSTEM},
                {"role": "user", "content": "\n".join(parts)},
            ],
            **extra_litellm_kwargs,
        )
        code = _strip_fences(response.choices[0].message.content.strip())
        return code + "\n"
    except Exception:
        logging.debug("codegen analysis code generation failed", exc_info=True)
        return None
