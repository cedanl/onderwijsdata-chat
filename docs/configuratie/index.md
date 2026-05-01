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
| `MAX_TOKENS` | `40960` | Maximum tokens per LLM-aanroep |
| `MAX_TOOL_ITERATIONS` | `100` | Maximum tool-aanroepen per vraag |
| `CBS_ROW_LIMIT` | `200` | Maximum rijen uit CBS-datasets |
| `RIO_PAGE_SIZE` | `50` | Maximum records per RIO-aanroep |

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
