# Onderwijsdata Chat

Een chatapp (FastAPI + React) waarmee je vragen kunt stellen over open Nederlandse onderwijsdata.

https://github.com/user-attachments/assets/9ab68b2a-7c00-4b2b-82ea-cbba245f1edb

De assistent heeft toegang tot CBS, RIO en DUO via tool calling, ondersteunt uploads van eigen xlsx/csv-bestanden, en kan Plotly-grafieken genereren en analyses exporteren als HTML-rapport, PDF of reproduceerbaar Python-pakket.

## Databronnen

| Bron | Inhoud | Catalogus |
|------|--------|-----------|
| **CBS** | 68 datasets met onderwijsstatistieken | [cedanl.github.io/cbs-onderwijsdata](https://cedanl.github.io/cbs-onderwijsdata/) |
| **RIO** | Register van onderwijsinstellingen en opleidingen (14 resources) | [cedanl.github.io/rio-onderwijsdata](https://cedanl.github.io/rio-onderwijsdata/) |
| **DUO** | 57 open datasets: prognoses, diplomering, instroom, adressen | [onderwijsdata.duo.nl](https://onderwijsdata.duo.nl) |
| **Eigen bestanden** | xlsx/csv-uploads — direct bevraagbaar via dezelfde interface | — |

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
| `MAX_TOOL_ITERATIONS` | `100` | Maximum tool-aanroepen per vraag |
| `CBS_ROW_LIMIT` | `200` | Maximum rijen uit CBS-datasets |
| `RIO_PAGE_SIZE` | `50` | Maximum records per RIO-aanroep |

## Starten

```bash
make dev
```

De app herstart automatisch bij bestandswijzigingen.

### Bereikbaarheid vanuit de host-browser

**VS Code devcontainer** — poorten worden automatisch doorgestuurd, open gewoon:
```
http://localhost:8000
```

**devcontainer-cli (plain Docker, geen VS Code)** — `forwardPorts` in `devcontainer.json` werkt niet zonder VS Code. Gebruik het container-bridge-IP:

```bash
make url   # print de juiste URL, bijv. http://172.17.0.2:8000
```

Open die URL in je host-browser.

## Projectstructuur

```
server.py           # FastAPI-app: REST endpoints, WebSocket chat, static file serving
app.py              # Entrypoint: start uvicorn
auth.py             # JWT-authenticatie (optioneel, gebruikersnaam/wachtwoord)
config.py           # Omgevingsvariabelen
prompt.py           # Systeemprompts
export.py           # HTML- en PDF-rapportgeneratie
agent/
  run.py            # Agentic loop met streaming en tool calling via LiteLLM
  models.py         # LiteLLM-kwargs en systeemprompt samenstellen
  history.py        # Gespreksgeschiedenis inkorten
  title.py          # Gesprekstitel genereren
frontend/           # React + Vite frontend
  src/
    components/     # Chat, sidebar, modals, pickers
    pages/          # Hoofd- en loginpagina
persistence/
  db.py             # SQLite gespreksopslag
tools/
  cbs.py            # CBS Open Data API
  duo.py            # DUO open datasets (onderwijsdata.duo.nl) + generieke query_data
  rio.py            # RIO register
  catalog.py        # Dataset-catalogus zoeken
  plot.py           # Plotly-grafieken
  store.py          # In-memory sessiecache voor DataFrames (DUO + uploads)
  codegen/          # Reproduceerbare Python-pakketgeneratie (analyse.py/.ipynb/requirements)
playground/
  willma_poc.py     # SURF Willma AI-Hub proof-of-concept
```
