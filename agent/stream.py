"""Shared stream-accumulation helper for LiteLLM async streams."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .tekens import normaliseer

# The callback every agent loop uses to send events to the client.
Emit = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class Tokens:
    """Wat een modelaanroep aan tokens kostte, zoals de provider het meldt (#678)."""

    invoer: int = 0
    uitvoer: int = 0
    # Anthropic rekent gecachete invoer (de systeemprompt) anders dan nieuwe; apart, voor de kosten.
    cache_gelezen: int = 0
    cache_geschreven: int = 0

    def __add__(self, ander: Tokens) -> Tokens:
        return Tokens(
            self.invoer + ander.invoer,
            self.uitvoer + ander.uitvoer,
            self.cache_gelezen + ander.cache_gelezen,
            self.cache_geschreven + ander.cache_geschreven,
        )


def _veld(bron: Any, naam: str) -> Any:
    """Een veld uit een object of een dict; None als het er niet is."""
    if isinstance(bron, dict):
        return bron.get(naam)
    return getattr(bron, naam, None)


def _cache(usage: Any, bovenin: str, *in_details: str) -> int:
    """Het eerste gemelde cachegetal: het veld bovenin, anders de details, anders 0.

    Beide beschrijven dezelfde tokens, dus nooit optellen; een `is None`-keten zodat een echte 0 bovenin wint.
    """
    details = _veld(usage, "prompt_tokens_details")
    for waarde in (_veld(usage, bovenin), *(_veld(details, naam) for naam in in_details)):
        if waarde is not None:
            return waarde
    return 0


def _tokens(chunk: Any) -> Tokens | None:
    """Het gebruik op een chunk, als die het draagt.

    LiteLLM zet het in `usage` (met `stream_options.include_usage`) of in `_hidden_params["usage"]` van de
    laatste chunk. De cache staat in `cache_read_input_tokens`/`cache_creation_input_tokens`; bij streaming
    zijn die leeg en staat hij alleen in `prompt_tokens_details` (`cached_tokens`, `cache_write_tokens` of
    `cache_creation_tokens`, #1027). `invoer` is het totaal, de cache inbegrepen.
    """
    usage = getattr(chunk, "usage", None) or (getattr(chunk, "_hidden_params", None) or {}).get("usage")
    if usage is None:
        return None
    return Tokens(
        invoer=_veld(usage, "prompt_tokens") or 0,
        uitvoer=_veld(usage, "completion_tokens") or 0,
        cache_gelezen=_cache(usage, "cache_read_input_tokens", "cached_tokens"),
        cache_geschreven=_cache(usage, "cache_creation_input_tokens", "cache_write_tokens", "cache_creation_tokens"),
    )


@dataclass
class StreamResult:
    text: str
    tool_calls: list[dict]
    # "length" means the output limit cut the answer off.
    finish_reason: str | None = None
    # Wat de provider terugmeldt als model (vaak een gedateerde versie), voor het manifest (#345).
    model_versie: str | None = None
    tokens: Tokens = field(default_factory=Tokens)
    # time.monotonic() of the first chunk, None when none came: how long a model takes to start (#800).
    eerste_chunk: float | None = None


async def accumulate_stream(
    stream,
    stop_event=None,
    emit: Emit | None = None,
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
    finish_reason: str | None = None
    model_versie: str | None = None
    tokens = Tokens()
    eerste_chunk: float | None = None

    async for chunk in stream:
        if eerste_chunk is None:
            eerste_chunk = time.monotonic()
        if stop_event and stop_event.is_set():
            break

        model_versie = getattr(chunk, "model", None) or model_versie
        tokens = _tokens(chunk) or tokens
        if not chunk.choices:  # alleen gebruik, na de laatste tekst
            continue
        choice = chunk.choices[0]
        finish_reason = getattr(choice, "finish_reason", None) or finish_reason
        delta = choice.delta

        if delta.content:
            # Per teken, dus veilig per fragment: deltas en eindtekst zijn dezelfde tekst (#326).
            content = normaliseer(delta.content)
            text_parts.append(content)
            if emit is not None:
                await emit({"type": "text_delta", "content": content})

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
        finish_reason=finish_reason,
        model_versie=model_versie,
        tokens=tokens,
        eerste_chunk=eerste_chunk,
    )
