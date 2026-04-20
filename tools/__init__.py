from typing import Any

from .catalog import search_catalog
from .cbs import get_cbs_data, get_cbs_dimension
from .plot import create_plot
from .rio import get_rio_data

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Zoek in de CBS en/of RIO catalogus naar relevante datasets op basis van een zoekopdracht.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Zoekterm, bijv. 'mbo studenten' of 'onderwijslocaties Amsterdam'"},
                    "source": {"type": "string", "enum": ["cbs", "rio", "both"], "description": "Te doorzoeken bron (standaard: beide)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cbs_data",
            "description": "Haal rijen op uit een CBS dataset. Gebruik $filter voor OData filtering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string", "description": "CBS dataset ID, bijv. '85423NED'"},
                    "filters": {"type": "object", "description": "OData parameters, bijv. {\"$filter\": \"Geslacht eq 'T001038'\"}"},
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cbs_dimension",
            "description": "Haal de mogelijke waarden op van een dimensie in een CBS dataset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string", "description": "CBS dataset ID"},
                    "dimension_name": {"type": "string", "description": "Naam van de dimensie, bijv. 'Geslacht'"},
                },
                "required": ["dataset_id", "dimension_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_rio_data",
            "description": "Haal records op uit de RIO LOD API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource": {"type": "string", "description": "RIO resource naam, bijv. 'onderwijslocaties' of 'aangeboden-opleidingen'"},
                    "filters": {"type": "object", "description": "Filter parameters, bijv. {\"organisatorischeEenheidcode\": \"25LH\"}"},
                },
                "required": ["resource"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_plot",
            "description": "Maak een interactieve grafiek van opgehaalde data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "array", "items": {"type": "object"}, "description": "Lijst van datarijen als objecten"},
                    "chart_type": {"type": "string", "enum": ["bar", "line", "scatter", "pie"], "description": "Type grafiek"},
                    "x": {"type": "string", "description": "Veldnaam voor de x-as (of labels bij pie)"},
                    "y": {"type": "string", "description": "Veldnaam voor de y-as (of waarden bij pie)"},
                    "title": {"type": "string", "description": "Titel van de grafiek"},
                    "color_by": {"type": "string", "description": "Veldnaam om op te groeperen (bijv. 'Geslacht' voor man/vrouw vergelijking)"},
                },
                "required": ["data", "chart_type", "x", "y", "title"],
            },
        },
    },
]

LABELS = {
    "search_catalog": "Catalogus doorzocht",
    "get_cbs_data": "CBS data opgehaald",
    "get_cbs_dimension": "CBS dimensie opgehaald",
    "get_rio_data": "RIO data opgehaald",
    "create_plot": "Grafiek aangemaakt",
}

_HANDLERS = {
    "search_catalog": search_catalog,
    "get_cbs_data": get_cbs_data,
    "get_cbs_dimension": get_cbs_dimension,
    "get_rio_data": get_rio_data,
    "create_plot": create_plot,
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
