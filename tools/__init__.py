from typing import Any

from .catalog import search_catalog
from .cbs import get_cbs_data, get_cbs_dimension
from .duo import get_duo_data, query_data
from .plot import create_choropleth_map, create_plot
from .rio import get_rio_data

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Zoek in de CBS-, RIO- en DUO-catalogus naar relevante datasets. De catalogus bevat CBS statistieken, RIO registers én DUO open data (prognoses, diplomering, instroom, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Zoekterm, bijv. 'mbo studenten prognose' of 'onderwijslocaties Amsterdam'"},
                    "source": {"type": "string", "enum": ["cbs", "rio", "duo", "both"], "description": "Te doorzoeken bron: 'cbs', 'rio', 'duo' (alleen DUO-datasets), of 'both' (alles)"},
                    "top_n": {"type": "integer", "description": "Maximaal aantal resultaten (standaard: 15)"},
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
            "name": "get_duo_data",
            "description": "Laad een DUO open dataset. Retourneert kolomschema, voorbeeldwaarden en data_key — gebruik daarna query_duo_data om gefilterde rijen op te halen voor analyse of grafiek.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string", "description": "CKAN package-naam uit de catalogus, bijv. 'studentprognoses-mbo-v1'"},
                    "resource": {"type": ["integer", "string"], "description": "Index (0, 1, ...) of naam-substring van het bestand binnen de dataset (default: 0)"},
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": "Filter en selecteer rijen uit een geladen dataset. Werkt voor DUO-data (data_key van get_duo_data) én geüploade bestanden (data_key begint met 'upload:').",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_key": {"type": "string", "description": "data_key uit get_duo_data"},
                    "filters": {"type": "object", "description": "Kolomfilters als exacte waarden, bijv. {\"Leerweg\": \"Voltijd\", \"Jaar\": \"2023\"}"},
                    "columns": {"type": "array", "items": {"type": "string"}, "description": "Alleen deze kolommen teruggeven"},
                    "max_rows": {"type": "integer", "description": "Maximaal aantal rijen (default: 500)"},
                },
                "required": ["data_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_choropleth_map",
            "description": (
                "Maak een interactieve kaart van Nederland met kleuren per regio. "
                "Gebruik dit voor regionale vergelijkingen: provincies, gemeenten of COROP-gebieden. "
                "De data moet CBS-regiocodes bevatten (bijv. 'PV20', 'GM0363')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Lijst van datarijen met regiocodes en een numerieke waarde per rij",
                    },
                    "location_col": {
                        "type": "string",
                        "description": "Kolomnaam met CBS-regiocodes, bijv. 'RegioS' (waarden als 'GM0363' of 'PV20')",
                    },
                    "value_col": {
                        "type": "string",
                        "description": "Kolomnaam met de numerieke waarden voor de kleurschaal",
                    },
                    "title": {"type": "string", "description": "Titel van de kaart"},
                    "level": {
                        "type": "string",
                        "enum": ["auto", "provincie", "gemeente", "corop"],
                        "description": "Geografisch niveau. 'auto' detecteert op basis van de codes (standaard).",
                    },
                },
                "required": ["data", "location_col", "value_col", "title"],
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
                    "chart_type": {"type": "string", "enum": ["bar", "line", "scatter", "pie", "histogram"], "description": "Type grafiek"},
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

_CLARIFY_SCOPE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "clarify_scope",
        "description": (
            "Stel EXACT één gesloten vraag met 2 of 3 klikbare antwoordopties. "
            "Gebruik dit als EERSTE actie bij elke nieuwe analysevraag en herhaal het per beurt "
            "totdat alle scope-dimensies vastliggen (tijdsperiode, geografisch niveau, "
            "opleidingsniveau, uitsplitsing, doel). "
            "Ga NOOIT direct naar search_catalog of data-tools zonder de scope eerst scherp te stellen. "
            "Bronkeuze via opties is ALLEEN toegestaan als ALLERLAATSTE clarify_scope-aanroep, "
            "nadat alle andere dimensies al bepaald zijn. "
            "Na deze tool is de beurt klaar — wacht op het antwoord van de gebruiker."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vraag": {
                    "type": "string",
                    "description": "Één concrete, gesloten verduidelijkingsvraag",
                },
                "opties": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Korte antwoordtekst, bijv. 'Laatste schooljaar'"},
                            "beschrijving": {"type": "string", "description": "Alleen voor bronopties: één zin over het verschil"},
                            "aanbevolen": {"type": "boolean", "description": "True voor de aanbevolen optie"},
                        },
                        "required": ["label"],
                    },
                    "description": "Precies 2 of 3 gesloten antwoordopties",
                },
            },
            "required": ["vraag", "opties"],
        },
    },
}

SCHEMAS = SCHEMAS + [_CLARIFY_SCOPE_SCHEMA]

LABELS = {
    "search_catalog": "Catalogus doorzocht",
    "clarify_scope": "Scope vastgesteld",
    "get_cbs_data": "CBS data opgehaald",
    "get_cbs_dimension": "CBS dimensie opgehaald",
    "get_rio_data": "RIO data opgehaald",
    "get_duo_data": "DUO dataset geladen",
    "query_data": "Data gefilterd",
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
