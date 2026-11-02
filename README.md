# Onderwijsdata Chat

**Een controleerbare chatbot voor onderwijsonderzoek.**

Stel vragen over CBS, RIO en DUO onderwijsdata. De app genereert antwoorden met volledig traceerbare bronnen — elke analyse exporteert automatisch als Python-code die je kunt auditen en reproduceren.

**Voor onderzoeksinstellingen:** de AI rekent nooit zelf. Elk getal komt uit een tool die op officiële CBS-, DUO- en RIO-data rekent en is herleidbaar tot de brontabel. Noemt het model toch een getal dat niet in de data staat, dan trekt een controle in code het antwoord in. De tekst stroomt live binnen en de controle draait daarna, dus het getal kan kort zichtbaar zijn voor het wordt ingetrokken; het ingetrokken antwoord blijft herkenbaar. Wat die controles wel en niet dekken staat in [Anti-hallucinatie architectuur](docs/anti-hallucination-architecture.md).

https://github.com/user-attachments/assets/9ab68b2a-7c00-4b2b-82ea-cbba245f1edb

De assistent heeft toegang tot CBS, RIO en DUO via tool calling en genereert antwoorden met volledige herkomstketen — per analysestap toont de app de Python-code die is uitgevoerd.

## Reproduceerbare analyses

**Elke analyse exporteert zichzelf als draaibare Python-code.** Dit is cruciaal voor onderzoeksinstellingen:

1. **Stel een vraag**: "Hoeveel eerstejaars hbo-studenten kozen per studiejaar voor techniek?"
2. **De app genereert**: Charts, KPI's, aggregaties
3. **Exporteer als Python**: De app genereert het exacte script dat je gebruikte — tool-aanroepen, filters, aggregaties — zodat je het resultaat kunt nazien en aanpassen
4. **Reproducibiliteit**: Perfect voor rapport, archief, of audit — iedereen kan je analyse opnieuw runnen

Voorbeeld: het script dat de app voor die vraag maakt (DUO `p02ho1ejrs`, resource 0: eerstejaars hbo). `ONDERDEEL` is
de sector van de opleiding, geen opleidingsnaam. Boven het script zet de app nog twee regels met de riodata-versie
waarmee het gemaakt is; `tests/test_readme_voorbeeld.py` draait dit voorbeeld tegen een bevroren kopie van het bestand.

```python
import pandas as pd
from riodata import duo

df = duo.load("p02ho1ejrs", 0)
# DUO-sentinel -1 = onderdrukte cel: DUO publiceert kleine aantallen niet, geen telwaarde. De app sluit ze uit.
# Totalen over een selectie met zulke cellen zijn een ondergrens.
for kolom in df.select_dtypes("number").columns:
    if not any(h in str(kolom).upper() for h in ("MUTATIE", "SALDO", "VERSCHIL", "GROEI", "DELTA")):
        df[kolom] = df[kolom].mask(df[kolom].isin([-1]))
if "STUDIEJAAR" in df.columns:
    df["STUDIEJAAR_LABEL"] = df["STUDIEJAAR"].map(lambda j: f"{j}/{j + 1}")
df = df[df["ONDERDEEL"].astype(str).str.lower().isin(["techniek"])]
group_by = ["STUDIEJAAR"]
if "STUDIEJAAR_LABEL" in df.columns and "STUDIEJAAR_LABEL" not in group_by:
    group_by.append("STUDIEJAAR_LABEL")
for kolom in ["AANTAL_EERSTEJAARS_INGESCHREVENEN"]:
    df[kolom] = pd.to_numeric(df[kolom], errors="coerce")
df = (
    df.groupby(group_by, dropna=False)
    .agg({"AANTAL_EERSTEJAARS_INGESCHREVENEN": lambda s: s.sum(min_count=1)})
    .reset_index()
)
print(df)
```

Zie [reproducibility.md](docs/reproducibility.md) voor details.

## Databronnen

