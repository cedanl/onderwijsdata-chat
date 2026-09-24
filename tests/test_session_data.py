import asyncio
import importlib
import json

import pandas as pd

from agent.session_data import record_data_key, session_data_keys
from agent.stream import StreamResult
from tools import store

run_module = importlib.import_module("agent.run")


def test_records_data_key_from_tool_result():
    session: dict = {}
    record_data_key(session, json.dumps({"data_key": "duo:p01hoinges:0", "totaal_rijen": 3}))
    record_data_key(session, json.dumps({"data_key": "duo:p01hoinges:0"}))
    record_data_key(session, json.dumps({"data_key": "query:abc"}))
    assert session["data_keys"] == ["duo:p01hoinges:0", "query:abc"]


def test_ignores_results_without_data_key():
    session: dict = {}
    for result in ("Fout bij ophalen RIO data: timeout", "[1, 2]", json.dumps({"rijen": []}), ""):
        record_data_key(session, result)
    assert session.get("data_keys", []) == []


def test_session_keys_skip_data_no_longer_in_store():
    store.put("cbs:85423NED", pd.DataFrame({"a": [1]}))
    session = {"data_keys": ["cbs:85423NED", "rio:erkenningen"]}
    assert session_data_keys(session) == ["cbs:85423NED"]


def test_agent_run_records_keys_of_its_tool_calls(monkeypatch):
    steps = iter([
        StreamResult(text="", tool_calls=[{"id": "t1", "name": "get_cbs_data", "arguments": '{"dataset_id": "85423NED"}'}]),
        StreamResult(text="Antwoord", tool_calls=[]),
    ])

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return next(steps)

    async def fake_call_tool(tc, emit):
        return json.dumps({"data_key": "cbs:85423NED"}), None

    async def emit(event: dict) -> None:
        pass

    monkeypatch.setattr(run_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(run_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(run_module, "_call_tool", fake_call_tool)

    session: dict = {}
    asyncio.run(run_module.run(
        [{"role": "user", "content": "vraag"}], session, emit, asyncio.Event(), model="openai/gpt-4o",
    ))
    assert session["data_keys"] == ["cbs:85423NED"]
