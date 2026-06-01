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
| `AVAILABLE_MODELS` | *(afgeleid uit API keys)* | Kommagescheiden lijst van modellen in de model-picker — zie [Model-picker](#model-picker) |
| `MAX_TOKENS` | `40960` | Maximum tokens per LLM-aanroep |
| `MAX_TOOL_ITERATIONS` | `100` | Maximum tool-aanroepen per vraag |
| `CBS_ROW_LIMIT` | `200` | Maximum rijen uit CBS-datasets |
| `RIO_PAGE_SIZE` | `50` | Maximum records per RIO-aanroep |

---

## Modus-picker

De app biedt twee analysemodi die gebruikers bovenin de chat kunnen kiezen:

| Modus | Gedrag |
|-------|--------|
| **Snel** *(standaard)* | Beantwoordt precies wat gevraagd is — geen automatische grafieken of uitgebreide interpretatie |
| **Verdiep** | Vraagt eerst door naar de vraag achter de vraag, daarna een volledige analyse met grafiek en interpretatie |

Geen configuratie nodig — de picker verschijnt automatisch in de UI.

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
| `CHAINLIT_AUTH_SECRET` | *(niet ingesteld)* | JWT-secret voor sessiebeheer. Genereer met `chainlit create-secret`. Zonder dit geen login en geen history. |
| `CHAT_USERS` | *(niet ingesteld)* | Wachtwoord-authenticatie: `user:pass,user2:pass2`. Vereist dat `CHAINLIT_AUTH_SECRET` is ingesteld. |
| `CHAT_HEADER_SECRET` | *(niet ingesteld)* | Header-authenticatie voor reverse proxy: stuur `X-Chat-Secret: <waarde>` mee. Optioneel ook `X-Chat-User: <identifier>`. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./chat_history.db` | Database voor gespreksopslag. Standaard lokale SQLite. Voor productie: `postgresql+asyncpg://user:pass@host/db`. |

!!! info "Authenticatie is optioneel"
    Zonder `CHAINLIT_AUTH_SECRET` werkt de app volledig zonder login. Chatgeschiedenis vereist zowel het secret als minimaal één authenticatiemethode.

---

## SURF Willma AI-Hub

Willma is de AI-Hub van SURF voor het Nederlandse onderwijs. Om via Willma te draaien:

```dotenv
MODEL=openai/<model-naam>
WILLMA_API_KEY=<jouw-willma-key>
WILLMA_BASE_URL=<endpoint-url>
```

Gebruik `willma_poc.py` om beschikbare modelnamen op te halen:

```bash
uv run python willma_poc.py
```

!!! note "Hoe werkt dit in de code?"
    Wanneer `WILLMA_API_KEY` is ingesteld, worden `api_base`, `api_key` en een `X-API-KEY` header automatisch meegegeven aan elke LiteLLM-aanroep (zie `agent.py`). Voor alle andere providers regelt LiteLLM de authenticatie op basis van standaard omgevingsvariabelen.

---

Zie [Providers & modellen](providers.md) voor een overzicht van alle ondersteunde providers met voorbeeldconfiguraties.
