"""An answer cut off at the output limit must not look like a finished one."""
import asyncio
import importlib
from types import SimpleNamespace

from agent.stream import StreamResult, accumulate_stream

run_module = importlib.import_module("agent.run")


def _chunk(content=None, finish_reason=None):
    delta = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish_reason)])


async def _stream(*chunks):
    for c in chunks:
        yield c


def test_stream_result_records_why_the_model_stopped():
    result = asyncio.run(accumulate_stream(_stream(_chunk("OPLEIDINGSVORM: 'VT' ="), _chunk(finish_reason="length"))))
    assert result.text == "OPLEIDINGSVORM: 'VT' ="
    assert result.finish_reason == "length"


def _final_message_end(monkeypatch, finish_reason):
    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return StreamResult(text="Conclusie – De gevraagde indicator is niet beschikbaar in de", tool_calls=[], finish_reason=finish_reason)

    monkeypatch.setattr(run_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(run_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(run_module.run([{"role": "user", "content": "vraag"}], {}, emit, asyncio.Event(), model="openai/gpt-4o"))
    return next(e for e in events if e["type"] == "message_end")


def test_answer_cut_off_at_the_limit_is_flagged(monkeypatch):
    assert _final_message_end(monkeypatch, "length").get("truncated") is True


def test_finished_answer_is_not_flagged(monkeypatch):
    assert not _final_message_end(monkeypatch, "stop").get("truncated")
