import asyncio
import importlib
import json

import pandas as pd

from agent.session_data import data_lineage, record_data_key, session_data_keys
from agent.stream import StreamResult
from tools import store

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")


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

    async def fake_execute_tool(call, emit):
        return json.dumps({"data_key": "cbs:85423NED"}), None

    async def emit(event: dict) -> None:
        pass

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)

    session: dict = {}
    asyncio.run(run_module.run(
        [{"role": "user", "content": "vraag"}], session, emit, asyncio.Event(), model="openai/gpt-4o",
    ))
    assert session["data_keys"] == ["cbs:85423NED"]
    assert session["data_provenance"]["cbs:85423NED"] == {
        "name": "get_cbs_data", "arguments": {"dataset_id": "85423NED"},
    }


_CBS_CALL = {"name": "get_cbs_data", "arguments": {"dataset_id": "85423NED", "filters": {"$filter": "Onderwijssoort eq 'A025294'"}}}
_QUERY_CALL = {"name": "query_data", "arguments": {"data_key": "cbs:85423NED:aa", "filters": {"Opleidingsvorm": "A028666"}}}


def test_lineage_of_a_derived_key_runs_from_the_load_call():
    # #174: het rapport moet zien welke selectie het gesprek maakte, niet alleen de key.
    session: dict = {}
    record_data_key(session, json.dumps({"data_key": "cbs:85423NED:aa"}), _CBS_CALL)
    record_data_key(session, json.dumps({"data_key": "cbs:85423NED:aa:bb"}), _QUERY_CALL)

    assert data_lineage(session, "cbs:85423NED:aa:bb") == [_CBS_CALL, _QUERY_CALL]
    assert data_lineage(session, "cbs:85423NED:aa") == [_CBS_CALL]


def test_lineage_is_empty_without_recorded_call():
    session: dict = {}
    record_data_key(session, json.dumps({"data_key": "cbs:85423NED"}))
    assert data_lineage(session, "cbs:85423NED") == []


def test_query_without_transformation_keeps_the_load_call():
    # query_data zonder filters geeft de eigen key terug; die mag de laadcall niet vervangen.
    session: dict = {}
    record_data_key(session, json.dumps({"data_key": "cbs:85423NED:aa"}), _CBS_CALL)
    noop = {"name": "query_data", "arguments": {"data_key": "cbs:85423NED:aa"}}
    record_data_key(session, json.dumps({"data_key": "cbs:85423NED:aa"}), noop)

    assert data_lineage(session, "cbs:85423NED:aa") == [_CBS_CALL]
