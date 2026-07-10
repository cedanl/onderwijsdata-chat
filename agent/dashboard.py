"""Dashboard generation orchestrator.

Takes a chat session with loaded datasets and uses an LLM to design
a complete dashboard — not just what the user asked, but the full
potential of the available data.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import plotly.io as pio

from core.config import MAX_TOKENS, MODEL
from agent.models import litellm_kwargs
from agent.ratelimit import acompletion_with_backoff
from tools import dispatch, LABELS
from tools import store
from tools.schemas import (
    TOOL_SCHEMAS,
    TOOL_GET_DUO_DATA,
    TOOL_GET_CBS_DATA,
    TOOL_GET_RIO_DATA,
    TOOL_QUERY_DATA,
    TOOL_CREATE_PLOT,
)

Emit = Callable[[dict[str, Any]], Awaitable[None]]

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "dashboard.md"

_DASHBOARD_TOOLS = [
    s for s in TOOL_SCHEMAS
    if s["function"]["name"] in (TOOL_QUERY_DATA, TOOL_CREATE_PLOT)
]

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


def _build_recipe_from_store() -> list[dict]:
    """Build recipe from current store keys — each key encodes how to reload."""
    recipe: list[dict] = []
    seen: set[str] = set()
    for key in store.list_keys():
        if key in seen:
            continue
        seen.add(key)
        parts = key.split(":", 2)
        if parts[0] == "duo" and len(parts) >= 3:
            recipe.append({"name": TOOL_GET_DUO_DATA, "arguments": json.dumps({"dataset_id": parts[1], "resource": _try_int(parts[2])})})
        elif parts[0] == "cbs" and len(parts) >= 2:
            recipe.append({"name": TOOL_GET_CBS_DATA, "arguments": json.dumps({"dataset_id": parts[1]})})
        elif parts[0] == "rio" and len(parts) >= 2:
            recipe.append({"name": TOOL_GET_RIO_DATA, "arguments": json.dumps({"resource": parts[1]})})
    return recipe


def _try_int(val: str) -> int | str:
    try:
        return int(val)
    except ValueError:
        return val


def _column_summary(df, col: str, max_examples: int = 5) -> dict:
    return {
        "naam": col,
        "type": str(df[col].dtype),
        "voorbeelden": [str(v) for v in df[col].dropna().unique()[:max_examples]],
    }


def build_dataset_context(session: dict) -> dict:
    """Build a context dict describing the available datasets for the LLM."""
    datasets: list[dict] = []
    seen_keys: set[str] = set()

    for key in store.list_keys():
        df = store.get(key)
        if df is None:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        datasets.append({
            "data_key": key,
            "row_count": len(df),
            "columns": [_column_summary(df, col) for col in df.columns],
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

    partial_error = None

    try:
        for _ in range(_MAX_TOOL_ITERATIONS):
            if stop_event and stop_event.is_set():
                break

            stream = await acompletion_with_backoff(
                emit,
                model=chosen_model,
                max_tokens=MAX_TOKENS,
                messages=messages,
                tools=_DASHBOARD_TOOLS,
                stream=True,
                **extra_kwargs,
            )

            text_parts: list[str] = []
            raw_tcs: dict[int, dict] = {}

            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    text_parts.append(delta.content)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in raw_tcs:
                            raw_tcs[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                        if tc.function:
                            if tc.function.name:
                                raw_tcs[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                raw_tcs[idx]["arguments"] += tc.function.arguments

            text_content = "".join(text_parts)
            tool_calls_list = list(raw_tcs.values())

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

                await emit({"type": "tool_end", "name": name})

                if name == TOOL_QUERY_DATA:
                    last_query_args = args

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
            "message": f"Dashboard deels gegenereerd (fout: rate limit). Figuren tot nu toe bewaard.",
            "level": "warning",
        })

    final_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            final_text = msg["content"]
            break

    spec = _parse_spec_from_response(final_text, figures, figure_recipes, context, session)
    return spec




def _extract_json_object(text: str) -> dict:
    """Extract the last top-level JSON object from text, handling nested braces."""
    import re
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


def _parse_spec_from_response(
    response: str,
    figures_json: list[str],
    figure_recipes: list[dict],
    context: dict,
    session: dict,
) -> DashboardSpec:
    """Parse the LLM response into a DashboardSpec."""
    spec_data: dict = {}
    try:
        spec_data = _extract_json_object(response)
    except (json.JSONDecodeError, ValueError):
        pass

    recipe = _build_recipe_from_store()
    topic = context.get("topic", "Dashboard")

    sources = spec_data.get("sources") or []
    if not sources:
        sources = _sources_from_recipe(recipe)

    return DashboardSpec(
        title=spec_data.get("title") or topic[:60] or "Dashboard",
        description=spec_data.get("description", ""),
        narrative=spec_data.get("narrative", ""),
        kpis=spec_data.get("kpis") or [],
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
