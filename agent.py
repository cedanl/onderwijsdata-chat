import asyncio
import json

import litellm
import chainlit as cl

from config import MAX_TOKENS, MAX_TOOL_ITERATIONS, MODEL, WILLMA_API_KEY, WILLMA_BASE_URL
from prompt import SYSTEM_PROMPT
from tools import LABELS, SCHEMAS, dispatch

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

    OllamaChatConfig.transform_request = _patched_transform

_SYSTEM = [{"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]}]
_MAX_HISTORY = 40


def _trim(history: list[dict]) -> list[dict]:
    if len(history) <= _MAX_HISTORY:
        return history
    first_user = next((m for m in history if m["role"] == "user"), None)
    tail = history[-(_MAX_HISTORY - 1):]
    if first_user and first_user not in tail:
        return [first_user] + tail
    return tail


async def _call_tool(tc: dict) -> tuple[str, object]:
    args = json.loads(tc["arguments"])
    label = LABELS.get(tc["name"], tc["name"])
    async with cl.Step(name=label, type="tool") as step:
        step.input = args
        result, figure = await asyncio.to_thread(dispatch, tc["name"], args)
        step.output = result
    return result, figure


def _call_key(tc: dict) -> str:
    return f"{tc['name']}:{tc['arguments']}"


_WILLMA_KWARGS: dict = (
    {
        "api_base": WILLMA_BASE_URL,
        "api_key": WILLMA_API_KEY,
        "extra_headers": {"X-API-KEY": WILLMA_API_KEY},
    }
    if WILLMA_API_KEY
    else {}
)


async def run(messages: list[dict]) -> str:
    history = _trim(list(messages))
    call_cache: dict[str, tuple[str, object]] = {}

    for _ in range(MAX_TOOL_ITERATIONS):
        stream = await litellm.acompletion(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=_SYSTEM + history,
            tools=SCHEMAS,
            stream=True,
            **_WILLMA_KWARGS,
        )

        msg = cl.Message(content="")
        await msg.send()

        text_parts: list[str] = []
        raw_tcs: dict[int, dict] = {}

        async for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                text_parts.append(delta.content)
                await msg.stream_token(delta.content)

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

        if not tool_calls:
            figures = cl.user_session.get("figures", [])
            if figures:
                msg.actions = [cl.Action(name="download_rapport", label="📥 Download rapport", payload={"action": "download"})]
            await msg.update()
            return text_content

        if not text_content:
            await msg.remove()
        else:
            await msg.update()

        history.append({
            "role": "assistant",
            "content": text_content or "",
            "tool_calls": [
                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in tool_calls
            ],
        })

        # Deduplicate: run only calls not seen earlier this conversation
        new_calls = [(i, tc) for i, tc in enumerate(tool_calls) if _call_key(tc) not in call_cache]
        new_results = await asyncio.gather(*[_call_tool(tc) for _, tc in new_calls])
        for (i, tc), res in zip(new_calls, new_results):
            call_cache[_call_key(tc)] = res

        results = [call_cache[_call_key(tc)] for tc in tool_calls]

        for tc, (result, figure) in zip(tool_calls, results):
            if figure is not None:
                figures = cl.user_session.get("figures", [])
                figures.append(figure)
                cl.user_session.set("figures", figures)
                turn_figs = cl.user_session.get("turn_figures", [])
                turn_figs.append(figure)
                cl.user_session.set("turn_figures", turn_figs)
                label = LABELS.get(tc["name"], tc["name"])
                await cl.Message(
                    content="",
                    elements=[cl.Plotly(name=label, figure=figure, display="inline")],
                ).send()
            history.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    await cl.Message(content="Het maximale aantal stappen is bereikt. Probeer een specifiekere vraag.").send()
    return "Het maximale aantal stappen is bereikt."
