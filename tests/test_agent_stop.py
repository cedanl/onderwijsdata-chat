"""Stopping between tool iterations must end the answer, not report 'max steps'."""
import asyncio
import importlib

from agent.stream import StreamResult

# agent/__init__ re-exports run(), which shadows the module attribute
run_module = importlib.import_module("agent.run")


def test_stop_during_tool_step_ends_message_as_aborted(monkeypatch):
    stop_event = asyncio.Event()

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return StreamResult(text="", tool_calls=[{"id": "t1", "name": "search_catalog", "arguments": "{}"}])

    async def fake_call_tool(tc, emit):
        stop_event.set()  # user presses Stop while the tool runs
        return "resultaat", None

    monkeypatch.setattr(run_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(run_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(run_module, "_call_tool", fake_call_tool)

    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    asyncio.run(run_module.run(
        [{"role": "user", "content": "vraag"}], {}, emit, stop_event, model="openai/gpt-4o",
    ))

    types = [e["type"] for e in events]
    assert "error" not in types, events
    assert events[-1]["type"] == "message_end"
    assert events[-1]["aborted"] is True
