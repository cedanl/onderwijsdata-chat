"""De gedeelde toolloop van chat, rapport en dashboard (#192).

De LLM-stroom wordt nagebootst: elke stap is één StreamResult. Tools draaien echt
via dispatch() tenzij een test _execute_tool vervangt.
"""

import asyncio

import plotly.graph_objects as go
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
    result = asyncio.run(
        loop_module.tool_loop(
            messages if messages is not None else [{"role": "user", "content": "vraag"}],
            model="openai/gpt-4o",
            tools=[],
            emit=emit,
            **kwargs,
        )
    )
    return result, events


def test_answer_without_tools_ends_the_loop(monkeypatch):
    _steps(monkeypatch, [StreamResult(text="Antwoord.", tool_calls=[], finish_reason="stop")])

    result, _ = _run()

    assert result.text == "Antwoord."
    assert result.finish_reason == "stop"
    assert not result.aborted and not result.exhausted


def test_tool_result_goes_back_to_the_model_and_is_kept_in_full(monkeypatch):
    lang = "x" * 50
    _steps(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_call("query_data")]),
            StreamResult(text="Klaar.", tool_calls=[]),
        ],
    )
    _fake_tools(monkeypatch, {"query_data": lang})
    messages = [{"role": "user", "content": "vraag"}]

    result, _ = _run(messages, max_result_chars=10)

    assert result.tool_results == [lang]
    tool_msg = next(m for m in messages if m["role"] == "tool")
    assert tool_msg["content"].startswith("x" * 10) and "afgekapt" in tool_msg["content"]
    assert result.tool_calls == [{"name": "query_data", "arguments": "{}"}]


def test_invalid_tool_arguments_become_feedback_not_a_crash(monkeypatch):
    _steps(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_call("query_data", '{"data_key": "x",\x01}')]),
            StreamResult(text="Hersteld.", tool_calls=[]),
        ],
    )
    executed: list[str] = []
    _fake_tools(monkeypatch, {}, executed)
    messages = [{"role": "user", "content": "vraag"}]

    result, _ = _run(messages)

    assert result.text == "Hersteld."
    assert executed == []
    assert "geen geldige JSON" in next(m for m in messages if m["role"] == "tool")["content"]


def test_identical_calls_run_once(monkeypatch):
    _steps(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_call("query_data", call_id="a"), _call("query_data", call_id="b")]),
            StreamResult(text="", tool_calls=[_call("query_data", call_id="c")]),
            StreamResult(text="Klaar.", tool_calls=[]),
        ],
    )
    executed: list[str] = []
    _fake_tools(monkeypatch, {"query_data": "rijen"}, executed)

    result, _ = _run()

    assert executed == ["query_data"]
    assert result.tool_results == ["rijen", "rijen", "rijen"]


def test_tool_limit_blocks_further_calls(monkeypatch):
    _steps(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_call("search_catalog", '{"q": 1}')]),
            StreamResult(text="", tool_calls=[_call("search_catalog", '{"q": 2}')]),
            StreamResult(text="Klaar.", tool_calls=[]),
        ],
    )
    executed: list[str] = []
    _fake_tools(monkeypatch, {"search_catalog": '[{"_cbs_id": "85423NED"}]'}, executed)
    messages = [{"role": "user", "content": "vraag"}]

    _run(messages, tool_limits={"search_catalog": 1})

    assert executed == ["search_catalog"]
    assert "LIMIET" in [m for m in messages if m["role"] == "tool"][-1]["content"]


def test_a_search_without_hits_does_not_use_up_the_limit(monkeypatch):
    _steps(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_call("search_catalog", '{"q": 1}')]),
            StreamResult(text="", tool_calls=[_call("search_catalog", '{"q": 2}')]),
            StreamResult(text="Klaar.", tool_calls=[]),
        ],
    )
    executed: list[str] = []
    _fake_tools(monkeypatch, {"search_catalog": "Geen resultaten gevonden voor 'x'."}, executed)
    messages = [{"role": "user", "content": "vraag"}]

    _run(messages, tool_limits={"search_catalog": 1})

    assert executed == ["search_catalog", "search_catalog"]
    assert not any("LIMIET" in m["content"] for m in messages if m["role"] == "tool")


def test_on_tool_result_sees_every_call_with_its_parsed_arguments(monkeypatch):
    _steps(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_call("query_data", '{"data_key": "k"}')]),
            StreamResult(text="Klaar.", tool_calls=[]),
        ],
    )
    _fake_tools(monkeypatch, {"query_data": "rijen"})
    seen: list = []

    async def on_tool_result(call, result, figure):
        seen.append((call.name, call.args, result, figure))

    _run(on_tool_result=on_tool_result)

    assert seen == [("query_data", {"data_key": "k"}, "rijen", None)]


