"""One tool loop for chat, report and dashboard (#192).

The model answers or calls tools; the tools run, their results go back into the
conversation, and the model continues until it answers. What differs per caller
— the events around an answer, what happens to a figure, which tools exist —
comes in through hooks, so a guard on the answer (``check``) is written once
instead of three times.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from core.config import MAX_TOKENS
from tools import LABELS, dispatch
from tools.snippet import generate as _generate_snippet

from .model_context import clamp_max_tokens
from .models import litellm_kwargs
from .ratelimit import acompletion_with_backoff
from .stream import Emit, accumulate_stream

logger = logging.getLogger(__name__)


# What a tool_end event carries of the output; the full result stays in the loop.
_EVENT_OUTPUT_CHARS = 2000


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str       # raw JSON as the model sent it
    args: dict | None    # parsed; None when not a JSON object

    @property
    def key(self) -> str:
        return f"{self.name}:{self.arguments}"


ToolHook = Callable[[ToolCall, str, Any], Awaitable[None]]
Check = Callable[[str, list[str]], list[str]]


@dataclass
class LoopResult:
    text: str = ""
    finish_reason: str | None = None
    tool_results: list[str] = field(default_factory=list)  # in full, for checks
    tool_calls: list[dict] = field(default_factory=list)   # {"name", "arguments"} as sent
    aborted: str | None = None           # "tools" or "stream": where a stop landed
    halted_on: ToolCall | None = None    # a halt_on tool ended the turn
    exhausted: bool = False              # max_iterations without an answer
    problems: list[str] = field(default_factory=list)  # check problems left after the correction
    partial_error: str | None = None     # model call failed; kept what was collected


def _parse_arguments(arguments: str) -> dict | None:
    """Tool-call JSON arguments; None when malformed or not an object.

    Models sometimes emit control characters or trailing garbage. The model gets
    that back as feedback, so a later, well-formed step can still succeed.
    """
    try:
        parsed = json.loads(arguments)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _truncate(result: str, limit: int) -> str:
    if len(result) <= limit:
        return result
    return result[:limit] + f"\n... (afgekapt, {len(result)} chars totaal. Gebruik filters of selecteer kolommen.)"


async def _execute_tool(call: ToolCall, emit: Emit) -> tuple[str, Any]:
    label = LABELS.get(call.name, call.name)
    logger.debug("TOOL CALL  %-30s args=%s", call.name, call.arguments)
    await emit({"type": "tool_start", "name": call.name, "label": label, "input": call.args})
    result, figure = await asyncio.to_thread(dispatch, call.name, call.args)
    result = str(result)

    snippet = _generate_snippet(call.name, call.args)
    if snippet:
        logger.info("REPRODUCEER %-28s\n%s", call.name, snippet)
    end_event = {"type": "tool_end", "name": call.name, "output": result[:_EVENT_OUTPUT_CHARS]}
    if snippet:
        end_event["snippet"] = snippet
    await emit(end_event)
    logger.debug("TOOL RESULT %-29s → %s", call.name, result[:_EVENT_OUTPUT_CHARS])
    return result, figure


@dataclass
class _Loop:
    """One run of the loop; state shared by the first round and the correction."""

    messages: list[dict]
    model: str
    tools: list[dict]
    emit: Emit
    stop_event: asyncio.Event | None
    max_iterations: int
    max_result_chars: int
    system: list[dict]
    stream_text: bool
    on_llm_start: Callable[[], Awaitable[None]] | None
    on_tool_result: ToolHook | None
    tool_limits: dict[str, int]
    halt_on: frozenset[str]
    result: LoopResult = field(default_factory=LoopResult)
    cache: dict[str, tuple[str, Any]] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    def _stopped(self) -> bool:
        return bool(self.stop_event and self.stop_event.is_set())

    async def rounds(self) -> None:
        """Call the model until it answers, a tool halts the turn, or a stop lands."""
        result = self.result
        for iteration in range(self.max_iterations):
            if self._stopped():
                result.aborted = "tools"
                return
            logger.debug("ITERATIE   %d", iteration + 1)

            stream = await acompletion_with_backoff(
                self.emit,
                model=self.model,
                max_tokens=clamp_max_tokens(self.model, MAX_TOKENS),
                messages=[*self.system, *self.messages],
                tools=self.tools,
                stream=True,
                **litellm_kwargs(self.model),
            )
            if self.on_llm_start:
                await self.on_llm_start()
            sr = await accumulate_stream(
                stream, stop_event=self.stop_event, emit=self.emit if self.stream_text else None,
            )
            result.text, result.finish_reason = sr.text, sr.finish_reason
            if self._stopped():
                result.aborted = "stream"
                return
            if sr.text:
                logger.debug("LLM TEKST  iter=%d  %r", iteration + 1, sr.text[:500])
            if not sr.tool_calls:
                return

            calls = [ToolCall(tc["id"], tc["name"], tc["arguments"], _parse_arguments(tc["arguments"]))
                     for tc in sr.tool_calls]
            logger.debug("LLM KIEST  %d tool(s): %s", len(calls), ", ".join(c.name for c in calls))
            self.messages.append({
                "role": "assistant",
                "content": sr.text or "",
                "tool_calls": [
                    {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                    for c in calls
                ],
            })
            result.tool_calls.extend({"name": c.name, "arguments": c.arguments} for c in calls)
            await self._run_tools(calls)

            halt = next((c for c in calls if c.name in self.halt_on), None)
            if halt:
                result.halted_on = halt
                return
        result.exhausted = True

    async def _run_tools(self, calls: list[ToolCall]) -> None:
        blocked: dict[str, str] = {}
        for c in calls:
            self.counts[c.name] = self.counts.get(c.name, 0) + 1
            limit = self.tool_limits.get(c.name)
            if limit and self.counts[c.name] > limit:
                blocked[c.id] = (
                    f"LIMIET: {c.name} is al {limit}x aangeroepen. Werk met de resultaten die je hebt "
                    "of geef aan dat de data niet beschikbaar is."
                )
                logger.warning("TOOL LIMIET  %s aangeroepen %d/%d keer", c.name, self.counts[c.name], limit)

        runnable = {
            c.key: c for c in calls
            if c.id not in blocked and c.name not in self.halt_on and c.args is not None and c.key not in self.cache
        }
        outcomes = await asyncio.gather(*[_execute_tool(c, self.emit) for c in runnable.values()])
        self.cache.update(zip(runnable, outcomes, strict=True))

        for c in calls:
            if c.id in blocked:
                content = blocked[c.id]
            elif c.name in self.halt_on:
                content = "OK"
            elif c.args is None:
                content = (f"Fout: de argumenten voor `{c.name}` waren geen geldige JSON."
                           " Lever opnieuw aan met geldige JSON-argumenten.")
            else:
                content, figure = self.cache[c.key]
                self.result.tool_results.append(content)
                if self.on_tool_result:
                    await self.on_tool_result(c, content, figure)
            self.messages.append({"role": "tool", "tool_call_id": c.id,
                                  "content": _truncate(content, self.max_result_chars)})


async def tool_loop(
    messages: list[dict],
    *,
    model: str,
    tools: list[dict],
    emit: Emit,
    max_iterations: int,
    max_result_chars: int,
    stop_event: asyncio.Event | None = None,
    system: list[dict] | None = None,
    stream_text: bool = False,
    on_llm_start: Callable[[], Awaitable[None]] | None = None,
    on_tool_result: ToolHook | None = None,
    tool_limits: dict[str, int] | None = None,
    halt_on: frozenset[str] = frozenset(),
    check: Check | None = None,
    correction: Callable[[list[str]], str] | None = None,
    on_correction: Callable[[list[str]], Awaitable[None]] | None = None,
    keep_partial: Callable[[], bool] | None = None,
) -> LoopResult:
    """Let the model call tools until it answers.

    ``messages`` is extended in place with the assistant turns and tool results;
    ``system`` is sent with every call but not stored. ``check(text, tool_results)``
    returns problems with a finished answer: the model then gets one correction
    round with ``correction(problems)``, announced to the caller through
    ``on_correction(problems)`` before it runs; problems left after that are returned in
    ``LoopResult.problems`` for the caller to act on. When the model call fails
    and ``keep_partial()`` says what was collected is usable, the error is
    returned in ``partial_error`` instead of raised.
    """
    run = _Loop(
        messages=messages, model=model, tools=tools, emit=emit, stop_event=stop_event,
        max_iterations=max_iterations, max_result_chars=max_result_chars, system=system or [],
        stream_text=stream_text, on_llm_start=on_llm_start, on_tool_result=on_tool_result,
        tool_limits=tool_limits or {}, halt_on=halt_on,
    )
    result = run.result
    try:
        await run.rounds()
        if check and _answered(result):
            problems = check(result.text, result.tool_results)
            if problems:
                logger.warning("CONTROLE MISLUKT, herkansing: %s", problems)
                if on_correction:
                    await on_correction(problems)
                messages += [
                    {"role": "assistant", "content": result.text},
                    {"role": "user", "content": correction(problems) if correction else "\n".join(problems)},
                ]
                await run.rounds()
                result.problems = check(result.text, result.tool_results) if _answered(result) else []
    except Exception as exc:
        if not (keep_partial and keep_partial()):
            raise
        result.partial_error = str(exc)
    return result


def _answered(result: LoopResult) -> bool:
    return not (result.aborted or result.halted_on or result.exhausted)
