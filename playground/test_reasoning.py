"""
Test GPT-OSS-120B reasoning modes en tool calling via Willma.

Test drie dingen:
1. Werkt 'Reasoning: high/medium/low' in het system-prompt?
2. Kan het model tools aanroepen (function calling)?
3. Hoe vergelijkt het met Qwen3?

Run:  uv run python playground/test_reasoning.py
"""

import json
import os
import sys
import time

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

# ── Modellen ──────────────────────────────────────────────────────────
GPT_OSS = "openai/gpt-oss-120b"
# Qwen3 variants op Willma (pas aan indien beschikbaar)
QWEN3_CANDIDATES = [
    "openai/Qwen/Qwen3.6-27B-FP8",
    "openai/Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
    "openai/Qwen/Qwen2.5-VL-32B-Instruct-AWQ",
]


def list_models() -> list[dict]:
    for path in ("/sequences", "/models"):
        resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)
        if resp.ok:
            data = resp.json()
            return data if isinstance(data, list) else data.get("data", [])
    resp.raise_for_status()
    return []


def chat(
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    extra: dict | None = None,
    timeout: int = 120,
) -> dict:
    """Stuur een chat-completions request en retourneer het volledige antwoord."""
    payload: dict = {"model": model, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools
    if extra:
        payload.update(extra)

    t0 = time.perf_counter()
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers=HEADERS,
        data=json.dumps(payload),
        timeout=timeout,
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if not resp.ok:
        return {"error": f"HTTP {resp.status_code}: {resp.text[:500]}", "elapsed_ms": elapsed_ms}

    data = resp.json()
    choice = data["choices"][0]
    msg = choice["message"]

    result = {
        "content": msg.get("content", ""),
        "tool_calls": msg.get("tool_calls"),
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage", {}),
        "elapsed_ms": elapsed_ms,
        "model": data.get("model", model),
    }
    # Reasoning tokens (indien aanwezig — GPT-OSS retourneert deze mogelijk)
    if "reasoning_content" in msg:
        result["reasoning_content"] = msg["reasoning_content"]
    return result


# ── Test 1: Reasoning modes ───────────────────────────────────────────

REASONING_TEST_MSG = [
    {
        "role": "user",
        "content": (
            "Ik heb een vraag over Nederlandse onderwijsdata. "
            "Welke dataset uit de CBS-catalogus bevat het meest gedetailleerde "
            "gegevens over het aantal MBO-studenten per gemeente, per schooljaar?"
        ),
    }
]

SYSTEM_HIGH = [{"role": "system", "content": "Reasoning: high"}]
SYSTEM_MEDIUM = [{"role": "system", "content": "Reasoning: medium"}]
SYSTEM_LOW = [{"role": "system", "content": "Reasoning: low"}]
SYSTEM_NO_REASONING: list[dict] = []


def test_reasoning_modes(model: str):
    print(f"\n{'='*60}")
    print(f"  TEST 1: Reasoning modes — {model}")
    print(f"{'='*60}")

    configs = [
        ("Geen reasoning", SYSTEM_NO_REASONING),
        ("Reasoning: low", SYSTEM_LOW),
        ("Reasoning: medium", SYSTEM_MEDIUM),
        ("Reasoning: high", SYSTEM_HIGH),
    ]

    for label, system in configs:
        messages = system + REASONING_TEST_MSG
        print(f"\n--- {label} ---")
        result = chat(model, messages)

        if "error" in result:
            print(f"  ERROR: {result['error']}")
            continue

        content = result["content"] or ""
        reasoning = result.get("reasoning_content", "")
        usage = result.get("usage", {})

        print(f"  Antwoord ({result['elapsed_ms']}ms): {content[:200]}...")
        if reasoning:
            print(f"  Reasoning trace ({len(str(reasoning))} chars): {str(reasoning)[:200]}...")
        print(f"  Tokens: {usage}")


# ── Test 2: Tool calling ──────────────────────────────────────────────

MOCK_CATALOG_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": (
                "Zoek in de CBS-, RIO- en DUO-catalogus naar relevante datasets. "
                "Retourneert maximaal 15 resultaten met metadata."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Zoekterm, bijv. 'mbo studenten gemeente'",
                    },
                    "source": {
                        "type": "string",
                        "enum": ["cbs", "rio", "duo", "both"],
                        "description": "Te doorzoeken bron",
                    },
                    "geo_niveau": {
                        "type": "string",
                        "enum": ["gemeente", "provincie", "corop", "landelijk"],
                        "description": "Geografisch niveau filter",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dataset_details",
            "description": "Haal gedetailleerde kolominformatie op voor een specifieke dataset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "Dataset ID, bijv. '85423NED'",
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
]

