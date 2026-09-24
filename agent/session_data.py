"""Which cached datasets belong to one conversation.

The store is shared by every session, so reports and dashboards must ask the
session which of its keys are theirs instead of listing the whole store.
"""

import json

from tools import store


def record_data_key(session: dict, tool_result: str) -> None:
    """Remember the data_key a tool result points to, if it has one."""
    try:
        parsed = json.loads(tool_result)
    except (TypeError, ValueError):
        return
    key = parsed.get("data_key") if isinstance(parsed, dict) else None
    if isinstance(key, str):
        keys = session.setdefault("data_keys", [])
        if key not in keys:
            keys.append(key)


def session_data_keys(session: dict) -> list[str]:
    """This conversation's data keys that are still in the store, in load order."""
    return [key for key in session.get("data_keys", []) if store.get(key) is not None]
