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
import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import plotly.io as pio

from agent.dashboard import (
    _build_recipe,
    _extract_json_object,
    _sources_from_recipe,
    build_dataset_context,
)
from agent.loop import ToolCall, tool_loop
from agent.report_checks import report_problems
from agent.stream import Emit
from core.config import MODEL
from tools.schemas import TOOL_CREATE_PLOT, TOOL_QUERY_DATA, TOOL_SCHEMAS

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "report.md"

_REPORT_TOOLS = [
    s
    for s in TOOL_SCHEMAS
    if s["function"]["name"] in (TOOL_QUERY_DATA, TOOL_CREATE_PLOT)  # ty: ignore[invalid-argument-type]
]

logger = logging.getLogger(__name__)

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


def _describe_call(call: dict) -> str:
    return f"{call['name']} {json.dumps(call['arguments'], ensure_ascii=False)}"


def _describe_herkomst(herkomst: list[dict]) -> str:
    """The tool calls that produced a dataset, so the report reuses that selection (#174)."""
    if not herkomst:
        return "onbekend (niet vastgelegd in dit gesprek)"
    return " → ".join(_describe_call(call) for call in herkomst)


def _build_system_prompt(context: dict) -> str:
    """Build the system prompt with injected dataset context."""
    base = _PROMPT_PATH.read_text() if _PROMPT_PATH.exists() else ""

    dataset_blocks: list[str] = []
    for ds in context.get("datasets", []):
        cols = "\n".join(f"  - {c['naam']} ({c['type']}): {', '.join(c['voorbeelden'])}" for c in ds["columns"])
        dataset_blocks.append(
            f"### {ds['data_key']}\n- Rijen: {ds['row_count']}\n"
            f"- Herkomst: {_describe_herkomst(ds.get('herkomst') or [])}\n- Kolommen:\n{cols}"
        )

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
    """Generate a report from the loaded session data.

    The report must agree with its own data (#175). If it does not, the model
    gets one correction; a report that still contradicts its data is refused.
    """
    context = build_dataset_context(session)

    if not context["datasets"]:
        raise ValueError("Geen datasets geladen. Stel eerst een vraag waarvoor data wordt opgehaald.")

    messages: list[dict] = [
        {"role": "system", "content": _build_system_prompt(context)},
        {"role": "user", "content": "Stel een professioneel rapport op dat antwoord geeft op de onderzoeksvraag."},
    ]
    figures: list[str] = []
    dataset_context = json.dumps(context, default=str)

    async def keep_figure(call: ToolCall, result: str, figure) -> None:
        _log_tool_call(call.name, call.args, result)
        if figure is not None and len(figures) < _MAX_VISUALISATIES:
            figures.append(pio.to_json(figure))

    def check(text: str, tool_results: list[str]) -> list[str]:
        spec = _parse_spec_from_response(text, figures, context, author)
        return report_problems(spec, figures, [*tool_results, dataset_context])

    result = await tool_loop(
        messages,
        model=model or MODEL,
        tools=_REPORT_TOOLS,
        emit=emit,
        stop_event=stop_event,
        max_iterations=_MAX_TOOL_ITERATIONS,
        max_result_chars=_MAX_TOOL_RESULT_CHARS,
        on_tool_result=keep_figure,
        check=check,
        correction=_correction,
        keep_partial=lambda: bool(figures),
    )
    if result.partial_error:
        await emit({
            "type": "toast",
            "message": "Rapport deels gegenereerd (fout: rate limit). Figuren tot nu toe bewaard.",
            "level": "warning",
        })
    if result.problems:
        logger.error("RAPPORT GEWEIGERD: %s", result.problems)
        raise ValueError(f"Rapport niet consistent met de data: {result.problems[0]} Probeer het opnieuw.")
    return _parse_spec_from_response(result.text, figures, context, author)


def _correction(problems: list[str]) -> str:
    return (
        "Je rapport klopt niet met de data die je hebt opgehaald:\n"
        + "\n".join(f"- {p}" for p in problems)
        + "\nHerstel dit: gebruik alleen getallen uit de toolresultaten en beschrijf wat de "
        "grafieken tonen. Geef daarna opnieuw het volledige JSON-blok."
    )


def _log_tool_call(name: str, args: dict, result: str) -> None:
    """Log what the report fetched: a misfilter must be traceable afterwards (#174)."""
    try:
        parsed = json.loads(result)
        outcome = f"totaal_rijen={parsed.get('totaal_rijen')}" if isinstance(parsed, dict) else "ok"
    except (TypeError, ValueError):
        outcome = f"melding={result[:200]!r}"
    logger.info("RAPPORT TOOL %s args=%s %s", name, json.dumps(args, ensure_ascii=False), outcome)


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

    recipe = _build_recipe(context.get("datasets", []))
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
