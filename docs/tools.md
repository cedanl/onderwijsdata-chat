# Tools

De assistent beschikt over de volgende tools. Ze worden automatisch ingezet op basis van je vraag — je hoeft ze niet expliciet aan te roepen.

Bij elke tool-aanroep wordt een reproduceerbaar Python-snippet getoond in de chat, zodat je de analyse lokaal kunt herhalen.

---

## search_catalog

Doorzoekt de gecombineerde catalogus van CBS, RIO en DUO.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `query` | string | Zoekterm, bijv. `"mbo studenten prognose"` |
| `source` | string | `"cbs"`, `"rio"`, `"duo"` of `"both"` (standaard: alles) |
| `top_n` | integer | Maximaal aantal resultaten (standaard: 15) |
| `geo_niveau` | string | Filter op geografisch niveau (optioneel) |

**Gebruik:** Als startpunt bij onduidelijke vragen of om te verkennen welke datasets beschikbaar zijn.

---

## get_cbs_data

Haalt rijen op uit een CBS-dataset via de OData API.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `dataset_id` | string | CBS dataset-ID, bijv. `"85423NED"` |
| `filters` | object | OData-parameters, bijv. `{"$filter": "Geslacht eq 'T001038'"}` |

---

## get_cbs_dimension

Haalt de mogelijke waarden op van een dimensie in een CBS-dataset. Handig om te zien welke filterwaarden beschikbaar zijn.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `dataset_id` | string | CBS dataset-ID |
| `dimension_name` | string | Naam van de dimensie, bijv. `"Geslacht"` |

---

## get_rio_data

Haalt records op uit het RIO-register.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `resource` | string | Resource naam, bijv. `"onderwijslocaties"` |
| `filters` | object | Filterparameters, bijv. `{"organisatorischeEenheidcode": "25LH"}` |

Zie [Databronnen → RIO](databronnen.md) voor beschikbare resources.

---

## get_duo_data

Laadt een DUO open dataset. Retourneert kolomschema, voorbeeldwaarden en een `data_key` voor vervolgquery's.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `dataset_id` | string | CKAN package-naam, bijv. `"studentprognoses-mbo-v1"` |
| `resource` | integer \| string | Index of naam-substring van het bestand binnen de dataset (standaard: 0) |

!!! note
    De geladen data wordt gecached in de sessie. Roep `get_duo_data` eenmalig aan per dataset en gebruik daarna `query_data` voor gefilterde analyses.

---

## query_data

Filtert, groepeert en aggregeert rijen uit gecachede data. Werkt voor alle databronnen na het ophalen (CBS, RIO, DUO) en voor resultaten van `run_analysis`.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `data_key` | string | Sleutel uit een eerdere tool-aanroep, bijv. `duo:123:0`, `cbs:85423NED` |
| `filters` | object | Kolomfilters met operators: `{"Jaar": {"gte": "2020"}}`, of exact: `{"Leerweg": "Voltijd"}` |
| `columns` | array | Alleen deze kolommen teruggeven |
| `max_rows` | integer | Maximaal aantal rijen (standaard: 500) |
| `group_by` | array | Groeperen op deze kolommen |
| `aggregate` | object | Aggregatiefuncties per kolom, bijv. `{"Aantal": "sum"}` |

---

## run_analysis

Voert pandas/numpy-code uit in een beveiligde sandbox op eerder opgehaalde data.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `code` | string | Python-code (pandas, numpy, plotly express beschikbaar) |
| `data_key` | string | Optionele data_key — het bijbehorende DataFrame is beschikbaar als `df` |

De sandbox blokkeert imports, `exec`, `eval`, `os`, `sys` en andere onveilige operaties. Beschikbare namen: `pd`, `np`, `math`, `px`, `go`.

---

## create_plot

Maakt een interactieve Plotly-grafiek.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `chart_type` | string | `"bar"`, `"line"`, `"scatter"`, `"pie"` of `"histogram"` |
| `x` | string | Veldnaam voor de x-as (of labels bij pie) |
| `y` | string | Veldnaam voor de y-as (of waarden bij pie) |
| `title` | string | Titel van de grafiek |
| `data_key` | string | Data_key van eerder opgehaalde data (optioneel, alternatief voor `data`) |
| `data` | array | Lijst van datarijen als objecten (optioneel, alternatief voor `data_key`) |
| `color_by` | string | Veldnaam voor groepering (optioneel) |

De grafiek wordt direct in de chat weergegeven.

---

## create_choropleth_map

Maakt een choropleth-kaart van Nederland op provincie-, gemeente- of COROP-niveau.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `location_col` | string | Kolomnaam met locatienamen |
| `value_col` | string | Kolomnaam met waarden |
| `title` | string | Titel van de kaart |
| `data_key` | string | Data_key van eerder opgehaalde data (optioneel) |
| `data` | array | Lijst van datarijen als objecten (optioneel) |
| `level` | string | `"auto"`, `"provincie"`, `"gemeente"` of `"corop"` (standaard: auto) |

---

## clarify_scope

Stelt een verduidelijkingsvraag aan de gebruiker wanneer de oorspronkelijke vraag meerdere interpretaties heeft.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `vraag` | string | De verduidelijkingsvraag |
| `opties` | array | 2-3 keuzes met `label`, `beschrijving` en `aanbevolen` (boolean) |

Deze tool wordt afgehandeld door de UI — de gebruiker ziet een keuzemenu en kan een optie selecteren.
