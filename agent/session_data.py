"""Which cached datasets belong to one conversation.

The store is shared by every session, so reports and dashboards must ask the
session which of its keys are theirs instead of listing the whole store.
"""

import json

from tools import fouten, store
from tools.schemas import TOOL_COMPUTE_KPI, TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS

# Rekentools waarvan de uitkomst in de chat al uit de data kwam: bewijs voor het rapport (#397).
# query_data alleen met aggregatie: een rijenselectie staat al in de datasetcontext.
_REKENTOOLS = frozenset({TOOL_COMPUTE_KPI, TOOL_RUN_ANALYSIS})
_MAX_REKENBEWIJS = 30


def _rekent(call: dict) -> bool:
    if call.get("name") in _REKENTOOLS:
        return True
    return call.get("name") == TOOL_QUERY_DATA and bool((call.get("arguments") or {}).get("aggregate"))


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


def record_rekenbewijs(session: dict, tool_result: str, call: dict) -> None:
    """Bewaar de uitkomst van een geslaagde rekentool met zijn aanroep (#397).

    Een KPI of afgeleid getal (som, verschil) dat compute_kpi of run_analysis gaf, is in de
    rapportfase anders geen bewijs: die controleert alleen zijn eigen toolresultaten.
    Alleen het toolresultaat telt, nooit de vrije antwoordtekst.
    """
    if not _rekent(call) or fouten.code(tool_result) is not None:
        return
    try:
        parsed = json.loads(tool_result)
    except (TypeError, ValueError):
        return
    if not isinstance(parsed, dict) or "fout" in parsed:
        return
    bewijs = session.setdefault("rekenbewijs", [])
    bewijs.append({"tool": call["name"], "argumenten": call.get("arguments") or {}, "resultaat": tool_result})
    del bewijs[:-_MAX_REKENBEWIJS]


def rekenbewijs(session: dict) -> list[dict]:
    """De bewaarde rekenuitkomsten van dit gesprek, oudste eerst."""
    return list(session.get("rekenbewijs") or [])
