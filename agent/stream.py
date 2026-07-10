"""Shared stream-accumulation helper for LiteLLM async streams."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class StreamResult:
    text: str
    tool_calls: list[dict]


async def accumulate_stream(
    stream,
    stop_event=None,
    emit: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> StreamResult:
    """Collect text and tool-call deltas from a LiteLLM stream.

    Parameters
    ----------
    stream:
        An async iterable of LiteLLM streaming chunks.
    stop_event:
        Optional ``asyncio.Event``; when set the loop breaks early.
    emit:
        Optional callback.  When provided **and** the chunk contains
        ``delta.content``, the helper awaits
        ``emit({"type": "text_delta", "content": ...})`` for every
        content fragment so callers can forward tokens in real time.
    """
    text_parts: list[str] = []
    raw_tcs: dict[int, dict] = {}

    async for chunk in stream:
        if stop_event and stop_event.is_set():
            break

        delta = chunk.choices[0].delta

        if delta.content:
            text_parts.append(delta.content)
            if emit is not None:
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

    return StreamResult(
        text="".join(text_parts),
        tool_calls=[raw_tcs[i] for i in sorted(raw_tcs)],
    )
