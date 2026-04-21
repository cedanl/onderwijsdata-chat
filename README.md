# Onderwijsdata Chat

Een Chainlit-chatapp waarmee je vragen kunt stellen over open Nederlandse onderwijsdata. De assistent heeft toegang tot CBS, RIO en DUO via tool calling en kan Plotly-grafieken genereren en een downloadbaar HTML-rapport produceren.

## Databronnen

| Bron | Inhoud | Catalogus |
|------|--------|-----------|
| **CBS** | 68 datasets met onderwijsstatistieken | [cedanl.github.io/cbs-onderwijsdata](https://cedanl.github.io/cbs-onderwijsdata/) |
| **RIO** | Register van onderwijsinstellingen en opleidingen (14 resources) | [cedanl.github.io/rio-onderwijsdata](https://cedanl.github.io/rio-onderwijsdata/) |
| **DUO** | 57 open datasets: prognoses, diplomering, instroom, adressen | [onderwijsdata.duo.nl](https://onderwijsdata.duo.nl) |

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
| `MAX_TOKENS` | `40960` | Maximum tokens per LLM-aanroep |
| `MAX_TOOL_ITERATIONS` | `100` | Maximum tool-aanroepen per vraag |
| `CBS_ROW_LIMIT` | `200` | Maximum rijen uit CBS-datasets |

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
app.py          # Chainlit entry point, chat-events en rapport-download
agent.py        # Agentic loop met streaming en tool calling via LiteLLM
config.py       # Omgevingsvariabelen
prompt.py       # Systeemprompt
report.py       # HTML-rapportgeneratie
tools/
  cbs.py        # CBS Open Data API
  duo.py        # DUO open datasets (onderwijsdata.duo.nl)
  rio.py        # RIO register
  catalog.py    # Dataset-catalogus zoeken
  plot.py       # Plotly-grafieken
```
