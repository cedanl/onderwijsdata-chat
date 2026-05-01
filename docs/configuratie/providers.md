# Providers & modellen

De app gebruikt [LiteLLM](https://docs.litellm.ai/docs/providers) als universele adapter. Dit betekent dat je met één instelling (`MODEL` in `.env`) kunt wisselen tussen vrijwel alle grote taalmodellen — zonder code te wijzigen.

Het `MODEL` veld volgt altijd het formaat `provider/model-naam`.

---

## Cloud providers

=== "Anthropic"
    ```dotenv
    MODEL=anthropic/claude-sonnet-4-6
    ANTHROPIC_API_KEY=sk-ant-...
    ```
    Andere modellen: `claude-opus-4-7`, `claude-haiku-4-5-20251001`

=== "OpenAI"
    ```dotenv
    MODEL=openai/gpt-4o
    OPENAI_API_KEY=sk-...
    ```

=== "Google Gemini"
    ```dotenv
    MODEL=gemini/gemini-1.5-pro
    GEMINI_API_KEY=...
    ```

=== "Azure OpenAI"
    ```dotenv
    MODEL=azure/gpt-4o
    AZURE_API_KEY=...
    AZURE_API_BASE=https://<resource>.openai.azure.com
    AZURE_API_VERSION=2024-02-01
    ```

=== "Azure AI Foundry"
    Claude via Foundry:
    ```dotenv
    MODEL=azure_ai/claude-sonnet-4-5
    AZURE_AI_API_KEY=...
    AZURE_AI_API_BASE=https://<resource>.services.ai.azure.com/anthropic
    ```

    Open modellen (Llama, Mistral, Phi):
    ```dotenv
    MODEL=azure_ai/Llama-3.1-70B-Instruct
    AZURE_AI_API_KEY=...
    AZURE_AI_API_BASE=https://<endpoint>.services.ai.azure.com/models
    ```

---

## Lokale modellen met Ollama

[Ollama](https://ollama.com) laat je open modellen lokaal draaien — geen API key nodig, geen data die de organisatie verlaat.

### Installatie

Installeer Ollama en pull een model:

```bash
# Installeer Ollama (zie https://ollama.com/download)
ollama pull llama3.2          # ~2 GB, geschikt voor eenvoudige vragen
ollama pull qwen2.5:14b       # betere redeneervaardigheden, ~9 GB
ollama pull mistral            # goede balans snelheid/kwaliteit
```

### Configuratie

```dotenv
MODEL=ollama/llama3.2
# OLLAMA_API_BASE hoeft niet ingesteld te worden als Ollama op localhost:11434 draait
```

Als Ollama op een ander adres draait (bijv. in een Docker-netwerk):

```dotenv
MODEL=ollama/llama3.2
OLLAMA_API_BASE=http://host.docker.internal:11434
```

### Aanbevolen modellen

| Model | Grootte | Geschikt voor |
|-------|---------|---------------|
| `llama3.2` | 2 GB | Snelle vragen, weinig RAM |
| `llama3.1:8b` | 5 GB | Goede balans |
| `qwen2.5:14b` | 9 GB | Complexere analyses |
| `mistral` | 4 GB | Meertalig, goed Nederlands |
| `qwen2.5-coder:7b` | 4 GB | Code-heavy taken |

!!! tip "Tool calling"
    Niet elk Ollama-model ondersteunt tool calling (nodig voor het ophalen van CBS/RIO/DUO-data). Kies een model dat expliciet tool use ondersteunt, zoals `llama3.1`, `llama3.2`, `qwen2.5` of `mistral-nemo`. Controleer de [Ollama library](https://ollama.com/library) voor de tag `Tools`.

!!! note "Hoe werkt dit?"
    LiteLLM herkent het prefix `ollama/` en routeert de aanroep automatisch naar de lokale Ollama-server. De `OLLAMA_API_BASE` variabele overschrijft het standaard adres (`http://localhost:11434`). Er is geen API key nodig.

---

## SURF Willma AI-Hub

Willma biedt toegang tot open modellen voor het Nederlandse onderwijs via SURF. Zie [Configuratie](index.md#surf-willma-ai-hub) voor de instelling.

---

## Hoe LiteLLM providers koppelt

LiteLLM leest omgevingsvariabelen automatisch per provider:

| Provider | Omgevingsvariabele |
|----------|--------------------|
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Azure OpenAI | `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION` |
| Azure AI Foundry | `AZURE_AI_API_KEY`, `AZURE_AI_API_BASE` |
| Gemini | `GEMINI_API_KEY` |
| Ollama | `OLLAMA_API_BASE` (optioneel, standaard `http://localhost:11434`) |

Je hoeft dus alleen de variabelen in te stellen die bij jouw gekozen provider horen — de rest kan leeg blijven. Alle providers zijn ook gedocumenteerd in [`.env.example`](https://github.com/cedanl/onderwijsdata-chat/blob/main/.env.example).
