"""Which cached datasets belong to one conversation.

The store is shared by every session, so reports and dashboards must ask the
session which of its keys are theirs instead of listing the whole store.
"""

import json

from tools import store


def record_data_key(session: dict, tool_result: str, call: dict | None = None) -> None:
    """Remember the data_key a tool result points to, if it has one.

    `call` ({"name", "arguments"}) is the tool call that produced it: its
    provenance. A report needs that to reuse the selection the conversation
    made instead of guessing it again from the key (#174).
    """
    try:
        parsed = json.loads(tool_result)
    except (TypeError, ValueError):
        return
    key = parsed.get("data_key") if isinstance(parsed, dict) else None
    if isinstance(key, str):
        keys = session.setdefault("data_keys", [])
        if key not in keys:
            keys.append(key)
        if call is not None:
            # Keys are deterministic per selection: the first producer is the real one.
            session.setdefault("data_provenance", {}).setdefault(key, call)


def data_lineage(session: dict, key: str) -> list[dict]:
    """The tool calls that produced `key`, from the load call to the last query.

    A query_data call names its parent in its data_key argument; follow that
    back as far as provenance was recorded. Empty when nothing was recorded.
    """
    provenance = session.get("data_provenance", {})
    lineage: list[dict] = []
    while key in provenance and len(lineage) < len(provenance):
        call = provenance[key]
        lineage.insert(0, call)
        key = call.get("arguments", {}).get("data_key")
    return lineage


def session_data_keys(session: dict) -> list[str]:
    """This conversation's data keys that are still in the store, in load order."""
    return [key for key in session.get("data_keys", []) if store.get(key) is not None]
