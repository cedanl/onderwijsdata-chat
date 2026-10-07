from typing import Any

from . import fouten, store
from .analysis import run_analysis
from .catalog import catalogus_telling, dataset_details, search_catalog
from .cbs import get_cbs_data, get_cbs_dimension
from .duo import get_duo_data
from .kpi import compute_kpi
from .outcome import outcome  # noqa: F401
from .plot import create_choropleth_map, create_plot
from .query import query_data
from .rio import get_rio_data
from .rio_instelling import get_rio_instelling
from .schemas import (
    TOOL_CLARIFY_SCOPE,
    TOOL_COMPUTE_KPI,
    TOOL_CREATE_CHOROPLETH_MAP,
    TOOL_CREATE_PLOT,
    TOOL_DATASET_COUNTS,
    TOOL_DATASET_DETAILS,
    TOOL_GET_CBS_DATA,
    TOOL_GET_CBS_DIMENSION,
    TOOL_GET_DUO_DATA,
    TOOL_GET_RIO_DATA,
    TOOL_GET_RIO_INSTELLING,
    TOOL_QUERY_DATA,
    TOOL_RUN_ANALYSIS,
    TOOL_SEARCH_CATALOG,
)
from .schemas import TOOL_SCHEMAS as SCHEMAS  # noqa: F401

LABELS = {
    TOOL_SEARCH_CATALOG: "Catalogus doorzocht",
    TOOL_DATASET_DETAILS: "Datasetdetails opgehaald",
    TOOL_DATASET_COUNTS: "Catalogus geteld",
    TOOL_CLARIFY_SCOPE: "Scope vastgesteld",
    TOOL_GET_CBS_DATA: "CBS data opgehaald",
    TOOL_GET_CBS_DIMENSION: "CBS dimensie opgehaald",
    TOOL_GET_RIO_DATA: "RIO data opgehaald",
    TOOL_GET_RIO_INSTELLING: "Instelling in RIO opgezocht",
    TOOL_GET_DUO_DATA: "DUO dataset geladen",
    TOOL_QUERY_DATA: "Data gefilterd",
    TOOL_RUN_ANALYSIS: "Analyse uitgevoerd",
    TOOL_COMPUTE_KPI: "KPI berekend",
    TOOL_CREATE_PLOT: "Grafiek aangemaakt",
    TOOL_CREATE_CHOROPLETH_MAP: "Kaart aangemaakt",
}

_HANDLERS = {
    TOOL_SEARCH_CATALOG: search_catalog,
    TOOL_DATASET_DETAILS: dataset_details,
    TOOL_DATASET_COUNTS: catalogus_telling,
    TOOL_GET_CBS_DATA: get_cbs_data,
    TOOL_GET_CBS_DIMENSION: get_cbs_dimension,
    TOOL_GET_RIO_DATA: get_rio_data,
    TOOL_GET_RIO_INSTELLING: get_rio_instelling,
    TOOL_GET_DUO_DATA: get_duo_data,
    TOOL_QUERY_DATA: query_data,
    TOOL_RUN_ANALYSIS: run_analysis,
    TOOL_COMPUTE_KPI: compute_kpi,
    TOOL_CREATE_PLOT: create_plot,
    TOOL_CREATE_CHOROPLETH_MAP: create_choropleth_map,
}


def dispatch(name: str, tool_input: dict) -> tuple[str, Any]:
    handler = _HANDLERS.get(name)
    if not handler:
        return f"Onbekende tool: {name}", None
    if isinstance(key := tool_input.get("data_key"), str):
        # cbs_85353NED en CBS:85353ned vonden niets en kostten een ronde per variant (#331).
        tool_input = {**tool_input, "data_key": store.canoniek(key)}
    try:
        result = handler(**tool_input)
        if isinstance(result, tuple):
            return result
        return result, None
    except Exception as e:
        return fouten.toolfout(name, e), None
