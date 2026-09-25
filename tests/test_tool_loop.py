"""De gedeelde toolloop van chat, rapport en dashboard (#192).

De LLM-stroom wordt nagebootst: elke stap is één StreamResult. Tools draaien echt
via dispatch() tenzij een test _execute_tool vervangt.
"""
import asyncio

import pytest

from agent import loop as loop_module
from agent.stream import StreamResult


def _call(name: str, arguments: str = "{}", call_id: str = "t1") -> dict:
    return {"id": call_id, "name": name, "arguments": arguments}


def _steps(monkeypatch, steps: list[StreamResult], seen: list | None = None) -> None:
    async def fake_completion(*args, **kwargs):
        if seen is not None:
            seen.append(list(kwargs["messages"]))
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)


def _fake_tools(monkeypatch, results: dict[str, str], calls: list | None = None) -> None:
    async def fake_execute(call, emit):
        if calls is not None:
            calls.append(call.name)
        return results[call.name], None

    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute)


def _run(messages=None, **kwargs):
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    kwargs.setdefault("max_iterations", 5)
    kwargs.setdefault("max_result_chars", 1000)
    result = asyncio.run(loop_module.tool_loop(
        messages if messages is not None else [{"role": "user", "content": "vraag"}],
        model="openai/gpt-4o", tools=[], emit=emit, **kwargs,
    ))
    return result, events


def test_answer_without_tools_ends_the_loop(monkeypatch):
    _steps(monkeypatch, [StreamResult(text="Antwoord.", tool_calls=[], finish_reason="stop")])

    result, _ = _run()

    assert result.text == "Antwoord."
    assert result.finish_reason == "stop"
    assert not result.aborted and not result.exhausted


def test_tool_result_goes_back_to_the_model_and_is_kept_in_full(monkeypatch):
    lang = "x" * 50
    _steps(monkeypatch, [
        StreamResult(text="", tool_calls=[_call("query_data")]),
        StreamResult(text="Klaar.", tool_calls=[]),
    ])
    _fake_tools(monkeypatch, {"query_data": lang})
    messages = [{"role": "user", "content": "vraag"}]

    result, _ = _run(messages, max_result_chars=10)

    assert result.tool_results == [lang]
    tool_msg = next(m for m in messages if m["role"] == "tool")
    assert tool_msg["content"].startswith("x" * 10) and "afgekapt" in tool_msg["content"]
    assert result.tool_calls == [{"name": "query_data", "arguments": "{}"}]


def test_invalid_tool_arguments_become_feedback_not_a_crash(monkeypatch):
    _steps(monkeypatch, [
        StreamResult(text="", tool_calls=[_call("query_data", '{"data_key": "x",\x01}')]),
        StreamResult(text="Hersteld.", tool_calls=[]),
    ])
    executed: list[str] = []
    _fake_tools(monkeypatch, {}, executed)
    messages = [{"role": "user", "content": "vraag"}]

    result, _ = _run(messages)

    assert result.text == "Hersteld."
    assert executed == []
    assert "geen geldige JSON" in next(m for m in messages if m["role"] == "tool")["content"]


def test_identical_calls_run_once(monkeypatch):
    _steps(monkeypatch, [
        StreamResult(text="", tool_calls=[_call("query_data", call_id="a"), _call("query_data", call_id="b")]),
        StreamResult(text="", tool_calls=[_call("query_data", call_id="c")]),
        StreamResult(text="Klaar.", tool_calls=[]),
    ])
    executed: list[str] = []
    _fake_tools(monkeypatch, {"query_data": "rijen"}, executed)

    result, _ = _run()

    assert executed == ["query_data"]
    assert result.tool_results == ["rijen", "rijen", "rijen"]


def test_tool_limit_blocks_further_calls(monkeypatch):
    _steps(monkeypatch, [
        StreamResult(text="", tool_calls=[_call("search_catalog", '{"q": 1}')]),
        StreamResult(text="", tool_calls=[_call("search_catalog", '{"q": 2}')]),
        StreamResult(text="Klaar.", tool_calls=[]),
    ])
    executed: list[str] = []
    _fake_tools(monkeypatch, {"search_catalog": "treffers"}, executed)
    messages = [{"role": "user", "content": "vraag"}]

    _run(messages, tool_limits={"search_catalog": 1})

    assert executed == ["search_catalog"]
    assert "LIMIET" in [m for m in messages if m["role"] == "tool"][-1]["content"]


