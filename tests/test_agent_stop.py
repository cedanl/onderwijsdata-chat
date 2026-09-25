"""Stopping between tool iterations must end the answer, not report 'max steps'."""
import asyncio
import importlib

from agent.stream import StreamResult

# agent/__init__ re-exports run(), which shadows the module attribute
run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")


def test_stop_during_tool_step_ends_message_as_aborted(monkeypatch):
    stop_event = asyncio.Event()

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return StreamResult(text="", tool_calls=[{"id": "t1", "name": "search_catalog", "arguments": "{}"}])

    async def fake_execute_tool(call, emit):
        stop_event.set()  # user presses Stop while the tool runs
        return "resultaat", None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)

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
