import anthropic
import chainlit as cl

from config import MAX_TOKENS, MAX_TOOL_ITERATIONS, MODEL
from prompt import get_system_prompt
from tools import LABELS, SCHEMAS, dispatch


def _build_system() -> list[dict]:
    return [{"type": "text", "text": get_system_prompt(), "cache_control": {"type": "ephemeral"}}]


async def run(messages: list[dict]) -> str:
    client = anthropic.Anthropic()
    history = list(messages)

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_build_system(),
            tools=SCHEMAS,
            messages=history,
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            return next((b.text for b in response.content if b.type == "text"), "")

        history.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in tool_uses:
            label = LABELS.get(block.name, block.name)
            async with cl.Step(name=label, type="tool") as step:
                step.input = block.input
                result = dispatch(block.name, block.input)
                step.output = result

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        history.append({"role": "user", "content": tool_results})

    return "Het maximale aantal stappen is bereikt. Probeer een specifiekere vraag."