def test_on_tool_result_sees_every_call_with_its_parsed_arguments(monkeypatch):
    _steps(monkeypatch, [
        StreamResult(text="", tool_calls=[_call("query_data", '{"data_key": "k"}')]),
        StreamResult(text="Klaar.", tool_calls=[]),
    ])
    _fake_tools(monkeypatch, {"query_data": "rijen"})
    seen: list = []

    async def on_tool_result(call, result, figure):
        seen.append((call.name, call.args, result, figure))

    _run(on_tool_result=on_tool_result)

    assert seen == [("query_data", {"data_key": "k"}, "rijen", None)]


def test_halt_tool_ends_the_turn_without_running(monkeypatch):
    _steps(monkeypatch, [StreamResult(text="", tool_calls=[_call("clarify_scope", '{"vraag": "Welk jaar?"}')])])
    executed: list[str] = []
    _fake_tools(monkeypatch, {}, executed)
    messages = [{"role": "user", "content": "vraag"}]

    result, _ = _run(messages, halt_on=frozenset({"clarify_scope"}))

    assert executed == []
    assert result.halted_on.name == "clarify_scope"
    assert result.halted_on.args == {"vraag": "Welk jaar?"}
    assert messages[-1] == {"role": "tool", "tool_call_id": "t1", "content": "OK"}


def test_stop_while_tools_run_aborts_before_the_next_model_call(monkeypatch):
    stop_event = asyncio.Event()
    _steps(monkeypatch, [StreamResult(text="Even kijken.", tool_calls=[_call("search_catalog")])])

    async def fake_execute(call, emit):
        stop_event.set()
        return "treffers", None

    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute)

    result, _ = _run(stop_event=stop_event)

    assert result.aborted == "tools"
    assert result.text == "Even kijken."


def test_stop_during_the_stream_keeps_the_text(monkeypatch):
    stop_event = asyncio.Event()

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        stop_event.set()
        return StreamResult(text="Half", tool_calls=[])

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)

    result, _ = _run(stop_event=stop_event)

    assert result.aborted == "stream"
    assert result.text == "Half"


def test_running_out_of_iterations_is_reported(monkeypatch):
    _steps(monkeypatch, [StreamResult(text="", tool_calls=[_call("query_data", call_id=str(i))]) for i in range(2)])
    _fake_tools(monkeypatch, {"query_data": "rijen"})

    result, _ = _run(max_iterations=2)

    assert result.exhausted


def test_check_gets_one_correction_round(monkeypatch):
    seen: list = []
    _steps(monkeypatch, [StreamResult(text="Fout 12.345", tool_calls=[]), StreamResult(text="Goed 10", tool_calls=[])], seen)

    result, _ = _run(
        check=lambda text, tool_results: ["12.345 staat niet in de data"] if "12.345" in text else [],
        correction=lambda problems: "Herstel: " + "; ".join(problems),
    )

    assert result.text == "Goed 10"
    assert result.problems == []
    assert seen[-1][-1] == {"role": "user", "content": "Herstel: 12.345 staat niet in de data"}


def test_check_problems_that_remain_are_returned_not_retried_again(monkeypatch):
    _steps(monkeypatch, [StreamResult(text="Fout 1", tool_calls=[]), StreamResult(text="Fout 2", tool_calls=[])])

    result, _ = _run(check=lambda text, tool_results: ["fout"], correction=lambda problems: "Herstel")

    assert result.text == "Fout 2"
    assert result.problems == ["fout"]


def test_model_error_keeps_the_partial_result_when_the_caller_can_use_it(monkeypatch):
    _steps(monkeypatch, [StreamResult(text="", tool_calls=[_call("create_plot")])])
    _fake_tools(monkeypatch, {"create_plot": "grafiek"})
    calls = {"n": 0}
    real_fake = loop_module.acompletion_with_backoff

    async def failing_second_call(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("rate limit")
        return await real_fake(*args, **kwargs)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", failing_second_call)

    result, _ = _run(keep_partial=lambda: True)
    assert result.partial_error == "rate limit"

    calls["n"] = 0
    _steps(monkeypatch, [StreamResult(text="", tool_calls=[_call("create_plot")])])
    monkeypatch.setattr(loop_module, "acompletion_with_backoff", failing_second_call)
    with pytest.raises(RuntimeError):
        _run(keep_partial=lambda: False)


def test_caller_hears_about_the_correction_before_it_runs(monkeypatch):
    _steps(monkeypatch, [StreamResult(text="Fout 12.345", tool_calls=[]), StreamResult(text="Goed", tool_calls=[])])
    heard: list = []

    async def on_correction(problems):
        heard.append(problems)

    _run(check=lambda text, tool_results: ["12.345"] if "12.345" in text else [],
         correction=lambda problems: "Herstel", on_correction=on_correction)

    assert heard == [["12.345"]]
