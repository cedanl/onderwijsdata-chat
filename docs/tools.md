# Tools

De assistent beschikt over de volgende tools. Ze worden automatisch ingezet op basis van je vraag — je hoeft ze niet expliciet aan te roepen.

---

## search_catalog

Doorzoekt de gecombineerde catalogus van CBS, RIO en DUO.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `query` | string | Zoekterm, bijv. `"mbo studenten prognose"` |
| `source` | string | `"cbs"`, `"rio"`, `"duo"` of `"both"` (standaard: alles) |
| `top_n` | integer | Maximaal aantal resultaten (standaard: 15) |

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
    De geladen data wordt gecached in de sessie. Roep `get_duo_data` eenmalig aan per dataset en gebruik daarna `query_duo_data` voor gefilterde analyses.

---

## query_duo_data

Filtert en selecteert rijen uit een eerder geladen DUO-dataset.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `data_key` | string | Sleutel uit `get_duo_data` |
| `filters` | object | Exacte kolomfilters, bijv. `{"Leerweg": "Voltijd", "Jaar": "2023"}` |
| `columns` | array | Alleen deze kolommen teruggeven |
| `max_rows` | integer | Maximaal aantal rijen (standaard: 500) |

---

## create_plot

Maakt een interactieve Plotly-grafiek van opgehaalde data.

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `data` | array | Lijst van datarijen als objecten |
| `chart_type` | string | `"bar"`, `"line"`, `"scatter"`, `"pie"` of `"histogram"` |
| `x` | string | Veldnaam voor de x-as (of labels bij pie) |
| `y` | string | Veldnaam voor de y-as (of waarden bij pie) |
| `title` | string | Titel van de grafiek |
| `color_by` | string | Veldnaam voor groepering (optioneel, bijv. `"Geslacht"`) |

De grafiek wordt direct in de chat weergegeven en opgenomen in het HTML-rapport.

---

## Rapport downloaden

Na een of meer grafieken verschijnt de knop **"Download rapport"** onder het laatste antwoord. Het rapport bevat alle grafieken en teksten van de sessie als zelfstandig HTML-bestand.
