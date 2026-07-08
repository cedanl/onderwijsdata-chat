from typing import Any

from .analysis import run_analysis
from .catalog import search_catalog
from .cbs import get_cbs_data, get_cbs_dimension
from .duo import get_duo_data, query_data
from .plot import create_choropleth_map, create_plot
from .rio import get_rio_data
from .schemas import TOOL_SCHEMAS as SCHEMAS

LABELS = {
    "search_catalog": "Catalogus doorzocht",
    "clarify_scope": "Scope vastgesteld",
    "get_cbs_data": "CBS data opgehaald",
    "get_cbs_dimension": "CBS dimensie opgehaald",
    "get_rio_data": "RIO data opgehaald",
    "get_duo_data": "DUO dataset geladen",
    "query_data": "Data gefilterd",
    "run_analysis": "Analyse uitgevoerd",
    "create_plot": "Grafiek aangemaakt",
    "create_choropleth_map": "Kaart aangemaakt",
}

_HANDLERS = {
    "search_catalog": search_catalog,
    "get_cbs_data": get_cbs_data,
    "get_cbs_dimension": get_cbs_dimension,
    "get_rio_data": get_rio_data,
    "get_duo_data": get_duo_data,
    "query_data": query_data,
    "run_analysis": run_analysis,
    "create_plot": create_plot,
    "create_choropleth_map": create_choropleth_map,
}


def dispatch(name: str, tool_input: dict) -> tuple[str, Any]:
    handler = _HANDLERS.get(name)
    if not handler:
        return f"Onbekende tool: {name}", None
    try:
        result = handler(**tool_input)
        if isinstance(result, tuple):
            return result
        return result, None
    except Exception as e:
        return f"Fout bij uitvoeren van {name}: {e}", None
