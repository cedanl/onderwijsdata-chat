from .catalog import search_catalog
from .cbs import get_cbs_data, get_cbs_dimension
from .rio import get_rio_data

SCHEMAS = [
    {
        "name": "search_catalog",
        "description": "Zoek in de CBS en/of RIO catalogus naar relevante datasets op basis van een zoekopdracht.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Zoekterm, bijv. 'mbo studenten' of 'onderwijslocaties Amsterdam'"},
                "source": {"type": "string", "enum": ["cbs", "rio", "both"], "description": "Te doorzoeken bron (standaard: beide)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_cbs_data",
        "description": "Haal rijen op uit een CBS dataset. Gebruik $filter voor OData filtering.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "CBS dataset ID, bijv. '85423NED'"},
                "filters": {"type": "object", "description": "OData parameters, bijv. {\"$filter\": \"Geslacht eq 'T001038'\"}"},
            },
            "required": ["dataset_id"],
        },
    },
    {
        "name": "get_cbs_dimension",
        "description": "Haal de mogelijke waarden op van een dimensie in een CBS dataset.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "CBS dataset ID"},
                "dimension_name": {"type": "string", "description": "Naam van de dimensie, bijv. 'Geslacht'"},
            },
            "required": ["dataset_id", "dimension_name"],
        },
    },
    {
        "name": "get_rio_data",
        "description": "Haal records op uit de RIO LOD API.",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource": {"type": "string", "description": "RIO resource naam, bijv. 'onderwijslocaties' of 'aangeboden-opleidingen'"},
                "filters": {"type": "object", "description": "Filter parameters, bijv. {\"organisatorischeEenheidcode\": \"25LH\"}"},
            },
            "required": ["resource"],
        },
    },
]

LABELS = {
    "search_catalog": "Catalogus doorzocht",
    "get_cbs_data": "CBS data opgehaald",
    "get_cbs_dimension": "CBS dimensie opgehaald",
    "get_rio_data": "RIO data opgehaald",
}

_HANDLERS = {
    "search_catalog": search_catalog,
    "get_cbs_data": get_cbs_data,
    "get_cbs_dimension": get_cbs_dimension,
    "get_rio_data": get_rio_data,
}


def dispatch(name: str, tool_input: dict) -> str:
    handler = _HANDLERS.get(name)
    if not handler:
        return f"Onbekende tool: {name}"
    try:
        return handler(**tool_input)
    except Exception as e:
        return f"Fout bij uitvoeren van {name}: {e}"
