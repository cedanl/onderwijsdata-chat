"""
Willma AI-Hub proof-of-concept.

Zet WILLMA_API_KEY en WILLMA_BASE_URL in je .env bestand en run:
    uv run python willma_poc.py
"""

import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("WILLMA_API_KEY")
BASE_URL = os.getenv("WILLMA_BASE_URL")

if not API_KEY:
    sys.exit("Stel WILLMA_API_KEY in als omgevingsvariabele.")
if not BASE_URL:
    sys.exit("Stel WILLMA_BASE_URL in als omgevingsvariabele.")

HEADERS = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}


def list_models() -> list[dict]:
    # Willma noemt modellen "sequences"; /models is de OpenAI-compat alias
    for path in ("/sequences", "/models"):
        resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)
        if resp.ok:
            data = resp.json()
            # /sequences geeft een list, /models geeft {"data": [...]}
            return data if isinstance(data, list) else data.get("data", [])
    resp.raise_for_status()
    return []


def chat(model: str, messages: list[dict], stream: bool = False) -> str:
    payload = {"model": model, "messages": messages, "stream": stream}
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers=HEADERS,
        data=json.dumps(payload),
        stream=stream,
        timeout=60,
    )
    resp.raise_for_status()

    if not stream:
        return resp.json()["choices"][0]["message"]["content"]

    # Server-sent events: collect streamed content
    parts: list[str] = []
    for line in resp.iter_lines():
        if not line:
            continue
        raw = line.decode() if isinstance(line, bytes) else line
        if raw.startswith("data: "):
            raw = raw[6:]
        if raw.strip() == "[DONE]":
            break
        try:
            chunk = json.loads(raw)
            if not chunk.get("choices"):
                continue
            delta = chunk["choices"][0].get("delta", {})
            if content := delta.get("content"):
                parts.append(content)
                print(content, end="", flush=True)
        except (json.JSONDecodeError, KeyError):
            pass
    print()
    return "".join(parts)


if __name__ == "__main__":
    models = list_models()

    print("=== Tekst-modellen (bruikbaar voor chat) ===")
    text_models = [m for m in models if m.get("sequence_type") == "text"]
    for m in text_models:
        always = m.get("latency_mode") == "always-on"
        print(f"  {'✓' if always else '~'} MODEL=openai/{m['name']}")

    if not text_models:
        sys.exit("Geen tekstmodellen gevonden.")

    # Kies het eerste always-on tekst-model
    model_name = next(
        (m["name"] for m in text_models if m.get("latency_mode") == "always-on"),
        text_models[0]["name"],
    )
    print(f"\n=== Chat met '{model_name}' ===")

    answer = chat(model_name, [{"role": "user", "content": "Hoi! Geef een korte begroeting in het Nederlands."}])
    print("Antwoord:", answer)

    print("\n=== Streaming ===")
    chat(
        model_name,
        [{"role": "user", "content": "Noem drie feiten over het Nederlandse onderwijs."}],
        stream=True,
    )
