"""Report generation orchestrator.

Produces a compact, professional report from the loaded session data:
the research question front and centre, chosen definitions (what the
report does and does not answer), 1-2 visualisations with an explanation,
and a conclusion. Unlike the dashboard, the report stays focused on the
user's question instead of exploring the full potential of the data.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import plotly.io as pio

from agent.dashboard import (
    _build_recipe_from_store,
    _extract_json_object,
    _sources_from_recipe,
    build_dataset_context,
)
from agent.models import litellm_kwargs
from agent.ratelimit import acompletion_with_backoff
from agent.stream import accumulate_stream
from core.config import MAX_TOKENS, MODEL
from tools import LABELS, dispatch
from tools.schemas import TOOL_CREATE_PLOT, TOOL_QUERY_DATA, TOOL_SCHEMAS

Emit = Callable[[dict[str, Any]], Awaitable[None]]

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "report.md"

_REPORT_TOOLS = [
    s
    for s in TOOL_SCHEMAS
    if s["function"]["name"] in (TOOL_QUERY_DATA, TOOL_CREATE_PLOT)  # ty: ignore[invalid-argument-type]
]

_MAX_TOOL_ITERATIONS = 15
_MAX_TOOL_RESULT_CHARS = 8000
_MAX_VISUALISATIES = 2

_DUTCH_MONTHS = [
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
]


def _nl_datum(today: date | None = None) -> str:
    today = today or date.today()
    return f"{today.day} {_DUTCH_MONTHS[today.month - 1]} {today.year}"


@dataclass
class ReportSpec:
    title: str = ""
    onderzoeksvraag: str = ""
    definities: list[dict] = field(default_factory=list)
    beantwoordt: list[str] = field(default_factory=list)
    beantwoordt_niet: list[str] = field(default_factory=list)
    visualisaties: list[dict] = field(default_factory=list)
    conclusie: str = ""
    bronnen: list[str] = field(default_factory=list)
    auteur: str = ""
    datum: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _build_system_prompt(context: dict) -> str:
    """Build the system prompt with injected dataset context."""
    base = _PROMPT_PATH.read_text() if _PROMPT_PATH.exists() else ""

    dataset_blocks: list[str] = []
    for ds in context.get("datasets", []):
        cols = "\n".join(f"  - {c['naam']} ({c['type']}): {', '.join(c['voorbeelden'])}" for c in ds["columns"])
        dataset_blocks.append(f"### {ds['data_key']}\n- Rijen: {ds['row_count']}\n- Kolommen:\n{cols}")

    datasets_section = "\n\n".join(dataset_blocks) if dataset_blocks else "Geen datasets geladen."

    instelling = context.get("instelling", "")
    topic = context.get("topic", "")

    injected = f"""

## Beschikbare datasets in deze sessie

{datasets_section}

## Gebruikerscontext
- Instelling: {instelling or "niet opgegeven"}
- Onderwerp (onderzoeksvraag): {topic or "niet opgegeven"}
"""
    return base + injected


async def generate(
    session: dict,
    emit: Emit,
    model: str | None = None,
    stop_event: asyncio.Event | None = None,
    author: str | None = None,
) -> ReportSpec:
    """Generate a report from the loaded session data."""
    context = build_dataset_context(session)

    if not context["datasets"]:
        raise ValueError("Geen datasets geladen. Stel eerst een vraag waarvoor data wordt opgehaald.")

    chosen_model = model or MODEL
    system_prompt = _build_system_prompt(context)
    extra_kwargs = litellm_kwargs(chosen_model)

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Stel een professioneel rapport op dat antwoord geeft op de onderzoeksvraag."},
    ]

    figures: list[str] = []
    partial_error: str | None = None

    try:
        for _ in range(_MAX_TOOL_ITERATIONS):
            if stop_event and stop_event.is_set():
                break

            stream = await acompletion_with_backoff(
                emit,
                model=chosen_model,
                max_tokens=MAX_TOKENS,
                messages=messages,
                tools=_REPORT_TOOLS,
                stream=True,
                **extra_kwargs,
            )

            sr = await accumulate_stream(stream, stop_event=stop_event)
            text_content = sr.text
            tool_calls_list = sr.tool_calls

            if not tool_calls_list:
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": text_content,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in tool_calls_list
                    ],
                }
            )

            for tc in tool_calls_list:
                name = tc["name"]
                args = json.loads(tc["arguments"])

                label = LABELS.get(name, name)
                await emit({"type": "tool_start", "name": name, "label": label})

                result, figure = await asyncio.to_thread(dispatch, name, args)

                await emit({"type": "tool_end", "name": name})

                if figure is not None and len(figures) < _MAX_VISUALISATIES:
                    figures.append(pio.to_json(figure))

                if len(result) > _MAX_TOOL_RESULT_CHARS:
                    result = result[:_MAX_TOOL_RESULT_CHARS] + f"\n... (afgekapt, {len(result)} chars totaal)"
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    except Exception as exc:
        if not figures:
            raise
        partial_error = str(exc)

    if partial_error:
        await emit(
            {
                "type": "toast",
                "message": "Rapport deels gegenereerd (fout: rate limit). Figuren tot nu toe bewaard.",
                "level": "warning",
            }
        )

    final_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            final_text = msg["content"]
            break

    return _parse_spec_from_response(final_text, figures, context, author)


def _parse_spec_from_response(
    response: str,
    figures_json: list[str],
    context: dict,
    author: str | None = None,
) -> ReportSpec:
    """Parse the LLM response into a ReportSpec."""
    spec_data: dict = {}
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        spec_data = _extract_json_object(response)

    recipe = _build_recipe_from_store()
    topic = context.get("topic", "Rapport")

    bronnen = spec_data.get("bronnen") or []
    if not bronnen:
        bronnen = _sources_from_recipe(recipe)

    vis_meta = spec_data.get("visualisaties") or []
    visualisaties: list[dict] = []
    for idx, figure_json in enumerate(figures_json):
        meta = vis_meta[idx] if idx < len(vis_meta) else {}
        visualisaties.append(
            {
                "titel": (meta.get("titel") or "").strip() or f"Visualisatie {idx + 1}",
                "toelichting": (meta.get("toelichting") or "").strip(),
                "figure_json": figure_json,
            }
        )

    onderzoeksvraag = (spec_data.get("onderzoeksvraag") or "").strip() or topic
    title = (spec_data.get("title") or "").strip() or onderzoeksvraag[:60] or "Rapport"

    return ReportSpec(
        title=title,
        onderzoeksvraag=onderzoeksvraag,
        definities=spec_data.get("definities") or [],
        beantwoordt=spec_data.get("beantwoordt") or [],
        beantwoordt_niet=spec_data.get("beantwoordt_niet") or [],
        conclusie=(spec_data.get("conclusie") or "").strip(),
        visualisaties=visualisaties,
        bronnen=bronnen,
        auteur=(author or "").strip(),
        datum=_nl_datum(),
    )