def test_identical_tool_call_shows_its_figure_once_but_answers_every_call(monkeypatch):
    # #218: a cache hit re-emitted the figure, so the user saw the same chart twice.
    _steps(
        monkeypatch,
        [
            StreamResult(
                text="", tool_calls=[_call("create_plot", '{"x": "a"}', "t1"), _call("create_plot", '{"x": "a"}', "t2")]
            ),
            StreamResult(text="", tool_calls=[_call("create_plot", '{"x": "a"}', "t3")]),
            StreamResult(text="Klaar.", tool_calls=[]),
        ],
    )
    executed: list[str] = []

    async def fake_execute(call, emit):
        executed.append(call.name)
        return "grafiek gemaakt", "FIG"

    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute)
    seen: list = []

    async def on_tool_result(call, result, figure):
        seen.append((call.id, result, figure))

    messages = [{"role": "user", "content": "vraag"}]
    _run(messages, on_tool_result=on_tool_result)

    assert executed == ["create_plot"]
    assert [figure for _, _, figure in seen] == ["FIG", None, None]
    assert all(result == "grafiek gemaakt" for _, result, _ in seen)
    assert [m["content"] for m in messages if m["role"] == "tool"] == ["grafiek gemaakt"] * 3


def test_the_same_chart_from_differently_written_arguments_is_shown_once(monkeypatch):
    # #327: after a correction round the model called create_plot again with the same arguments in
    # another order. Another cache key, the same chart: the top-5 answer showed it twice.
    _steps(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_call("create_plot", '{"x": "a", "y": "b"}', "t1")]),
            StreamResult(text="", tool_calls=[_call("create_plot", '{"y":"b","x":"a"}', "t2")]),
            StreamResult(text="Klaar.", tool_calls=[]),
        ],
    )

    async def fake_execute(call, emit):
        return "grafiek gemaakt", go.Figure(go.Bar(x=["a"], y=[1]))

    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute)
    seen: list = []

    async def on_tool_result(call, result, figure):
        seen.append(figure)

    _run(on_tool_result=on_tool_result)

    assert [f is not None for f in seen] == [True, False]


def test_same_tool_with_other_arguments_shows_another_figure(monkeypatch):
    _steps(
        monkeypatch,
        [
            StreamResult(
                text="", tool_calls=[_call("create_plot", '{"x": "a"}', "t1"), _call("create_plot", '{"x": "b"}', "t2")]
            ),
            StreamResult(text="Klaar.", tool_calls=[]),
        ],
    )

    async def fake_execute(call, emit):
        return "ok", f"FIG-{call.args['x']}"

    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute)
    seen: list = []

    async def on_tool_result(call, result, figure):
        seen.append(figure)

    _run(on_tool_result=on_tool_result)

    assert seen == ["FIG-a", "FIG-b"]


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
    _steps(
        monkeypatch,
        [StreamResult(text="Fout 12.345", tool_calls=[]), StreamResult(text="Goed 10", tool_calls=[])],
        seen,
    )

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

    _run(
        check=lambda text, tool_results: ["12.345"] if "12.345" in text else [],
        correction=lambda problems: "Herstel",
        on_correction=on_correction,
    )

    assert heard == [["12.345"]]


# --- #18: geladen dataset gekoppeld aan de zoekactie ervoor ---

_TREFFERS = '[{"_cbs_id": "85423NED"}, {"_ckan_id": "p01hoinges"}, {"_ckan_id": "p02ho1ejrs"}, {"_ckan_id": "ver-weg"}]'


def _search_then_load(monkeypatch, laad_tool, laad_args):
    _steps(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_call("search_catalog", '{"query": "ingeschrevenen"}', "t1")]),
            StreamResult(text="", tool_calls=[_call(laad_tool, laad_args, "t2")]),
            StreamResult(text="Klaar.", tool_calls=[]),
        ],
    )
    _fake_tools(monkeypatch, {"search_catalog": _TREFFERS, laad_tool: '{"data_key": "k"}'})


def test_load_inside_the_top_three_is_logged_without_deviation(monkeypatch, caplog):
    _search_then_load(monkeypatch, "get_duo_data", '{"dataset_id": "p01hoinges"}')

    with caplog.at_level("INFO", logger="agent.search_trace"):
        _run()

    assert any("CATALOGUS_GELADEN" in r.message and "afwijking=nee" in r.message for r in caplog.records)
    assert not any("CATALOGUS_AFWIJKING" in r.message for r in caplog.records)


def test_load_lines_carry_the_catalogue_digest(monkeypatch, caplog):
    # A shifted top three after a catalogue update must be told apart from a behaviour change (#344).
    from tools.catalog import catalogus_digest

    _search_then_load(monkeypatch, "get_duo_data", '{"dataset_id": "p01hoinges"}')

    with caplog.at_level("INFO", logger="agent.search_trace"):
        _run()

    [record] = [r for r in caplog.records if "CATALOGUS_GELADEN" in r.message]
    assert f"catalogus={catalogus_digest()}" in record.message


def test_load_outside_the_top_three_is_a_separate_metric(monkeypatch, caplog):
    # "ver-weg" is hit four: the model had to correct the ranking.
    _search_then_load(monkeypatch, "get_duo_data", '{"dataset_id": "ver-weg"}')

    with caplog.at_level("INFO", logger="agent.search_trace"):
        _run()

    [record] = [r for r in caplog.records if "CATALOGUS_AFWIJKING" in r.message]
    assert "ver-weg" in record.message and "ingeschrevenen" in record.message
    assert "85423NED" in record.message  # the top three it was measured against


def test_rio_load_is_matched_on_its_resource_argument(monkeypatch, caplog):
    _search_then_load(monkeypatch, "get_rio_data", '{"resource": "p02ho1ejrs"}')

    with caplog.at_level("INFO", logger="agent.search_trace"):
        _run()

    assert any("afwijking=nee" in r.message for r in caplog.records)
