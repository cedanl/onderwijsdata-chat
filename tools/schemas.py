TOOL_SCHEMAS = [
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
            "description": "Haal een CBS dataset op. Retourneert kolomschema, voorbeeldwaarden en data_key — gebruik daarna query_data om gefilterde rijen op te halen.",
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
            "description": "Haal RIO data op. Retourneert kolomschema, voorbeeldwaarden en data_key — gebruik daarna query_data om gefilterde rijen op te halen.",
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
            "description": "Filter en selecteer rijen uit een geladen dataset. Werkt voor alle databronnen: DUO (data_key van get_duo_data), CBS (data_key van get_cbs_data), RIO (data_key van get_rio_data) én geüploade bestanden (data_key begint met 'upload:').",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_key": {"type": "string", "description": "data_key uit get_duo_data, get_cbs_data of get_rio_data"},
                    "filters": {"type": "object", "description": "Kolomfilters: exacte waarden bijv. {\"Leerweg\": \"Voltijd\"}, of range-operatoren: {\"JAAR__gte\": \"2020\"}, {\"JAAR__lte\": \"2023\"}, {\"JAAR__in\": [\"2021\",\"2022\"]}"},
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
    {
        "type": "function",
        "function": {
            "name": "clarify_scope",
            "description": (
                "Stel EXACT één gesloten vraag met 2 of 3 klikbare antwoordopties. "
                "Dit is de ENIGE manier om scope-vragen te stellen — schrijf ze nooit als platte tekst. "
                "Gebruik bij een nieuwe analysevraag om open scope-dimensies vast te leggen. "
                "Sla dimensies over die al uit de vraag of het gebruikersprofiel blijken. "
                "Typisch 1–3 aanroepen. Als de vraag al specifiek genoeg is (3+ dimensies "
                "expliciet), sla deze tool over en ga direct naar search_catalog. "
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
    },
]