| Bron | Inhoud | Catalogus |
|------|--------|-----------|
| **CBS** | 125 datasets met onderwijsstatistieken over mbo, hbo en wo; vier daarvan zijn vo-tabellen, alleen als vo-context voor ho | [cedanl.github.io/cbs-onderwijsdata](https://cedanl.github.io/cbs-onderwijsdata/) |
| **RIO** | Register van onderwijsinstellingen en opleidingen, met sectorfilter op mbo/hbo/wo (8 resources) | [cedanl.github.io/rio-onderwijsdata](https://cedanl.github.io/rio-onderwijsdata/) |
| **DUO** | 15 open datasets over mbo, hbo en wo: prognoses, diplomering, instroom, adressen; één daarvan (`voprognoses`) is alleen vo-context voor ho | [onderwijsdata.duo.nl](https://onderwijsdata.duo.nl) |
| **ROA** | Arbeidsmarkt-prognoses per opleidingsniveau en -sector (AIS 2030, schoolverlaters SIS 2024); in de chat via `get_roa_benchmark` en in de dashboards | — |
| **UWV** | Open match vacatures (momentopname mei 2023); in de chat via `get_uwv_vacatures` en in de dashboards | — |

## Vereisten

- [uv](https://docs.astral.sh/uv/) — Python package manager
- Een API key voor een ondersteund taalmodel (zie `.env.example`)

## Installatie

```bash
cp .env.example .env
# Vul je API key in .env in
uv sync
```

## Configuratie

Kopieer `.env.example` naar `.env` en stel minimaal `MODEL` en de bijbehorende API key in:

```dotenv
MODEL=anthropic/claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

Ondersteunde providers via [LiteLLM](https://docs.litellm.ai/docs/providers): Anthropic, OpenAI, Azure OpenAI, Azure AI Foundry, Google Gemini.

Optionele instellingen:

| Variabele | Standaard | Betekenis |
|-----------|-----------|-----------|
| `AVAILABLE_MODELS` | *(afgeleid uit API keys)* | Kommagescheiden lijst van modellen in de UI-picker, bijv. `azure_ai/claude-sonnet-4-6,azure_ai/gpt-4o`. Gebruik dit als je meerdere modellen via één provider aanbiedt. |
| `MAX_TOKENS` | `40960` | Maximum tokens per LLM-aanroep |
| `TEMPERATURE` | `0` | Sampling-temperatuur van het model; 0 voor herhaalbare analyses |
| `SEED` | `42` | Vaste seed voor providers die dat ondersteunen; de rest negeert hem |
| `MAX_TOOL_ITERATIONS` | `25` | Maximum tool-aanroepen per vraag |
| `CBS_ROW_LIMIT` | `5000` | Maximum rijen uit CBS-datasets |
| `RIO_PAGE_SIZE` | `50` | Maximum records per RIO-aanroep |
| `DUO_ROW_LIMIT` | `500` | Maximum rijen uit DUO-datasets |
| `MAX_HISTORY` | `40` | Maximum berichten in chat-geschiedenis (de eerste vraag blijft); de helft is het maximum aantal vragen per gesprek |
| `MAX_MESSAGE_CHARS` | `4000` | Maximum tekens per nieuw chatbericht; langere berichten weigert de server |
| `RUN_SLOW_S` | `20` | Seconden tot de chat onder de voortgang zegt dat het even kan duren |
| `RUN_TIMEOUT_S` | `300` | Seconden tot een vraag wordt gestopt |
| `GENEREER_TIMEOUT_S` | `480` | Seconden tot een rapport of dashboard aan de serverkant wordt gestopt (onder de 10 min van de frontend, #759) |

## Starten

```bash
make dev
```

De app herstart automatisch bij bestandswijzigingen.

### Bereikbaarheid vanuit de host-browser

`make dev` start de frontend op poort 5173 (`FRONTEND_PORT`) en de backend op 8000 (`BACKEND_PORT`); open de
frontend, lokaal op `http://localhost:5173`. Komen de poorten van de container niet op de host (bijvoorbeeld met
devcontainer-cli zonder VS Code), gebruik dan het IP van de container:

```bash
make url   # print de juiste URL, bijv. http://172.17.0.2:5173
```

## MCP-server

De catalogus is ook te doorzoeken vanuit een MCP-client (Claude Desktop, Cursor, VS Code), zonder de chat-app te draaien:

```bash
uv sync --extra mcp
uv run python mcp_server.py
```

Drie tools met dezelfde schema's als in de chat: `search_catalog` (altijd één JSON-envelope met `status`, `kandidaten` en `vervolgstap`), `dataset_details` en `dataset_counts`. Geen API-sleutel nodig; de datatools blijven bij de chat. Zie [docs/mcp.md](docs/mcp.md) voor de clientconfiguratie.
