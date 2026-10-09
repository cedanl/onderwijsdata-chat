# Onderwijsdata Chat

**Een controleerbare chatbot voor onderwijsonderzoek.**

Stel vragen over CBS, RIO en DUO onderwijsdata. De app genereert antwoorden met volledig traceerbare bronnen — elke analyse exporteert automatisch als Python-code die je kunt auditen en reproduceren.

**Voor onderzoeksinstellingen:** de AI rekent nooit zelf. Elk getal komt uit een tool die op officiële CBS-, DUO- en RIO-data rekent en is herleidbaar tot de brontabel. Noemt het model toch een getal dat niet in de data staat, dan trekt een controle in code het antwoord in voordat het de gebruiker bereikt. Wat die controles wel en niet dekken staat in [Anti-hallucinatie architectuur](docs/anti-hallucination-architecture.md).

https://github.com/user-attachments/assets/9ab68b2a-7c00-4b2b-82ea-cbba245f1edb

De assistent heeft toegang tot CBS, RIO en DUO via tool calling en genereert antwoorden met volledige herkomstketen — per analysestap toont de app de Python-code die is uitgevoerd.

## Reproduceerbare analyses

**Elke analyse exporteert zichzelf als draaibare Python-code.** Dit is cruciaal voor onderzoeksinstellingen:

1. **Stel een vraag**: "Hoeveel HBO-studenten volgen Informatica?"
2. **De app genereert**: Charts, KPI's, aggregaties
3. **Exporteer als Python**: De app genereert het exacte script dat je gebruikte — tool-aanroepen, filters, aggregaties — zodat je het resultaat kunt nazien en aanpassen
4. **Reproducibiliteit**: Perfect voor rapport, archief, of audit — iedereen kan je analyse opnieuw runnen

Voorbeeld:
```python
from riodata import duo
import pandas as pd

df = duo.load("p02ho1ejrs", "...")
df = df[df["ONDERDEEL"] == "Informatica"]
df = df[df["OPLEIDINGSVORM"] == "VT"]
hbo = df.groupby("STUDIEJAAR")["AANTAL_INGESCHREVENEN"].sum()
print(hbo)
```

Zie [reproducibility.md](docs/reproducibility.md) voor details.

## Databronnen

| Bron | Inhoud | Catalogus |
|------|--------|-----------|
| **CBS** | 119 datasets met onderwijsstatistieken over mbo, hbo en wo | [cedanl.github.io/cbs-onderwijsdata](https://cedanl.github.io/cbs-onderwijsdata/) |
| **RIO** | Register van onderwijsinstellingen en opleidingen, met sectorfilter op mbo/hbo/wo (9 resources) | [cedanl.github.io/rio-onderwijsdata](https://cedanl.github.io/rio-onderwijsdata/) |
| **DUO** | 14 open datasets over mbo, hbo en wo: prognoses, diplomering, instroom, adressen | [onderwijsdata.duo.nl](https://onderwijsdata.duo.nl) |
| **ROA** | Arbeidsmarkt-analyses per opleidingsniveau (AIS2030); alleen dashboards, niet via de chat | — |
| **UWV** | Open match vacatures (momentopname mei 2023); alleen dashboards, niet via de chat | — |

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
| `MAX_HISTORY` | `40` | Maximum berichten in chat-geschiedenis |
| `MAX_MESSAGE_CHARS` | `4000` | Maximum tekens per nieuw chatbericht; langere berichten weigert de server |
| `RUN_SLOW_S` | `20` | Seconden tot de melding "dit duurt langer dan normaal" |
| `RUN_TIMEOUT_S` | `300` | Seconden tot een vraag wordt gestopt |

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