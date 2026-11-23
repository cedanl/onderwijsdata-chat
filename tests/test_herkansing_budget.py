"""De herkansing na een mislukte controle komt niet bovenop het stappenbudget (#1090).

Het budget begrenst het aantal toolstappen per vraag. Na een afrondronde zonder tools (`tool_choice: none`) of een
budget dat op was, startte de herkansing een nieuwe, volledige reeks rondes met alle tools: een vraag die al vastliep
op 25 stappen kon er nog eens 25 doen. Nu krijgt de herkansing hooguit wat er van het budget over is, en na een op
budget geen tools meer.
"""

import asyncio
import json

import pytest

from agent import loop as loop_module
from agent.stream import StreamResult

_FOUT = "12.345 staat niet in de data"


def _check(text: str, tool_results: list[str]) -> list[str]:
    return [_FOUT] if "12.345" in text else []


def _tool(call_id: str) -> StreamResult:
    arguments = json.dumps({"data_key": f"duo:p01hoinges:{call_id}"})
    return StreamResult(text="", tool_calls=[{"id": call_id, "name": "query_data", "arguments": arguments}])


def _beurt(monkeypatch, stappen: list[StreamResult], **kwargs) -> tuple[loop_module.LoopResult, list, list]:
    """Een toolloop met een nagebootst model; geeft het resultaat, de `tool_choice` per modelaanroep en de
    uitgevoerde toolaanroepen. Elke toolaanroep krijgt een eigen uitkomst: de loop voert identieke aanroepen één keer uit."""
    keuzes: list = []
    uitgevoerd: list[str] = []

    async def fake_completion(*args, **kw):
        keuzes.append(kw.get("tool_choice"))
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    async def fake_execute(call, emit, recept_van=None):
        uitgevoerd.append(call.id)
        return f"resultaat {call.id}", None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    result = asyncio.run(
        loop_module.tool_loop(
            [{"role": "user", "content": "vraag"}],
            model="openai/gpt-4o",
            tools=[{"type": "function", "function": {"name": "query_data"}}],
            emit=emit,
            max_result_chars=1000,
            check=_check,
            correction=lambda problems: "Herstel: " + "; ".join(problems),
            **kwargs,
        )
    )
    return result, keuzes, uitgevoerd


def test_na_de_afrondronde_krijgt_de_herkansing_geen_tools(monkeypatch):
    stappen = [
        _tool("a"),
        _tool("b"),
        StreamResult(text=f"Deelantwoord: {_FOUT}", tool_calls=[]),  # afrondronde, tool_choice none
        StreamResult(text="Hersteld antwoord.", tool_calls=[]),  # herkansing
    ]

    result, keuzes, uitgevoerd = _beurt(monkeypatch, stappen, max_iterations=2, wrap_up="Rond af.")

    assert keuzes == [None, None, "none", "none"]
    assert uitgevoerd == ["a", "b"]
    assert result.text == "Hersteld antwoord." and result.wrapped_up and not result.exhausted
    assert result.problems == []


def test_een_model_dat_in_de_herkansing_toch_een_tool_aanroept_krijgt_hem_niet(monkeypatch):
    stappen = [
        _tool("a"),
        StreamResult(text=f"Deelantwoord: {_FOUT}", tool_calls=[]),
        _tool("extra"),  # de herkansing, ondanks tool_choice none
    ]

    result, _, uitgevoerd = _beurt(monkeypatch, stappen, max_iterations=1, wrap_up="Rond af.")

    assert uitgevoerd == ["a"]
    assert result.exhausted


def test_een_budget_dat_met_het_antwoord_op_raakt_geeft_een_herkansing_zonder_tools(monkeypatch):
    """Het antwoord was de laatste ronde van het budget: geen afrondronde, wel een herkansing, maar zonder tools."""
    stappen = [
        _tool("a"),
        StreamResult(text=f"Antwoord: {_FOUT}", tool_calls=[]),
        StreamResult(text="Hersteld.", tool_calls=[]),
    ]

    result, keuzes, uitgevoerd = _beurt(monkeypatch, stappen, max_iterations=2, wrap_up="Rond af.")

    assert uitgevoerd == ["a"]
    assert keuzes == [None, None, "none"]
    assert result.text == "Hersteld." and result.problems == []
    assert not result.wrapped_up, "de herstelde tekst blijft een gewoon antwoord, geen deelantwoord"


def test_het_totaal_aan_toolstappen_is_nooit_groter_dan_het_budget(monkeypatch):
    stappen = [
        _tool("a"),
        StreamResult(text=f"Antwoord: {_FOUT}", tool_calls=[]),  # ronde 2 van 3: een fout getal
        _tool("b"),  # de herkansing mag nog één ronde met tools (ronde 3 van 3)
        _tool("c"),  # budget op: afrondronde zonder tools; dit is een toolaanroep dus exhausted
    ]

    result, keuzes, uitgevoerd = _beurt(monkeypatch, stappen, max_iterations=3, wrap_up="Rond af.")

    assert uitgevoerd == ["a", "b"]
    assert len(uitgevoerd) <= 3
    assert keuzes == [None, None, None, "none"]
    assert result.exhausted


@pytest.mark.parametrize("max_iterations", [4, 5, 25])
def test_een_herkansing_binnen_het_budget_werkt_zoals_voorheen(monkeypatch, max_iterations):
    stappen = [
        _tool("a"),
        StreamResult(text=f"Antwoord: {_FOUT}", tool_calls=[]),
        _tool("b"),  # de herkansing haalt nog een bron op
        StreamResult(text="Hersteld antwoord.", tool_calls=[]),
    ]

    result, keuzes, uitgevoerd = _beurt(monkeypatch, stappen, max_iterations=max_iterations, wrap_up="Rond af.")

    assert uitgevoerd == ["a", "b"]
    assert keuzes == [None] * 4
    assert result.text == "Hersteld antwoord." and result.problems == []
    assert not result.wrapped_up and not result.exhausted
