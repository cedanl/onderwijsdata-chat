"""Replay data-fetching tool calls to refresh datasets in the store."""

import json

import plotly.io as pio

from tools import dispatch

DATA_FETCH_TOOLS = frozenset({"get_duo_data", "get_cbs_data", "get_rio_data"})


def extract_data_calls(tool_calls: list[dict] | None) -> list[dict]:
    """Extract unique data-fetching tool calls, preserving order."""
    if not tool_calls:
        return []
    seen: set[str] = set()
    result: list[dict] = []
    for tc in tool_calls:
        if tc.get("name") not in DATA_FETCH_TOOLS:
            continue
        key = f"{tc['name']}:{tc['arguments']}"
        if key in seen:
            continue
        seen.add(key)
        result.append(tc)
    return result


def replay_data_calls(calls: list[dict]) -> list[dict]:
    """Re-execute data-fetching calls. Returns per-call status."""
    results: list[dict] = []
    for tc in calls:
        name = tc["name"]
        try:
            args = json.loads(tc.get("arguments") or "{}")
            output, _ = dispatch(name, args)
            results.append({"name": name, "arguments": tc.get("arguments"), "success": True, "output": output})
        except Exception as e:
            results.append({"name": name, "arguments": tc.get("arguments"), "success": False, "error": str(e)})
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
            result_str, _ = dispatch("query_data", query)
            rows = json.loads(result_str).get("rijen", [])
            if not rows:
                continue
            plot_args = {**plot, "data": rows}
            _, figure = dispatch("create_plot", plot_args)
            if figure is not None:
                figures_json.append(pio.to_json(figure))
        except Exception:
            continue

    return figures_json
