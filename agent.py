import asyncio
import json

import litellm
import chainlit as cl

from config import MAX_HISTORY, MAX_TOKENS, MAX_TOOL_ITERATIONS, MODEL, WILLMA_API_KEY, WILLMA_BASE_URL
from prompt import SYSTEM_PROMPT_SNEL, SYSTEM_PROMPT_VERDIEP
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

_MAX_HISTORY = MAX_HISTORY

_RAPPORT_ACTIONS = [
    cl.Action(name="download_rapport", label="📥 HTML", payload={"action": "download"}),
    cl.Action(name="download_rapport_pdf", label="📄 PDF", payload={"action": "download_pdf"}),
]

_WILLMA_KWARGS: dict = (
    {
        "api_base": WILLMA_BASE_URL,
        "api_key": WILLMA_API_KEY,
        "extra_headers": {"X-API-KEY": WILLMA_API_KEY},
    }
    if WILLMA_API_KEY
    else {}
)


def _build_system(modus: str) -> list[dict]:
    text = SYSTEM_PROMPT_VERDIEP if modus == "verdiep" else SYSTEM_PROMPT_SNEL
    return [{"role": "system", "content": [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]}]


def _litellm_kwargs(model: str) -> dict:
    """Return extra kwargs for litellm based on the chosen model."""
    if WILLMA_API_KEY and not model.startswith("anthropic/") and not model.startswith("ollama"):
        return _WILLMA_KWARGS
    return {}


def _trim(history: list[dict]) -> tuple[list[dict], bool]:
    if len(history) <= _MAX_HISTORY:
        return history, False
    first_user = next((m for m in history if m["role"] == "user"), None)
    tail = history[-(_MAX_HISTORY - 1):]
    if first_user and first_user not in tail:
        return [first_user] + tail, True
    return tail, True


async def _call_tool(tc: dict) -> tuple[str, object]:
    if tc["name"] == "suggest_followups":
        args = json.loads(tc["arguments"])
        cl.user_session.set("pending_suggestions", args.get("suggestions", []))
        return "OK", None
    args = json.loads(tc["arguments"])
    label = LABELS.get(tc["name"], tc["name"])
    async with cl.Step(name=label, type="tool") as step:
        step.input = args
        result, figure = await asyncio.to_thread(dispatch, tc["name"], args)
        step.output = result
    return result, figure


def _call_key(tc: dict) -> str:
    return f"{tc['name']}:{tc['arguments']}"


async def generate_title(question: str, answer: str, model: str | None = None) -> str:
    chosen_model = model or MODEL
    response = await litellm.acompletion(
        model=chosen_model,
        max_tokens=20,
        messages=[{
            "role": "user",
            "content": (
                "Geef een titel van maximaal 6 woorden voor dit gesprek. "
                "Alleen de titel zelf, geen uitleg of aanhalingstekens.\n\n"
                f"Vraag: {question[:400]}\nAntwoord: {answer[:400]}"
            ),
        }],
        **_litellm_kwargs(chosen_model),
    )
    return response.choices[0].message.content.strip().strip('"\'')


async def run(
    messages: list[dict],
    stop_event: asyncio.Event | None = None,
    model: str | None = None,
    modus: str = "snel",
) -> str:
    chosen_model = model or MODEL
    system = _build_system(modus)
    extra_kwargs = _litellm_kwargs(chosen_model)

    history, was_trimmed = _trim(list(messages))
    if was_trimmed:
        await cl.context.emitter.send_toast(
            "Oudere berichten vallen buiten de context van het model.",
            type="warning",
        )

    call_cache: dict[str, tuple[str, object]] = {}

    for _ in range(MAX_TOOL_ITERATIONS):
        if stop_event and stop_event.is_set():
            break

        stream = await litellm.acompletion(
            model=chosen_model,
            max_tokens=MAX_TOKENS,
            messages=system + history,
            tools=SCHEMAS,
            stream=True,
            **extra_kwargs,
        )

        msg = cl.Message(content="")
        await msg.send()

        text_parts: list[str] = []
        raw_tcs: dict[int, dict] = {}

        async for chunk in stream:
            if stop_event and stop_event.is_set():
                break

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

        if stop_event and stop_event.is_set():
            if text_content:
                await msg.update()
            else:
                await msg.remove()
            return text_content

        if not tool_calls:
            msg.actions = _RAPPORT_ACTIONS
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

        # Terminal: only suggest_followups was called — show labelled suggestion block and return
        if all(tc["name"] == "suggest_followups" for tc in tool_calls):
            pending = cl.user_session.get("pending_suggestions", [])
            cl.user_session.set("pending_suggestions", [])
            if text_content:
                msg.actions = _RAPPORT_ACTIONS
                await msg.update()
            if pending:
                followup_actions = [
                    cl.Action(name="followup", label=s, payload={"question": s})
                    for s in pending
                ]
                await cl.Message(content="**Vraag suggesties**", actions=followup_actions).send()
            return text_content

    await cl.Message(content="Het maximale aantal stappen is bereikt. Probeer een specifiekere vraag.").send()
    return "Het maximale aantal stappen is bereikt."
