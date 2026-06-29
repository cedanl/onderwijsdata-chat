import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import litellm

from config import MAX_TOKENS, MAX_TOOL_ITERATIONS, MODEL
from tools import LABELS, SCHEMAS, dispatch
from .history import trim
from .models import build_system, litellm_kwargs

Emit = Callable[[dict[str, Any]], Awaitable[None]]

# LiteLLM bug: transform_request for ollama_chat converts tool_calls in history
# messages but never writes them to the output Ollama message, causing orphaned
# tool-result messages on the second LLM call. Patch it here.
if MODEL.startswith("ollama_chat/") or MODEL.startswith("ollama/"):
    from litellm.llms.ollama.chat.transformation import OllamaChatConfig

    _orig_transform = OllamaChatConfig.transform_request

    def _patched_transform(self, model, messages, optional_params, litellm_params, headers):
        result = _orig_transform(self, model, messages, optional_params, litellm_params, headers)
        for orig, out in zip(messages, result.get("messages", [])):
            if not isinstance(orig, dict):
                continue
            raw_tools = orig.get("tool_calls")
            if raw_tools and "tool_calls" not in out:
                converted = []
                for tc in raw_tools:
                    args = tc.get("function", {}).get("arguments", "{}")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    converted.append({"function": {"name": tc["function"]["name"], "arguments": args}})
                out["tool_calls"] = converted
        return result

    OllamaChatConfig.transform_request = _patched_transform  # ty: ignore[invalid-assignment]


async def _call_tool(tc: dict, emit: Emit) -> tuple[str, object]:
    if tc["name"] == "clarify_scope":
        return "OK", None
    args = json.loads(tc["arguments"])
    label = LABELS.get(tc["name"], tc["name"])
    await emit({"type": "tool_start", "name": tc["name"], "label": label, "input": args})
    result, figure = await asyncio.to_thread(dispatch, tc["name"], args)
    await emit({"type": "tool_end", "name": tc["name"], "output": str(result)[:500]})
    return result, figure


def _call_key(tc: dict) -> str:
    return f"{tc['name']}:{tc['arguments']}"


_RATE_LIMIT_MAX_RETRIES = 4
_RATE_LIMIT_BASE_DELAY = 2.0


async def _acompletion_with_backoff(emit: Emit, **kwargs):
    for attempt in range(_RATE_LIMIT_MAX_RETRIES):
        try:
            return await litellm.acompletion(**kwargs)
        except litellm.RateLimitError:
            if attempt == _RATE_LIMIT_MAX_RETRIES - 1:
                raise
            delay = _RATE_LIMIT_BASE_DELAY * (2 ** attempt)
            await emit({
                "type": "toast",
                "message": f"API rate limit bereikt, nieuwe poging over {delay:.0f}s…",
                "level": "warning",
            })
            await asyncio.sleep(delay)


async def run(
    messages: list[dict],
    session: dict,
    emit: Emit,
    stop_event: asyncio.Event | None = None,
    model: str | None = None,
) -> str:
    settings: dict = session.get("chat_settings") or {}
    chosen_model = model or MODEL
    system = build_system(settings)
    extra_kwargs = litellm_kwargs(chosen_model)

    history, was_trimmed = trim(list(messages))
    if was_trimmed:
        await emit({
            "type": "toast",
            "message": "Oudere berichten vallen buiten de context van het model.",
            "level": "warning",
        })

    call_cache: dict[str, tuple[str, object]] = {}
    turn_tool_calls: list[dict] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        if stop_event and stop_event.is_set():
            break

        stream = await _acompletion_with_backoff(
            emit,
            model=chosen_model,
            max_tokens=MAX_TOKENS,
            messages=system + history,
            tools=SCHEMAS,
            stream=True,
            **extra_kwargs,
        )

        await emit({"type": "message_start"})

        text_parts: list[str] = []
        raw_tcs: dict[int, dict] = {}

        async for chunk in stream:
            if stop_event and stop_event.is_set():
                break

            delta = chunk.choices[0].delta

            if delta.content:
                text_parts.append(delta.content)
                await emit({"type": "text_delta", "content": delta.content})

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in raw_tcs:
                        raw_tcs[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc.id:
                        raw_tcs[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            raw_tcs[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            raw_tcs[idx]["arguments"] += tc.function.arguments

        text_content = "".join(text_parts)
        tool_calls = [raw_tcs[i] for i in sorted(raw_tcs)]

        if stop_event and stop_event.is_set():
            await emit({"type": "message_end", "content": text_content, "aborted": True})
            return text_content

        if not tool_calls:
            session["_last_turn_tool_calls"] = turn_tool_calls
            await emit({
                "type": "message_end",
                "content": text_content,
                "actions": ["download_rapport_samenvatting", "download_rapport"],
            })
            return text_content

        history.append({
            "role": "assistant",
            "content": text_content or "",
            "tool_calls": [
                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in tool_calls
            ],
        })

        turn_tool_calls.extend({"name": tc["name"], "arguments": tc["arguments"]} for tc in tool_calls)

        new_calls = [(i, tc) for i, tc in enumerate(tool_calls) if _call_key(tc) not in call_cache]
        new_results = await asyncio.gather(*[_call_tool(tc, emit) for _, tc in new_calls])
        for (i, tc), res in zip(new_calls, new_results):
            call_cache[_call_key(tc)] = res

        results = [call_cache[_call_key(tc)] for tc in tool_calls]

        for tc, (result, figure) in zip(tool_calls, results):
            if figure is not None:
                import plotly.io as pio
                figures = session.get("figures", [])
                figures.append(figure)
                session["figures"] = figures
                turn_figs = session.get("turn_figures", [])
                turn_figs.append(figure)
                session["turn_figures"] = turn_figs
                fig_meta = getattr(getattr(figure, "layout", None), "meta", None) or {}
                if not fig_meta.get("chat_hidden"):
                    label = LABELS.get(tc["name"], tc["name"])
                    await emit({
                        "type": "figure",
                        "label": label,
                        "figure_json": pio.to_json(figure),
                    })
            history.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        if any(tc["name"] == "clarify_scope" for tc in tool_calls):
            session["_last_turn_tool_calls"] = turn_tool_calls
            clarify_tc = next(tc for tc in tool_calls if tc["name"] == "clarify_scope")
            args = json.loads(clarify_tc["arguments"])
            opties = args.get("opties") or []

            # Cancel the open message_start before sending the clarification card.
            # If the LLM produced text before the tool call, close it properly first.
            if text_content:
                await emit({"type": "message_end", "content": text_content, "actions": []})
            else:
                await emit({"type": "message_cancel"})

            await emit({
                "type": "clarification",
                "vraag": args.get("vraag", ""),
                "opties": opties,
            })
            return text_content

    await emit({"type": "error", "message": "Het maximale aantal stappen is bereikt. Probeer een specifiekere vraag."})
    return "Het maximale aantal stappen is bereikt."
