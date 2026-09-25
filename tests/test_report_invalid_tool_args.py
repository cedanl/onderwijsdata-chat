"""Invalid tool-call arguments from the LLM must not abort the report.

The LLM can emit tool-call arguments that fail json.loads (raw control
character, trailing garbage, ...). The raw JSONDecodeError is a ValueError
subclass, so it used to surface as-is to the user via the report_error
handler. generate() must instead recover: report the malformed call to the
model and continue, so a later well-formed step can still produce a report.
"""
import asyncio
import json

import pandas as pd
import pytest

from agent import report as report_module
from agent.report import ReportSpec
from agent.stream import StreamResult
from tools import store

_DATASET = "cbs:85423NED"


@pytest.fixture(autouse=True)
def _dataset_in_store():
    store.clear()
    store.put(_DATASET, pd.DataFrame({"JAAR": [2021, 2022], "AANTAL": [10, 20]}))
    yield
    store.clear()


def _make_generate(monkeypatch, steps: list[StreamResult]):
    """Patch the LLM stream so generate() runs through the given steps."""

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        step = steps.pop(0)
        return step

    monkeypatch.setattr(report_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(report_module, "accumulate_stream", fake_accumulate)


def _run_generate():
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    spec = asyncio.run(report_module.generate(
        {"data_keys": [_DATASET], "chat_settings": {"instelling": "HU"}},
        emit,
        model="openai/gpt-4o",
    ))
    return spec, events


def _run_generate_async():
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    return report_module.generate(
        {"data_keys": [_DATASET], "chat_settings": {"instelling": "HU"}},
        emit,
        model="openai/gpt-4o",
    ), events


def test_generate_recovers_from_invalid_tool_call_arguments(monkeypatch):
    bad_args = '{"JAAR": [2021, 2022], "AANTAL": [10, 20]}\x0a{"niet": "goed"}'
    steps = [
        StreamResult(text="", tool_calls=[
            {"id": "t1", "name": "query_data", "arguments": bad_args},
        ]),
        StreamResult(text=json.dumps({
            "title": "Testrapport",
            "onderzoeksvraag": "Instroom",
            "conclusie": "Conclusie",
        }), tool_calls=[]),
    ]
    _make_generate(monkeypatch, steps)

    generate, events = _run_generate_async()
    spec = asyncio.run(generate)

    assert isinstance(spec, ReportSpec)
    assert spec.title == "Testrapport"
    types = [e["type"] for e in events]
    assert "report_error" not in types
    assert "error" not in types


def test_generate_surfaces_http_error_message_as_useful_error(monkeypatch):
    # A JSON-decoding failure deep inside a tool (e.g. a malformed upstream)
    # is a ValueError subclass; generate() must not leak the raw parser text.
    bad_args = '{"data_key": "cbs:00000NED"}\x08'
    steps = [
        StreamResult(text="", tool_calls=[
            {"id": "t1", "name": "query_data", "arguments": bad_args},
        ]),
        StreamResult(text=json.dumps({
            "title": "Testrapport",
            "onderzoeksvraag": "Instroom",
            "conclusie": "Conclusie",
        }), tool_calls=[]),
    ]
    _make_generate(monkeypatch, steps)

    generate, _ = _run_generate_async()
    spec = asyncio.run(generate)

    assert isinstance(spec, ReportSpec)
    assert spec.title == "Testrapport"

def test_generate_logs_each_tool_call_with_arguments_and_rows(monkeypatch, caplog):
    # #174: de audit kon een misfilter in het rapport niet aanwijzen; de WS-frames tonen alleen toolnamen.
    query = {"data_key": _DATASET, "filters": {"JAAR": 2021}}
    _make_generate(monkeypatch, [
        StreamResult(text="", tool_calls=[{"id": "t1", "name": "query_data", "arguments": json.dumps(query)}]),
        StreamResult(text='{"title": "T"}', tool_calls=[]),
    ])

    with caplog.at_level("INFO", logger="agent.report"):
        _run_generate()

    [record] = [r for r in caplog.records if "RAPPORT TOOL" in r.message]
    assert "query_data" in record.message
    assert '"JAAR": 2021' in record.message
    assert "totaal_rijen=1" in record.message


def _final(conclusie: str) -> StreamResult:
    return StreamResult(text=json.dumps({"title": "T", "conclusie": conclusie}), tool_calls=[])


def test_generate_retries_once_with_a_correction_when_the_report_contradicts_its_data(monkeypatch):
    # #175: een getal dat niet in de data staat krijgt één herkansing met een concrete correctie.
    seen: list[list[dict]] = []

    async def fake_completion(*args, **kwargs):
        seen.append(list(kwargs["messages"]))
        return object()

    _make_generate(monkeypatch, [_final("In 2021 waren het er 12.345."), _final("In 2021 waren het er 10.")])
    monkeypatch.setattr(report_module, "acompletion_with_backoff", fake_completion)

    spec, _ = _run_generate()

    assert spec.conclusie == "In 2021 waren het er 10."
    correctie = seen[-1][-1]
    assert correctie["role"] == "user" and "12.345" in correctie["content"]


def test_generate_refuses_a_report_that_stays_inconsistent(monkeypatch):
    _make_generate(monkeypatch, [_final("Het waren er 12.345."), _final("Het waren er 54.321.")])

    with pytest.raises(ValueError, match="niet consistent"):
        _run_generate()
