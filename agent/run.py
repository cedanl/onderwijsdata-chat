import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import plotly.io as pio

from core.config import MAX_TOOL_ITERATIONS, MODEL
from tools import LABELS, SCHEMAS
from tools.schemas import TOOL_CLARIFY_SCOPE

from .history import trim
from .loop import ToolCall, tool_loop
from .models import build_system
from .session_data import record_data_key

logger = logging.getLogger(__name__)

Emit = Callable[[dict[str, Any]], Awaitable[None]]
_TOOL_LIMITS: dict[str, int] = {"search_catalog": 5}
_MAX_TOOL_RESULT_CHARS = 12000

# LiteLLM bug: transform_request for ollama_chat converts tool_calls in history
# messages but never writes them to the output Ollama message, causing orphaned
# tool-result messages on the second LLM call. Patch it here.
if MODEL.startswith(("ollama_chat/", "ollama/")):
    from litellm.llms.ollama.chat.transformation import OllamaChatConfig

    _orig_transform = OllamaChatConfig.transform_request

    def _patched_transform(self, model, messages, optional_params, litellm_params, headers):
        result = _orig_transform(self, model, messages, optional_params, litellm_params, headers)
        for orig, out in zip(messages, result.get("messages", []), strict=False):
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

    OllamaChatConfig.transform_request = _patched_transform


async def _handle_figure(name: str, figure, session: dict, emit: Emit) -> None:
    """Store *figure* in the session and emit a figure event."""
    if figure is None:
        return
    for key in ("figures", "turn_figures"):
        figs = session.get(key, [])
        figs.append(figure)
        session[key] = figs
    await emit({
        "type": "figure",
        "label": LABELS.get(name, name),
        "figure_json": pio.to_json(figure),
    })


async def _handle_clarify_scope(
    call: ToolCall,
    text_content: str,
    turn_history: list[dict],
    messages: list[dict],
    session: dict,
    emit: Emit,
) -> str:
    """End the turn with a clarification card; returns the text for ``run()``."""
    args = call.args or {}

    # Persist the clarification exchange back to messages so the next
    # turn has the tool_calls context (prevents re-asking same question).
    messages.extend(turn_history)
    session["_clarified"] = True

    # Cancel the open message_start before sending the clarification card.
    # If the LLM produced text before the tool call, close it properly first.
    if text_content:
        await emit({"type": "message_end", "content": text_content, "actions": []})
    else:
        await emit({"type": "message_cancel"})

    await emit({
        "type": "clarification",
        "vraag": args.get("vraag", ""),
        "opties": args.get("opties") or [],
    })
    return text_content


async def run(
    messages: list[dict],
    session: dict,
    emit: Emit,
    stop_event: asyncio.Event | None = None,
    model: str | None = None,
) -> str:
    settings: dict = session.get("chat_settings") or {}
    chosen_model = model or MODEL

    _raw = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    last_user_msg = (
        " ".join(b.get("text", "") for b in _raw if isinstance(b, dict))
        if isinstance(_raw, list) else str(_raw)
    )
    logger.info("RUN START  model=%s  vraag=%r", chosen_model, last_user_msg[:200])

    history, was_trimmed = trim(list(messages))
    initial_history_len = len(history)
    if was_trimmed:
        await emit({
            "type": "toast",
            "message": "Oudere berichten vallen buiten de context van het model.",
            "level": "warning",
        })

    async def keep(call: ToolCall, result: str, figure) -> None:
        record_data_key(session, result, {"name": call.name, "arguments": call.args})
        await _handle_figure(call.name, figure, session, emit)

    async def _slow_warning():
        await asyncio.sleep(45)
        await emit({
            "type": "toast",
            "message": "Het model is nog bezig — bij complexe vragen kan dit even duren.",
            "level": "info",
        })

    slow_task = asyncio.create_task(_slow_warning())
    try:
        result = await tool_loop(
            history,
            model=chosen_model,
            tools=SCHEMAS,
            emit=emit,
            stop_event=stop_event,
            system=build_system(settings),
            stream_text=True,
            on_llm_start=lambda: emit({"type": "message_start"}),
            on_tool_result=keep,
            tool_limits=_TOOL_LIMITS,
            halt_on=frozenset({TOOL_CLARIFY_SCOPE}),
            max_iterations=MAX_TOOL_ITERATIONS,
            max_result_chars=_MAX_TOOL_RESULT_CHARS,
        )
    finally:
        slow_task.cancel()

    if result.aborted == "tools":
        # Stopped while tools ran: close the open message as aborted. No
        # content key, so the client keeps the text it already has.
        await emit({"type": "message_end", "aborted": True})
        return ""
    if result.aborted == "stream":
        await emit({"type": "message_end", "content": result.text, "aborted": True})
        return result.text
    if result.halted_on:
        session["_last_turn_tool_calls"] = result.tool_calls
        return await _handle_clarify_scope(
            result.halted_on, result.text, history[initial_history_len:], messages, session, emit,
        )
    if result.exhausted:
        await emit({"type": "error", "message": "Het maximale aantal stappen is bereikt. Probeer een specifiekere vraag."})
        return "Het maximale aantal stappen is bereikt."

    text_content = result.text
    logger.info("FINALE ANTWOORD  %r", text_content[:500])
    session["_last_turn_tool_calls"] = result.tool_calls
    truncated = result.finish_reason == "length"
    if truncated:
        logger.warning("ANTWOORD AFGEKAPT op outputlimiet  model=%s", chosen_model)
    if not text_content.strip():
        logger.warning("LEEG ANTWOORD  model=%s", chosen_model)
    await emit({
        "type": "message_end",
        "content": text_content,
        "actions": [],
        **({"truncated": True} if truncated else {}),
    })
    return text_content
