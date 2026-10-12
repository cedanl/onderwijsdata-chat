"""Replay data-fetching tool calls to refresh datasets in the store."""

import json
import logging

import plotly.io as pio

from tools import dispatch
from tools.schemas import (
    TOOL_CREATE_PLOT,
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_RIO_DATA,
    TOOL_QUERY_DATA,
)

logger = logging.getLogger(__name__)

# De enige tools die een recept mag herhalen: de load-tools waaruit _build_recipe het
# samenstelt. Het recept komt van de client, en zonder deze grens kon een ingelogde
# client er elke tool mee aanroepen, run_analysis inbegrepen (#505). De scopecontrole
# (#355) zit in de tools zelf en geldt zo ook voor dit pad.
REPLAYABLE_TOOLS = frozenset({TOOL_GET_DUO_DATA, TOOL_GET_CBS_DATA, TOOL_GET_RIO_DATA})


def replay_data_calls(calls: list[dict]) -> list[dict]:
    """Re-execute data-fetching calls. Returns per-call status.

    De fouttekst per mislukte call is een vaste, veilige melding: de ruwe uitzondering
    (met paden of parser-details) gaat alleen naar het log (#503).
    """
    results: list[dict] = []
    for tc in calls:
        name = tc.get("name")
        if name not in REPLAYABLE_TOOLS:
            logger.warning("Replay geweigerd: tool %r staat niet in het recept-allowlist", name)
            results.append(
                {
                    "name": name,
                    "arguments": tc.get("arguments"),
                    "success": False,
                    "error": "tool niet toegestaan bij verversen",
                }
            )
            continue
        try:
            args = json.loads(tc.get("arguments") or "{}")
            output, _ = dispatch(name, args)
            results.append({"name": name, "arguments": tc.get("arguments"), "success": True, "output": output})
        except Exception:
            logger.warning("Herladen van %s mislukt", name, exc_info=True)
            results.append(
                {"name": name, "arguments": tc.get("arguments"), "success": False, "error": "herladen mislukt"}
            )
    return results


def replay_dashboard_figures(
    recipe: list[dict],
    figure_recipes: list[dict],
) -> list[str]:
    """Reload data and re-create figures. Returns updated figures_json.

    1. Replay data-load calls (populates store with fresh data)
    2. For each figure recipe: re-query data, re-create plot
    """
    replay_data_calls(recipe)

    figures_json: list[str] = []
    for fr in figure_recipes:
        query = fr.get("query")
        plot = fr.get("plot") or {}
        if not query or not query.get("data_key"):
            continue
        try:
            result_str, _ = dispatch(TOOL_QUERY_DATA, query)
            rows = json.loads(result_str).get("rijen", [])
            if not rows:
                continue
            plot_args = {**plot, "data": rows}
            _, figure = dispatch(TOOL_CREATE_PLOT, plot_args)
            if figure is not None:
                figures_json.append(pio.to_json(figure))
        except Exception:
            logger.debug("Figure replay mislukt, overgeslagen", exc_info=True)
            continue

    return figures_json
