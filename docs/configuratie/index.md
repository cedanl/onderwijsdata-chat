# Configuratie

Alle instellingen worden beheerd via het `.env` bestand. Kopieer `.env.example` naar `.env` en pas de waarden aan.

## Verplichte instellingen

| Variabele | Beschrijving |
|-----------|--------------|
| `MODEL` | Model in LiteLLM-formaat: `provider/model-naam` — zie [Providers & modellen](providers.md) |
| API key | Afhankelijk van de provider: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc. |

Minimale configuratie voor Anthropic:

```dotenv
MODEL=anthropic/claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Optionele instellingen

| Variabele | Standaard | Beschrijving |
|-----------|-----------|--------------|
| `AVAILABLE_MODELS` | *(niet ingesteld)* | Kommagescheiden lijst van modellen in de model-picker — zie [Model-picker](#model-picker) |
| `MAX_TOKENS` | `40960` | Maximum tokens per LLM-aanroep |
| `MAX_TOOL_ITERATIONS` | `100` | Maximum tool-aanroepen per vraag |
| `MAX_HISTORY` | `40` | Maximum aantal berichten in gespreksgeschiedenis |
| `CBS_ROW_LIMIT` | `5000` | Maximum rijen uit CBS-datasets |
| `RIO_PAGE_SIZE` | `50` | Maximum records per RIO-aanroep |
| `DUO_ROW_LIMIT` | `500` | Maximum rijen uit DUO-datasets |

---

## Model-picker

De model-picker verschijnt alleen als `AVAILABLE_MODELS` is ingesteld. Zonder deze instelling gebruikt de app altijd het `MODEL` uit `.env` — geen picker, geen keuze.

```dotenv
AVAILABLE_MODELS=azure_ai/claude-sonnet-4-6,azure_ai/claude-haiku-4-5,azure_ai/gpt-4o
MODEL=azure_ai/claude-sonnet-4-6
```

`MODEL` bepaalt welk model standaard geselecteerd is in de picker. Zet dit op één van de modellen in `AVAILABLE_MODELS`.

Modellen van verschillende providers kunnen gecombineerd worden — LiteLLM leest per provider automatisch de juiste API keys:

```dotenv
AVAILABLE_MODELS=anthropic/claude-sonnet-4-6,openai/gpt-4o,ollama_chat/llama3.1:8b,deepseek/deepseek-chat
```

!!! warning "Zet altijd alle benodigde API keys"
    Elk model in `AVAILABLE_MODELS` moet via de bijbehorende omgevingsvariabele bereikbaar zijn. Een model in de picker zonder werkende API key geeft een foutmelding bij gebruik.

---

## Chatgeschiedenis & authenticatie

| Variabele | Standaard | Beschrijving |
|-----------|-----------|--------------|
| `CHAT_SECRET` | *(per herstart gegenereerd)* | HMAC-secret voor sessiebeheer. Stel in voor stabiele tokens die herstarts overleven. |
| `CHAT_USERS` | *(niet ingesteld)* | Wachtwoord-authenticatie: `user:pass,user2:pass2`. Vereist dat `CHAT_SECRET` is ingesteld. |

!!! info "Authenticatie is optioneel"
    Zonder `CHAT_USERS` werkt de app volledig zonder login. Chatgeschiedenis vereist zowel `CHAT_SECRET` als `CHAT_USERS`.

---

## SURF Willma AI-Hub

Willma is de AI-Hub van SURF voor het Nederlandse onderwijs. Om via Willma te draaien:

```dotenv
MODEL=openai/<model-naam>
WILLMA_API_KEY=<jouw-willma-key>
WILLMA_BASE_URL=https://willma.surf.nl/api/v0
```

Gebruik `playground/willma_poc.py` om beschikbare modelnamen op te halen:

```bash
uv run python playground/willma_poc.py
```

!!! note "Hoe werkt dit in de code?"
    Wanneer `WILLMA_API_KEY` is ingesteld, worden `api_base`, `api_key` en een `X-API-KEY` header automatisch meegegeven aan elke LiteLLM-aanroep (zie `agent/models.py`). Voor alle andere providers regelt LiteLLM de authenticatie op basis van standaard omgevingsvariabelen.

---

Zie [Providers & modellen](providers.md) voor een overzicht van alle ondersteunde providers met voorbeeldconfiguraties.
