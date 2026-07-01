"""Replay data-fetching tool calls to refresh datasets in the store."""

import json

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
