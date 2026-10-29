from typing import Any

from core.config import RIO_PAGE_SIZE
from data.arbeidsmarkt import SECTOR_CLUSTER_MAP

# ── Tool name constants ──────────────────────────────────────────────
TOOL_SEARCH_CATALOG = "search_catalog"
TOOL_GET_MAAT = "get_maat"
TOOL_DATASET_DETAILS = "dataset_details"
TOOL_DATASET_COUNTS = "dataset_counts"
TOOL_DATASET_PROFIEL = "dataset_profiel"
TOOL_RELATIE = "relatie"
TOOL_CLARIFY_SCOPE = "clarify_scope"
TOOL_GET_CBS_DATA = "get_cbs_data"
TOOL_GET_CBS_DIMENSION = "get_cbs_dimension"
TOOL_GET_RIO_DATA = "get_rio_data"
TOOL_GET_RIO_INSTELLING = "get_rio_instelling"
TOOL_GET_DUO_DATA = "get_duo_data"
TOOL_QUERY_DATA = "query_data"
TOOL_CREATE_PLOT = "create_plot"
TOOL_CREATE_CHOROPLETH_MAP = "create_choropleth_map"
TOOL_RUN_ANALYSIS = "run_analysis"
TOOL_COMPUTE_KPI = "compute_kpi"
TOOL_GET_UWV_VACATURES = "get_uwv_vacatures"
TOOL_GET_ROA_BENCHMARK = "get_roa_benchmark"

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": TOOL_GET_MAAT,
            "description": (
                "Vaste maat uit een vast recept: jij kiest de maat en de afbakening, de code kiest dataset, bestand "
                "en codes. Gebruik dit vóór search_catalog voor een telling van studenten, inschrijvingen of "
                "eerstejaars per hbo/wo-instelling, mbo-studenten per instelling, ingeschrevenen hbo/wo landelijk, "
                "of doorstroom vmbo → mbo landelijk (doorstroom_vmbo_mbo: CBS 85569NED, mbo-instromers uit "
                "vmbo-leerjaar 3-4; zonder instelling of sector). "
                "'Studenten' is ingeschreven_personen_ho (personen); inschrijvingen_ho alleen als de gebruiker om "
                "inschrijvingen vraagt. Bij doorstroom_vmbo_mbo zet de app de bron, de definitie en het "
                "DUO-alternatief zelf onder het antwoord; de DUO-telling (Instromende mbo-studenten, vmbo-diploma) "
                "alleen als de gebruiker erom vraagt, via get_duo_data. Geslacht per opleiding bij een hbo/wo-instelling: "
                "opleiding_naar_geslacht. Geeft een data_key met één rij per studiejaar (bij geslacht per opleiding "
                "één per studiejaar en geslacht), de teldefinitie en het recept; "
                "query_data, compute_kpi en create_plot werken er gewoon mee. Een onbekende instelling of maat is "
                "een fout, geen gok."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "maat": {
                        "type": "string",
                        "enum": [
                            "ingeschreven_personen_ho",
                            "inschrijvingen_ho",
                            "eerstejaars_ho",
                            "deelnemers_ho_landelijk",
                            "mbo_studenten_instelling",
                            "doorstroom_vmbo_mbo",
                        ],
                        "description": "De maat; zie de beschrijving van de tool.",
                    },
                    "instelling": {
                        "type": "string",
                        "description": "Officiële naam of alias van de instelling (hbo, wo of mbo); niet bij een landelijke maat.",
                    },
                    "sector": {
                        "type": "string",
                        "enum": ["hbo", "wo"],
                        "description": "Alleen bij deelnemers_ho_landelijk: hbo of wo.",
                    },
                    "vorm": {
                        "type": "string",
                        "enum": ["alle", "voltijd", "deeltijd", "duaal", "bol", "bbl"],
                        "description": "Opleidingsvorm (ho) of leerweg (mbo); standaard alle.",
                    },
                    "schooljaren": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Schooljaren als 2024/25 (of het startjaar 2024); weglaten voor alle beschikbare.",
                    },
                    "opleiding_naar_geslacht": {
                        "type": "string",
                        "description": (
                            "Alleen voor de verdeling naar geslacht (man/vrouw) van één opleiding bij één hbo/wo-"
                            "instelling: haar naam of CROHO-code, met ingeschreven_personen_ho, eerstejaars_ho of "
                            "inschrijvingen_ho en zonder vorm. DUO heeft geslacht niet per opleiding; de code geeft de "
                            "verdeling alleen in de jaren waarin ze exact af te leiden is, en anders de reden. Leid "
                            "haar nooit zelf af uit het geslachtsbestand."
                        ),
                    },
                },
                "required": ["maat"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_SEARCH_CATALOG,
            "description": (
                "Zoek in de CBS-, RIO- en DUO-catalogus naar relevante datasets. De catalogus bevat CBS statistieken, "
                "RIO registers én DUO open data (prognoses, diplomering, instroom, etc.). Het antwoord is altijd JSON "
                "met een `status` (candidates, no_match, needs_clarification, out_of_scope, metadata_unknown, "
                "source_unavailable of tool_error), de `kandidaten` (elk met `dataset_id` en `geraakt`), een `melding` "
                "en een `vervolgstap`. Lees eerst de status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "2 tot 4 losse Nederlandse trefwoorden, ook bij een vraag in een andere taal (de catalogus is "
                            "Nederlandstalig; 'university students' vindt niets). GEEN volzin en GEEN vraagteken. Laat "
                            "instellingsnamen, plaatsnamen en jaartallen weg: daar wordt niet op gefilterd. "
                            "Goed: 'ingeschrevenen wo opleidingsvorm'. Fout: 'Hoeveel voltijdstudenten heeft de VU?'"
                        ),
                    },
                    "top_n": {"type": "integer", "description": "Maximaal aantal resultaten (standaard: 15)"},
                    "geo_niveau": {
                        "type": "string",
                        "enum": ["gemeente", "provincie", "corop", "landelijk", "landsdeel"],
                        "description": "Filter: geef alleen datasets terug die dit geografisch niveau ondersteunen. Gebruik bij regionale vragen.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_DATASET_DETAILS,
            "description": (
                "Haal gedetailleerde kolominformatie op voor één specifiek dataset uit de catalogus. "
                "Gebruik dit nadat search_catalog kandidaten heeft opgeleverd, om te controleren "
                "welke kolommen, dimensiewaarden en types beschikbaar zijn vóór het laden van data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "Dataset-ID uit `dataset_id` van een kandidaat in search_catalog: CBS (bijv. '85423NED'), DUO (bijv. 'instromende-mbo-studenten') of RIO (bijv. 'onderwijslocaties')",
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_DATASET_COUNTS,
            "description": (
                "Aantal datasets per bron (CBS, DUO, RIO) dat deze chat kan opvragen. Gebruik dit voor een vraag "
                "naar hoeveel datasets er zijn, niet het aantal zoekresultaten."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_GET_CBS_DATA,
            "description": (
                "Haal een CBS dataset op via een selectie: jij kiest per dimensie een code, de server bouwt "
                "de bronfilter. Elke dimensie van de tabel moet gekozen zijn (een code, of '*' om uit te "
                "splitsen) en de periode benoemd; een onvolledige selectie wordt geweigerd. Retourneert "
                "kolomschema, voorbeeldwaarden en data_key — gebruik daarna query_data om gefilterde rijen "
                "op te halen. De kolom Periodestatus geeft per rij de officiële CBS-status "
                "(Definitief/Voorlopig/...); noem de status alleen op basis daarvan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string", "description": "CBS dataset ID, bijv. '85423NED'"},
                    "selectie": {
                        "type": "object",
                        "description": (
                            "De selectie. 'dimensies': per dimensie een code uit get_cbs_dimension, een lijst "
                            "codes, of '*' om uit te splitsen. 'periode': lijst van schooljaren of "
                            "periodecodes, {'van': …, 'tot': …} als bereik, of '*'. 'onderwerpen': optioneel, "
                            "alleen deze kolomsleutels. 'sector': optioneel, 'mbo', 'hbo' of 'wo', de sector waarvoor "
                            "je de tabel bevraagt; een code van een andere sector wordt dan geweigerd. Bijv. "
                            '{"dimensies": {"Geslacht": "T001038", "Opleidingsfase": "*"}, '
                            '"periode": ["2024/25"]}'
                        ),
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_GET_CBS_DIMENSION,
            "description": "Haal de mogelijke waarden op van een dimensie in een CBS dataset: code → titel. Voor de tijddimensie (Perioden) code → {titel, status} met de officiële CBS-status; er is geen aparte dimensie 'Status'.",
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
            "name": TOOL_DATASET_PROFIEL,
            "description": (
                "Profiel van een geladen tabel (data_key): per kolom type, waar hij op lijkt (identificatie, jaar, "
                "schooljaar, geocode, categorie, getal), lege en unieke cellen, bereik en vaakste waarden, plus de "
                "korrel: de kolomcombinatie die elke rij apart aanwijst. Gebruik dit vóór een som of telling over "
                "een tabel waarvan je de korrel niet zeker weet: een som over een kolom buiten de korrel telt dubbel."
            ),
            "parameters": {
                "type": "object",
                "properties": {"data_key": {"type": "string", "description": "data_key uit een laad- of filterstap"}},
                "required": ["data_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_RELATIE,
            "description": (
                "Wat hangt aan wat tussen CBS, DUO en RIO. Met één data_key: per sleutelkolom (instellingscode, "
                "instellingsnaam, gemeente, provincie, schooljaar, opleidingscode) wat eraan hangt en hoeveel "
                "waarden het register of de gebiedsindeling kent. Met andere_key: de kolommen die beide tabellen "
                "als dezelfde sleutel dragen, hoe hun waarden vertalen (GM0344 is gemeente 344, 2021SJ00 is "
                "schooljaar 2021), de kardinaliteit en de overlap. Koppelt zelf niets: gebruik de uitkomst in "
                "query_data of run_analysis. Vraag dit vóór je twee bronnen combineert."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data_key": {"type": "string", "description": "data_key van de tabel"},
                    "andere_key": {"type": "string", "description": "data_key van de tabel om mee te koppelen"},
                },
                "required": ["data_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_GET_RIO_DATA,
            "description": (
                "Haal RIO data op. Retourneert kolomschema, voorbeeldwaarden en data_key — gebruik daarna "
                f"query_data om gefilterde rijen op te halen. Levert maximaal {RIO_PAGE_SIZE} rijen "
                "(één pagina) en géén totalen: gebruik RIO niet voor aantallen over het hele register "
                "('hoeveel opleidingen staan er in RIO?'), maar DUO of CBS. Voor bestuur, instellingen, "
                f"vestigingen of erkenningen van één instelling: {TOOL_GET_RIO_INSTELLING}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "resource": {
                        "type": "string",
                        "description": "RIO resource naam, bijv. 'onderwijslocaties' of 'aangeboden-opleidingen'",
                    },
                    "filters": {
                        "type": "object",
                        "description": (
                            'Filter parameters, bijv. {"type": "AANGEBODENMBOOPLEIDING"}. organisatorischeEenheidcode '
                            "is de RIO-code van een aanbieder (zoals 114A897), niet de BRIN-code."
                        ),
                    },
                },
                "required": ["resource"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_GET_RIO_INSTELLING,
            "description": (
                "Overzicht van één onderwijsinstelling uit RIO: het bevoegd gezag (bestuur), de erkende "
                "instellingen eronder en hun vestigingen, met de aantallen erkenningen, instellingen en "
                "vestigingen op de peildatum. Gebruik dit voor elke vraag naar het bestuur, de instellingen, "
                "vestigingen of erkenningen van een instelling. De code zoekt en telt: neem `aantallen` "
                "letterlijk over en tel niet zelf. Bij `status: meerdere` vraag je welke van de `kandidaten` "
                "bedoeld is."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "naam": {
                        "type": "string",
                        "description": "Naam van de instelling of het bestuur zoals de gebruiker hem noemt, bijv. 'ROC Mondriaan'",
                    },
                },
                "required": ["naam"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_GET_DUO_DATA,
            "description": (
                "Laad een DUO open dataset. Retourneert kolomschema, voorbeeldwaarden en data_key — gebruik daarna "
                "query_data om gefilterde rijen op te halen voor analyse of grafiek. `teldefinitie` zegt wat DUO "
                "telt (bijv. personen of inschrijvingen): label aantallen daarmee, vergelijk geen datasets met een "
                "andere teldefinitie alsof ze gelijk zijn, en verklaar een verschil niet verder dan die definities. "
                "`publicatieregels` (bijv. aantallen 1–4 gepubliceerd als 4) maken kleine aantallen onzeker: "
                "noem een 4 dan geen exact aantal. Dat is iets anders dan een lege (-1) cel."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "CKAN package-naam uit de catalogus, bijv. 'studentprognoses-mbo-v1'",
                    },
                    "resource": {
                        "type": ["integer", "string"],
                        "description": "Index (0, 1, ...) uit _resources van dataset_details, of de exacte bestandsnaam. Zonder resource: het bestand met leidend_voor_totalen, anders 0. Een naamdeel dat op meerdere bestanden past laadt niets en noemt de opties.",
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_QUERY_DATA,
            "description": "Filter en selecteer rijen uit een geladen dataset. Werkt voor alle databronnen: DUO (data_key van get_duo_data), CBS (data_key van get_cbs_data), RIO (data_key van get_rio_data).",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_key": {
                        "type": "string",
                        "description": "data_key uit get_duo_data, get_cbs_data of get_rio_data",
                    },
                    "filters": {
                        "type": "object",
                        "description": 'Kolomfilters: exacte waarden bijv. {"Leerweg": "Voltijd"}, of range-operatoren: {"JAAR__gte": "2020"}, {"JAAR__lte": "2023"}, {"JAAR__in": ["2021","2022"]}',
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Alleen deze kolommen teruggeven",
                    },
                    "max_rows": {"type": "integer", "description": "Maximaal aantal rijen (default: 500)"},
                    "group_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Groepeer op deze kolommen (bijv. [\"STUDIEJAAR\"]). Vereist ook 'aggregate'.",
                    },
                    "aggregate": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "string",
                            "enum": ["sum", "mean", "count", "nunique", "size", "min", "max"],
                        },
                        "description": (
                            'Aggregatiefuncties per kolom, bijv. {"AANTAL": "sum"}. Alleen samen met \'group_by\'. '
                            "count = niet-lege waarden, nunique = verschillende waarden, size = rijen (ook lege)."
                        ),
                    },
                },
                "required": ["data_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_CREATE_CHOROPLETH_MAP,
            "description": (
                "Maak een interactieve kaart van Nederland met kleuren per regio. "
                "Gebruik bij voorkeur data_key om data rechtstreeks uit de store te lezen. "
                "De data moet CBS-regiocodes bevatten (bijv. 'PV20', 'GM0363')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data_key": {
                        "type": "string",
                        "description": "data_key van een query_data-resultaat. De kaart leest de data zelf uit de store; datarijen kunnen niet rechtstreeks worden meegegeven.",
                    },
                    "location_col": {
                        "type": "string",
                        "description": "Kolomnaam met de locaties: CBS-regiocodes ('RegioS' met 'GM0363' of 'PV20') of namen van provincies, gemeenten of COROP-gebieden (DUO: 'PROVINCIE INSTELLING', 'GEMEENTE INSTELLING'). Locaties die niet op de kaart staan worden in het antwoord genoemd.",
                    },
                    "value_col": {
                        "type": "string",
                        "description": "Kolomnaam met de numerieke waarden voor de kleurschaal",
                    },
                    "title": {"type": "string", "description": "Titel van de kaart"},
                    "level": {
                        "type": "string",
                        "enum": ["auto", "provincie", "gemeente", "corop"],
                        "description": "Geografisch niveau. 'auto' (standaard) leidt het af uit de codes of uit de niveau waar de namen op passen; een niveau waar geen enkele locatie bij past geeft een fout.",
                    },
                },
                "required": ["data_key", "location_col", "value_col", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_COMPUTE_KPI,
            "description": (
                "Bereken één KPI-waarde over data die al in de store staat. Gebruik dit voor ELK getal dat als KPI "
                "in een dashboard komt, inclusief verschillen en percentages. Reken zelf nooit een trend uit: geef "
                "de data_key en de maat op en neem de teruggegeven `value` en `trend` letterlijk over."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data_key": {"type": "string", "description": "data_key van een query_data-resultaat"},
                    "value_column": {"type": "string", "description": "Kolom met de numerieke waarden"},
                    "metric": {
                        "type": "string",
                        "enum": [
                            "last",
                            "first",
                            "sum",
                            "mean",
                            "min",
                            "max",
                            "delta",
                            "pct_change",
                            "index",
                            "max_drop",
                            "max_rise",
                        ],
                        "description": (
                            "last/first = laatste of eerste waarde, sum/mean/min/max = aggregaat over alle rijen, "
                            "delta = laatste min eerste, pct_change = procentuele verandering van eerste naar laatste, "
                            "index = laatste als index met de eerste waarde op 100, "
                            "max_drop/max_rise = grootste daling of stijging tussen twee opeenvolgende rijen, met in `tussen` "
                            "welke twee (gebruik dit voor 'grootste daling/stijging', zoek die niet zelf in de tabel). "
                            "Met sort_column staat in `periode` over welke schooljaren de uitkomst gaat: noem precies die."
                        ),
                    },
                    "sort_column": {
                        "type": "string",
                        "description": "Kolom om op te sorteren voor last/first/delta/pct_change/index/max_drop/max_rise, bijv. STUDIEJAAR. Zonder deze kolom telt de rijvolgorde.",
                    },
                    "label": {"type": "string", "description": "Label van de KPI, bijv. 'Voltijd 2025/26'"},
                    "van": {
                        "type": "integer",
                        "description": "Startjaar waarmee de reeks begint (2024 = 2024/25). Zonder `van` en `tot` rekent de KPI over alle rijen. Vereist sort_column.",
                    },
                    "tot": {
                        "type": "integer",
                        "description": "Startjaar waarmee de reeks eindigt, inclusief. Vereist sort_column.",
                    },
                },
                "required": ["data_key", "value_column", "metric", "label"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_CREATE_PLOT,
            "description": "Maak een interactieve grafiek van data die al in de store staat. Geef altijd de data_key van een query_data-resultaat; datarijen kunnen niet rechtstreeks worden meegegeven.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_key": {
                        "type": "string",
                        "description": "data_key van een query_data-resultaat. De grafiek leest de data zelf uit de store, zodat de getallen gelijk zijn aan wat de tool heeft berekend.",
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["auto", "bar", "line", "scatter", "pie", "histogram"],
                        "description": "Kies 'auto' tenzij je een specifiek type nodig hebt; de code bepaalt het dan uit de data (tijd-as zoals JAAR of PERIODE wordt line, een aandeel wordt pie bij maximaal 5 groepen en anders bar). Let op: 'histogram' en 'scatter' volgen nooit uit 'auto' en moet je zelf kiezen. Eén datapunt wordt alleen getekend met 'bar', en dat kies je alleen als de gebruiker om een grafiek vraagt.",
                    },
                    "x": {"type": "string", "description": "Veldnaam voor de x-as (of labels bij pie)"},
                    "y": {"type": "string", "description": "Veldnaam voor de y-as (of waarden bij pie)"},
                    "title": {"type": "string", "description": "Titel van de grafiek"},
                    "color_by": {
                        "type": "string",
                        "description": "Veldnaam om op te groeperen (bijv. 'Geslacht' voor man/vrouw vergelijking)",
                    },
                    "highlight": {
                        "type": "string",
                        "description": "De categorie met deze waarde krijgt de accentkleur, de rest wordt grijs. Gebruik dit als één categorie (bijv. één instelling in een benchmark) de aandacht moet krijgen. Zonder color_by is dat een waarde van x (één staaf); met color_by een groep. Zet color_by niet op de x-kolom om één staaf uit te lichten.",
                    },
                    "is_share": {
                        "type": "boolean",
                        "description": "Zet op true als de grafiek een aandeel of verhouding van een geheel toont (bijv. 'welk percentage van de studenten...'). Werkt alleen bij chart_type='auto' en stuurt de keuze richting pie of bar.",
                    },
                },
                "required": ["data_key", "chart_type", "x", "y", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_RUN_ANALYSIS,
            "description": (
                "Voer een kort pandas/numpy script uit op geladen data. "
                "Gebruik voor berekeningen die niet met query_data group_by/aggregate kunnen "
                "(percentuele groei, ratio's, custom transformaties). "
                "Wijs het resultaat toe aan 'result' (dict, list of DataFrame). "
                "Optioneel: wijs een Plotly figuur toe aan 'figure'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": (
                            "Python code. Beschikbaar: df (het DataFrame), pd, np, math, px, go, "
                            "store_get('key') voor extra datasets (key letterlijk). Wijs resultaat toe aan 'result'. "
                            "Geen imports, bestanden of netwerk."
                        ),
                    },
                    "data_key": {
                        "type": "string",
                        "description": "data_key van een geladen dataset. Het DataFrame is beschikbaar als 'df'.",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_CLARIFY_SCOPE,
            "description": (
                "Stel EXACT één gesloten vraag met 2 of 3 klikbare antwoordopties. "
                "Roep deze tool DIRECT aan — schrijf GEEN tekst vooraf, geen inleiding, geen uitleg. "
                "Dit is de ENIGE manier om scope-vragen te stellen — schrijf ze nooit als platte tekst. "
                "Gebruik bij een nieuwe analysevraag om open scope-dimensies vast te leggen. "
                "Sla dimensies over die al uit de vraag of het gebruikersprofiel blijken. "
                "Typisch 1–3 aanroepen. Als de vraag al specifiek genoeg is (3+ dimensies "
                "expliciet), sla deze tool over en ga direct naar search_catalog. "
                "Na deze tool is de beurt klaar — wacht op het antwoord van de gebruiker. "
                "Als het antwoord binnenkomt en er nog open scope-dimensies zijn, roep deze "
                "tool opnieuw aan — NOOIT de volgende vraag als platte tekst schrijven."
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
                                "label": {
                                    "type": "string",
                                    "description": "Korte antwoordtekst, bijv. 'Laatste schooljaar'",
                                },
                                "beschrijving": {
                                    "type": "string",
                                    "description": "Alleen voor bronopties: één zin over het verschil",
                                },
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
    {
        "type": "function",
        "function": {
            "name": TOOL_GET_UWV_VACATURES,
            "description": (
                "UWV-vacatures per provincie of gemeente en beroepencluster, optioneel voor één onderwijssector. "
                "Een momentopname (peildatum in het resultaat), geen reeks, niet per instelling en zonder "
                "opleidingsniveau. Arbeidsmarkt-context bij een onderwijsvraag. Het resultaat heeft een data_key: "
                "de tabel met alle beroepenclusters (BEROEPENCLUSTER, VACATURES) voor query_data en create_plot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "provincie": {
                        "type": "string",
                        "description": "Provincienaam, bijv. 'Utrecht', 'Noord-Holland'",
                    },
                    "sector": {
                        "type": "string",
                        "enum": sorted(SECTOR_CLUSTER_MAP),
                        "description": "Optioneel: de onderwijssector waarvan de beroepenclusters meetellen",
                    },
                    "gemeente": {
                        "type": "string",
                        "description": "Optioneel: een gemeente in die provincie, bijv. 'Amersfoort'",
                    },
                },
                "required": ["provincie"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_GET_ROA_BENCHMARK,
            "description": (
                "ROA (AIS 2030): schoolverlaters (SIS 2024: werkloosheid, vast dienstverband, buiten de "
                "vakrichting; alleen landelijk) en de prognose tot 2030 (landelijk, of per arbeidsmarktregio "
                "of provincie), per opleidingsniveau mbo2-4, bachelor en master, of voor één opleidingssector. "
                "Niet per instelling. Het resultaat heeft een data_key: de tabel met elk cijfer als rij "
                "(ONDERDEEL, REGIO, OPLEIDING, INDICATOR, PERCENTAGE, AANTAL, TYPERING) voor query_data en create_plot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {
                        "type": "string",
                        "description": (
                            "Optioneel: een ROA-opleidingssector, bijv. 'Mbo4 - techniek en ict' of "
                            "'Master - zorg en onderwijs'. Zonder sector: alle mbo/hbo/wo-niveaus."
                        ),
                    },
                    "regio": {
                        "type": "string",
                        "description": (
                            "Optioneel: een arbeidsmarktregio (bijv. 'Midden-Utrecht') of provincie (bijv. "
                            "'Utrecht'). Zonder regio: landelijk."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
]
