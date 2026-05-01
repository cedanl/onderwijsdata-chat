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

[Ollama](https://ollama.com) laat je open modellen lokaal draaien — geen cloud API key nodig, geen data die de organisatie verlaat.

### Installatie

Installeer Ollama en pull een model:

```bash
# Installeer Ollama (zie https://ollama.com/download)
ollama pull gpt-oss:20b        # aanbevolen, goede tool calling
ollama pull llama3.1:8b        # alternatief
ollama pull qwen2.5:14b        # alternatief
```

### Configuratie

```dotenv
MODEL=ollama_chat/gpt-oss:20b
OPENAI_API_BASE=http://localhost:11434/v1
```

In Docker (als Ollama op de host draait):

```dotenv
MODEL=ollama_chat/gpt-oss:20b
OPENAI_API_BASE=http://host.docker.internal:11434/v1
```

!!! warning "Gebruik `ollama_chat/` — niet `ollama/`"
    LiteLLM heeft twee prefixen voor Ollama. Alleen `ollama_chat/` ondersteunt `tools` en `tool_choice`. De app heeft tool calling nodig om data op te halen bij CBS, RIO en DUO — met `ollama/` werken de databronnen niet.

!!! note "Geen API key nodig"
    Ollama vereist geen API key. De app toont ook geen waarschuwing over ontbrekende keys wanneer `MODEL` begint met `ollama_chat/` of `ollama/`.

### Aanbevolen modellen

| Model | Grootte | Opmerkingen |
|-------|---------|-------------|
| `gpt-oss:20b` | ~12 GB | Sterk in tool calling, aanbevolen |
| `llama3.1:8b` | 5 GB | Goede balans snelheid/kwaliteit |
| `qwen2.5:14b` | 9 GB | Complexere analyses |
| `mistral` | 4 GB | Meertalig, goed Nederlands |

Controleer de [Ollama library](https://ollama.com/library) op de tag **Tools** om te zien welke modellen tool calling ondersteunen.

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
| Ollama | `OPENAI_API_BASE` (bijv. `http://localhost:11434/v1`) |

Je hoeft dus alleen de variabelen in te stellen die bij jouw gekozen provider horen — de rest kan leeg blijven. Alle providers zijn ook gedocumenteerd in [`.env.example`](https://github.com/cedanl/onderwijsdata-chat/blob/main/.env.example).
