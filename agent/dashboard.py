"""Dashboard generation orchestrator.

Takes a chat session with loaded datasets and uses an LLM to design
a complete dashboard — not just what the user asked, but the full
potential of the available data.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import plotly.io as pio

from agent.grounding import unsourced_numbers
from agent.model_context import clamp_max_tokens
from agent.models import litellm_kwargs
from agent.ratelimit import acompletion_with_backoff
from agent.session_data import data_lineage, session_data_keys
from agent.stream import accumulate_stream
from core.config import MAX_TOKENS, MODEL
from tools import LABELS, dispatch, store
from tools.columns import sample_values
from tools.schemas import (
    TOOL_COMPUTE_KPI,
    TOOL_CREATE_PLOT,
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_RIO_DATA,
    TOOL_QUERY_DATA,
    TOOL_SCHEMAS,
)

Emit = Callable[[dict[str, Any]], Awaitable[None]]

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "dashboard.md"

_DASHBOARD_TOOLS = [
    s for s in TOOL_SCHEMAS
    if s["function"]["name"] in (TOOL_QUERY_DATA, TOOL_CREATE_PLOT, TOOL_COMPUTE_KPI)  # ty: ignore[invalid-argument-type]
]

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 15
_MAX_TOOL_RESULT_CHARS = 8000


@dataclass
class DashboardSpec:
    title: str = ""
    description: str = ""
    narrative: str = ""
    kpis: list[dict] = field(default_factory=list)
    figures_json: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    recipe: list[dict] = field(default_factory=list)
    figure_recipes: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DashboardSpec:
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            narrative=data.get("narrative", ""),
            kpis=data.get("kpis") or [],
            figures_json=data.get("figures_json") or [],
            sources=data.get("sources") or [],
            recipe=data.get("recipe") or [],
            figure_recipes=data.get("figure_recipes") or [],
        )


_LOAD_TOOLS = (TOOL_GET_DUO_DATA, TOOL_GET_CBS_DATA, TOOL_GET_RIO_DATA)


def _build_recipe(datasets: list[dict]) -> list[dict]:
    """Reload calls for the given datasets, one per load call.

    The recorded load call (its herkomst) is used as is, so CBS filters survive
    a reload (#174). Without herkomst the key itself says how to reload.
    """
    recipe: list[dict] = []
    for ds in datasets:
        herkomst = ds.get("herkomst") or []
        if herkomst and herkomst[0]["name"] in _LOAD_TOOLS:
            call = {"name": herkomst[0]["name"], "arguments": json.dumps(herkomst[0]["arguments"])}
        else:
            call = _reload_call_from_key(ds["data_key"])
        if call and call not in recipe:
            recipe.append(call)
    return recipe


def _reload_call_from_key(key: str) -> dict | None:
    # Derived keys append a selection hash (duo:p01hoinges:3:74a5c5e2); reload the source.
    parts = key.split(":")
    if parts[0] == "duo" and len(parts) >= 3:
        return {"name": TOOL_GET_DUO_DATA, "arguments": json.dumps({"dataset_id": parts[1], "resource": _try_int(parts[2])})}
    if parts[0] == "cbs" and len(parts) >= 2:
        return {"name": TOOL_GET_CBS_DATA, "arguments": json.dumps({"dataset_id": parts[1]})}
    if parts[0] == "rio" and len(parts) >= 2:
        return {"name": TOOL_GET_RIO_DATA, "arguments": json.dumps({"resource": parts[1]})}
    return None


def _try_int(val: str) -> int | str:
    try:
        return int(val)
    except ValueError:
        return val


def _column_summary(df, col: str, max_examples: int = 5) -> dict:
    return {
        "naam": col,
        "type": str(df[col].dtype),
        "voorbeelden": sample_values(df[col], max_examples),
    }


def build_dataset_context(session: dict) -> dict:
    """Build a context dict describing the available datasets for the LLM."""
    datasets: list[dict] = []
    for key in session_data_keys(session):
        df = store.get(key)
        datasets.append({
            "data_key": key,
            "row_count": len(df),
            "columns": [_column_summary(df, col) for col in df.columns],
            "herkomst": data_lineage(session, key),
        })

    settings = session.get("chat_settings") or {}
    instelling = settings.get("instelling", "")

    turns = session.get("turns") or []
    first_question = ""
    if turns:
        first_question = turns[0].get("question", "")
    elif session.get("messages"):
        user_msgs = [m for m in session["messages"] if m.get("role") == "user"]
        if user_msgs:
            first_question = user_msgs[0].get("content", "")

    return {
        "datasets": datasets,
        "instelling": instelling,
        "topic": first_question,
    }


def _build_system_prompt(context: dict) -> str:
    """Build the system prompt with injected dataset context."""
    base = _PROMPT_PATH.read_text() if _PROMPT_PATH.exists() else ""

    dataset_blocks: list[str] = []
    for ds in context.get("datasets", []):
        cols = "\n".join(
            f"  - {c['naam']} ({c['type']}): {', '.join(c['voorbeelden'])}"
            for c in ds["columns"]
        )
        dataset_blocks.append(
            f"### {ds['data_key']}\n- Rijen: {ds['row_count']}\n- Kolommen:\n{cols}"
        )

    datasets_section = "\n\n".join(dataset_blocks) if dataset_blocks else "Geen datasets geladen."

    instelling = context.get("instelling", "")
    topic = context.get("topic", "")

    injected = f"""

## Beschikbare datasets in deze sessie

{datasets_section}

## Gebruikerscontext
- Instelling: {instelling or 'niet opgegeven'}
- Onderwerp: {topic or 'niet opgegeven'}
"""
    return base + injected


async def generate(
    session: dict,
    emit: Emit,
    model: str | None = None,
    stop_event: asyncio.Event | None = None,
) -> DashboardSpec:
    """Generate a dashboard from the loaded session data."""
    context = build_dataset_context(session)

    if not context["datasets"]:
        raise ValueError("Geen datasets geladen. Stel eerst een vraag waarvoor data wordt opgehaald.")

    chosen_model = model or MODEL
    system_prompt = _build_system_prompt(context)
    extra_kwargs = litellm_kwargs(chosen_model)

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Genereer een dashboard op basis van de beschikbare datasets."},
    ]

    figures: list[str] = []
    figure_recipes: list[dict] = []
    last_query_args: dict | None = None
    computed_kpis: dict[str, dict] = {}
    tool_results: list[str] = []

    partial_error = None
    final_text = ""

    try:
        for _ in range(_MAX_TOOL_ITERATIONS):
            if stop_event and stop_event.is_set():
                break

            clamped_tokens = clamp_max_tokens(chosen_model, MAX_TOKENS)
            stream = await acompletion_with_backoff(
                emit,
                model=chosen_model,
                max_tokens=clamped_tokens,
                messages=messages,
                tools=_DASHBOARD_TOOLS,
                stream=True,
                **extra_kwargs,
            )

            sr = await accumulate_stream(stream, stop_event=stop_event)
            text_content = sr.text
            tool_calls_list = sr.tool_calls
            final_text = text_content

            if not tool_calls_list:
                break

            messages.append({
                "role": "assistant",
                "content": text_content,
                "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in tool_calls_list
                ],
            })

            for tc in tool_calls_list:
                name = tc["name"]
                args = json.loads(tc["arguments"])

                label = LABELS.get(name, name)
                await emit({"type": "tool_start", "name": name, "label": label})

                result, figure = await asyncio.to_thread(dispatch, name, args)
                tool_results.append(result)

                await emit({"type": "tool_end", "name": name})

                if name == TOOL_QUERY_DATA:
                    last_query_args = args

                if name == TOOL_COMPUTE_KPI:
                    _collect_kpi(computed_kpis, result)

                if figure is not None:
                    figures.append(pio.to_json(figure))
                    await emit({"type": "figure", "label": label, "figure_json": pio.to_json(figure)})
                    plot_params = {k: v for k, v in args.items() if k != "data"}
                    figure_recipes.append({
                        "query": last_query_args,
                        "plot": plot_params,
                    })

                if len(result) > _MAX_TOOL_RESULT_CHARS:
                    result = result[:_MAX_TOOL_RESULT_CHARS] + f"\n... (afgekapt, {len(result)} chars totaal)"
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    except Exception as exc:
        if not figures:
            raise
        partial_error = str(exc)

    if partial_error:
        await emit({
            "type": "toast",
            "message": "Dashboard deels gegenereerd (fout: rate limit). Figuren tot nu toe bewaard.",
            "level": "warning",
        })

    spec = _parse_spec_from_response(final_text, figures, figure_recipes, context, session, computed_kpis)

    sourcing_error = _check_number_sourcing(final_text, tool_results)
    if sourcing_error:
        logger.error("Number sourcing guard rejected response: %s", sourcing_error)
        spec.narrative = f"**Fout in dashboard:** {sourcing_error}"
        spec.kpis = []

    return spec




def _extract_json_object(text: str) -> dict:
    """Extract the last top-level JSON object from text, handling nested braces."""
    # Try fenced code block first (greedy — captures the whole JSON)
    fence_match = re.search(r"```(?:json)?\s*(\{.+\})\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))

    # Find the last { and scan for its matching }
    candidates: list[str] = []
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[i:j + 1])
                    break

    # Return the largest candidate that parses as JSON with a "title" key
    for candidate in reversed(candidates):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict) and "title" in obj:
                return obj
        except json.JSONDecodeError:
            continue

    # Fallback: try the largest candidate
    for candidate in sorted(candidates, key=len, reverse=True):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    return {}


def _normaliseer_waarde(value: object) -> str:
    """Vergelijkbare vorm van een getal: '30.083' en '30083' zijn hetzelfde getal."""
    return str(value).replace(".", "").replace(" ", "").replace("\u00a0", "").strip().lower()


def _collect_kpi(computed: dict[str, dict], result: str) -> None:
    """Bewaar een compute_kpi-uitkomst, geïndexeerd op de genormaliseerde waarde."""
    try:
        payload = json.loads(result)
        if isinstance(payload, dict):
            if "fout" in payload:
                logger.warning("compute_kpi error: %s", payload["fout"])
            elif "value" in payload:
                computed[_normaliseer_waarde(payload["value"])] = payload
    except json.JSONDecodeError:
        logger.warning("compute_kpi returned invalid JSON: %r", result[:100])


def _check_number_sourcing(response: str, tool_results: list[str]) -> str | None:
    """Foutmelding als het dashboard getallen noemt die niet uit de tools komen."""
    unverified = unsourced_numbers(response, tool_results)
    if unverified:
        return (
            f"Dashboard bevat getallen die niet uit tools komen: {sorted(unverified)}. "
            "Alle getallen > 999 moeten uit query_data, compute_kpi, of andere tools komen."
        )
    return None


def _validate_kpis(kpis: list[dict], computed: dict[str, dict]) -> list[dict]:
    """Laat alleen KPI's door waarvan de waarde uit compute_kpi komt.

    Het label blijft van het model — dat is tekst. De waarde, de trend en de
    richting komen uit de tool, zodat een getal in een dashboard nooit door het
    model zelf berekend kan zijn. Liever twee gevalideerde KPI's dan vier
    waarvan er één verzonnen is.
    """
    gevalideerd: list[dict] = []
    for kpi in kpis:
        bron = computed.get(_normaliseer_waarde(kpi.get("value", "")))
        if bron is None:
            logger.warning("KPI geweigerd, waarde komt niet uit compute_kpi: %r", kpi)
            continue
        gevalideerd.append({
            **kpi,
            "value": bron["value"],
            "trend": bron.get("trend"),
            "trendDirection": bron.get("trendDirection"),
            "bron": bron.get("bron"),
        })
    return gevalideerd


def _parse_spec_from_response(
    response: str,
    figures_json: list[str],
    figure_recipes: list[dict],
    context: dict,
    session: dict,
    computed_kpis: dict[str, dict] | None = None,
) -> DashboardSpec:
    """Parse the LLM response into a DashboardSpec."""
    spec_data: dict = {}
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        spec_data = _extract_json_object(response)

    recipe = _build_recipe(context.get("datasets", []))
    topic = context.get("topic", "Dashboard")

    sources = spec_data.get("sources") or []
    if not sources:
        sources = _sources_from_recipe(recipe)

    return DashboardSpec(
        title=spec_data.get("title") or topic[:60] or "Dashboard",
        description=spec_data.get("description", ""),
        narrative=spec_data.get("narrative", ""),
        kpis=_validate_kpis(spec_data.get("kpis") or [], computed_kpis or {}),
        figures_json=figures_json,
        sources=sources,
        recipe=recipe,
        figure_recipes=figure_recipes,
    )


_SOURCE_PREFIXES = {
    TOOL_GET_DUO_DATA: "DUO",
    TOOL_GET_CBS_DATA: "CBS",
    TOOL_GET_RIO_DATA: "RIO",
}


def _sources_from_recipe(recipe: list[dict]) -> list[str]:
    """Derive source labels from recipe tool calls as fallback."""
    sources: list[str] = []
    for call in recipe:
        prefix = _SOURCE_PREFIXES.get(call.get("name", ""))
        if not prefix:
            continue
        try:
            args = json.loads(call["arguments"]) if isinstance(call["arguments"], str) else call["arguments"]
        except (json.JSONDecodeError, TypeError):
            args = {}
        dataset = args.get("dataset_id") or args.get("resource") or ""
        label = f"{prefix} — {dataset}" if dataset else prefix
        if label not in sources:
            sources.append(label)
    return sources