CATALOG_SEARCH_RESULT = json.dumps(
    [
        {
            "bron": "MBO; deelnemers naar geslacht, regio en opleiding",
            "_cbs_id": "85423NED",
            "_dimensies": ["Geslacht", "RegioS", "Opleiding", "Perioden"],
            "_geo_niveau": ["gemeente", "provincie", "landelijk"],
            "_perioden_formaat": ["SJ"],
            "tags": ["mbo", "studenten", "deelnemers"],
        },
        {
            "bron": "MBO; first-year students by demographic characteristics",
            "_cbs_id": "83920NED",
            "_dimensies": ["Geslacht", "Leeftijd", "RegioS", "Perioden"],
            "_geo_niveau": ["provincie", "landelijk"],
            "_perioden_formaat": ["SJ"],
            "tags": ["mbo", "instroom", "eerstejaars"],
        },
    ],
    ensure_ascii=False,
)

TOOL_CALL_MSGS = [
    {
        "role": "user",
        "content": (
            "Hoeveel MBO-studenten zijn er in 2023 per gemeente? "
            "Gebruik search_catalog om de juiste dataset te vinden."
        ),
    }
]


def test_tool_calling(model: str):
    print(f"\n{'='*60}")
    print(f"  TEST 2: Tool calling — {model}")
    print(f"{'='*60}")

    result = chat(model, TOOL_CALL_MSGS, tools=MOCK_CATALOG_TOOLS)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return

    print(f"  Finish reason: {result['finish_reason']}")
    print(f"  Tokens: {result.get('usage', {})}")

    if result.get("tool_calls"):
        for tc in result["tool_calls"]:
            fn = tc.get("function", {})
            print(f"  Tool call: {fn.get('name')}({fn.get('arguments')})")
    else:
        print(f"  Geen tool calls — antwoord: {(result['content'] or '')[:300]}")

    # Simuleer tool-resultaat en vraag om vervolg
    if result.get("tool_calls"):
        tc = result["tool_calls"][0]
        fn = tc.get("function", {})

        follow_up = TOOL_CALL_MSGS + [
            {
                "role": "assistant",
                "content": result["content"] or "",
                "tool_calls": [
                    {
                        "id": tc.get("id", "call_1"),
                        "type": "function",
                        "function": {
                            "name": fn["name"],
                            "arguments": fn["arguments"],
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": tc.get("id", "call_1"),
                "content": CATALOG_SEARCH_RESULT,
            },
            {
                "role": "user",
                "content": "Kies de juiste dataset en roep dataset_details aan.",
            },
        ]

        result2 = chat(model, follow_up, tools=MOCK_CATALOG_TOOLS)
        if "error" in result2:
            print(f"  Vervolg ERROR: {result2['error']}")
        else:
            print(f"\n  Vervolg antwoord ({result2['elapsed_ms']}ms):")
            if result2.get("tool_calls"):
                for tc2 in result2["tool_calls"]:
                    fn2 = tc2.get("function", {})
                    print(f"  Tool call: {fn2.get('name')}({fn2.get('arguments')})")
            else:
                print(f"  {result2['content'][:300]}")


# ── Test 3: Vergelijking ──────────────────────────────────────────────

REASONING_QUESTION = (
    "Ik wil weten hoeveel HBO-studenten er in 2022 per provincie waren. "
    "Welke dataset moet ik gebruiken? Denk na over welke bron (CBS, DUO, RIO) "
    "het beste past en waarom."
)


def compare_models(models: list[str]):
    print(f"\n{'='*60}")
    print(f"  TEST 3: Vergelijking — reasoning vraag")
    print(f"{'='*60}")

    for model in models:
        print(f"\n--- {model} ---")
        messages = [
            {"role": "system", "content": "Reasoning: high"},
            {"role": "user", "content": REASONING_QUESTION},
        ]
        result = chat(model, messages, timeout=120)

        if "error" in result:
            print(f"  ERROR: {result['error']}")
            continue

        content = result["content"] or ""
        reasoning = result.get("reasoning_content", "")
        usage = result.get("usage", {})

        print(f"  Antwoord ({result['elapsed_ms']}ms):")
        print(f"  {content[:400]}")
        if reasoning:
            print(f"\n  Reasoning ({len(str(reasoning))} chars):")
            print(f"  {str(reasoning)[:400]}")
        print(f"  Tokens: {usage}")


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    models = list_models()
    available = [m["name"] for m in models if m.get("sequence_type") == "text"]

    print("=== Beschikbare tekstmodellen ===")
    for m in available:
        print(f"  - {m}")

    # Bepaal welke modellen testen
    test_models = []
    if GPT_OSS in available:
        test_models.append(GPT_OSS)
    else:
        print(f"\nWARN: {GPT_OSS} niet gevonden op Willma")

    for qwen in QWEN3_CANDIDATES:
        if qwen in available:
            test_models.append(qwen)
            break

    if not test_models:
        sys.exit("Geen testmodellen gevonden op Willma.")

    print(f"\nTe testen modellen: {test_models}")

    for model in test_models:
        test_reasoning_modes(model)
        test_tool_calling(model)

    if len(test_models) > 1:
        compare_models(test_models)

    print(f"\n{'='*60}")
    print("  TESTS VOLTOOID")
    print(f"{'='*60}")
