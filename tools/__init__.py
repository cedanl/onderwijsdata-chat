from typing import Any

from .analysis import run_analysis
from .catalog import search_catalog
from .cbs import get_cbs_data, get_cbs_dimension
from .duo import get_duo_data, query_data
from .plot import create_choropleth_map, create_plot
from .rio import get_rio_data
from .schemas import (
    TOOL_SCHEMAS as SCHEMAS,
    TOOL_SEARCH_CATALOG,
    TOOL_CLARIFY_SCOPE,
    TOOL_GET_CBS_DATA,
    TOOL_GET_CBS_DIMENSION,
    TOOL_GET_RIO_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_QUERY_DATA,
    TOOL_RUN_ANALYSIS,
    TOOL_CREATE_PLOT,
    TOOL_CREATE_CHOROPLETH_MAP,
)

LABELS = {
    TOOL_SEARCH_CATALOG: "Catalogus doorzocht",
    TOOL_CLARIFY_SCOPE: "Scope vastgesteld",
    TOOL_GET_CBS_DATA: "CBS data opgehaald",
    TOOL_GET_CBS_DIMENSION: "CBS dimensie opgehaald",
    TOOL_GET_RIO_DATA: "RIO data opgehaald",
    TOOL_GET_DUO_DATA: "DUO dataset geladen",
    TOOL_QUERY_DATA: "Data gefilterd",
    TOOL_RUN_ANALYSIS: "Analyse uitgevoerd",
    TOOL_CREATE_PLOT: "Grafiek aangemaakt",
    TOOL_CREATE_CHOROPLETH_MAP: "Kaart aangemaakt",
}

_HANDLERS = {
    TOOL_SEARCH_CATALOG: search_catalog,
    TOOL_GET_CBS_DATA: get_cbs_data,
    TOOL_GET_CBS_DIMENSION: get_cbs_dimension,
    TOOL_GET_RIO_DATA: get_rio_data,
    TOOL_GET_DUO_DATA: get_duo_data,
    TOOL_QUERY_DATA: query_data,
    TOOL_RUN_ANALYSIS: run_analysis,
    TOOL_CREATE_PLOT: create_plot,
    TOOL_CREATE_CHOROPLETH_MAP: create_choropleth_map,
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
