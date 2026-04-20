import json

import litellm
import chainlit as cl

from config import MAX_TOKENS, MAX_TOOL_ITERATIONS, MODEL
from prompt import SYSTEM_PROMPT
from tools import LABELS, SCHEMAS, dispatch

_SYSTEM = [{"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]}]


async def run(messages: list[dict]) -> str:
    history = list(messages)

    for _ in range(MAX_TOOL_ITERATIONS):
        response = await litellm.acompletion(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=_SYSTEM + history,
            tools=SCHEMAS,
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            return message.content or ""

        history.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ],
        })

        for tc in tool_calls:
            args = json.loads(tc.function.arguments)
            label = LABELS.get(tc.function.name, tc.function.name)

            async with cl.Step(name=label, type="tool") as step:
                step.input = args
                result, figure = dispatch(tc.function.name, args)
                step.output = result

            if figure is not None:
                figures = cl.user_session.get("figures", [])
                figures.append(figure)
                cl.user_session.set("figures", figures)
                await cl.Message(
                    content="",
                    elements=[cl.Plotly(name=label, figure=figure, display="inline")],
                ).send()

            history.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return "Het maximale aantal stappen is bereikt. Probeer een specifiekere vraag."
