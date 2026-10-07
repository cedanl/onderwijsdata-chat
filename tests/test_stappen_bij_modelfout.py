"""Een rate limit na alle pogingen gooit de al uitgevoerde stappen niet weg (#431, CH-25).

De nieuwe poging krijgt de opgehaalde data mee in het gesprek, in plaats van alles
opnieuw op te halen en de limiet opnieuw te raken.
"""

import asyncio
import importlib

import litellm
import pytest

from agent.history import TUSSENSTAP, afgeronde_stappen
from agent.stream import StreamResult

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_VRAAG = {"role": "user", "content": "Hoeveel mbo-studenten?"}


def _aanroep(*ids: str, tekst: str = "") -> dict:
    calls = [{"id": i, "type": "function", "function": {"name": "get_duo_data", "arguments": "{}"}} for i in ids]
    return {"role": "assistant", "content": tekst, "tool_calls": calls}


def _resultaat(i: str) -> dict:
    return {"role": "tool", "tool_call_id": i, "content": f"data {i}"}


def test_afgeronde_stap_gaat_mee_met_tekst():
    stappen = afgeronde_stappen([_aanroep("a"), _resultaat("a")])
    assert stappen == [{**_aanroep("a"), "content": TUSSENSTAP}, _resultaat("a")]


def test_eigen_tekst_van_de_stap_blijft():
    assert afgeronde_stappen([_aanroep("a", tekst="Ik zoek het op."), _resultaat("a")])[0]["content"] == (
        "Ik zoek het op."
    )


def test_aanroep_zonder_alle_resultaten_gaat_niet_mee():
    beurt = [_aanroep("a"), _resultaat("a"), _aanroep("b", "c"), _resultaat("b")]
    assert afgeronde_stappen(beurt) == [{**_aanroep("a"), "content": TUSSENSTAP}, _resultaat("a")]


def test_correctieronde_hoort_bij_de_onderbroken_beurt():
    beurt = [
        _aanroep("a"),
        _resultaat("a"),
        {"role": "assistant", "content": "Er waren 12 studenten."},
        {"role": "user", "content": "Controle van je antwoord …"},
        _aanroep("b"),
        _resultaat("b"),
    ]
    assert [m["role"] for m in afgeronde_stappen(beurt)] == ["assistant", "tool", "assistant", "tool"]


def _chat_met_rate_limit_na_een_stap(monkeypatch) -> list[dict]:
    antwoorden = [StreamResult(text="", tool_calls=[{"id": "a", "name": "get_duo_data", "arguments": "{}"}])]

    async def fake_completion(*args, **kwargs):
        if not antwoorden:
            raise litellm.RateLimitError("te veel", llm_provider="openai", model="m")
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return antwoorden.pop(0)

    async def fake_execute_tool(call, emit):
        return '{"data_key": "duo:p01hoinges:0"}', None

    async def emit(event):
        pass

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    messages = [dict(_VRAAG)]
    with pytest.raises(litellm.RateLimitError):
        asyncio.run(run_module.run(messages, {}, emit, asyncio.Event()))
    return messages


def test_stappen_blijven_in_het_gesprek_na_een_rate_limit(monkeypatch):
    messages = _chat_met_rate_limit_na_een_stap(monkeypatch)

    assert [m["role"] for m in messages] == ["user", "assistant", "tool"]
    assert messages[1]["tool_calls"][0]["id"] == "a"
    assert messages[1]["content"] == TUSSENSTAP
    assert messages[2] == {"role": "tool", "tool_call_id": "a", "content": '{"data_key": "duo:p01hoinges:0"}'}
