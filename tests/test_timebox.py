"""Tijdsgrens per run (#90): melding na de drempel, netjes stoppen na de grens."""

import asyncio
import importlib
from unittest.mock import patch

from agent import timebox as timebox_module
from agent.loop import LoopResult

run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie


def _draai(nep_loop, traag_s=0.01, grens_s=0.05):
    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    vraag = [{"role": "user", "content": "Hoeveel studenten heeft de HU?"}]
    stop = asyncio.Event()
    with (
        patch.object(run_module, "tool_loop", nep_loop),
        patch.object(run_module, "RUN_SLOW_S", traag_s),
        patch.object(run_module, "RUN_TIMEOUT_S", grens_s),
    ):
        asyncio.run(run_module.run(vraag, session={}, emit=emit, stop_event=stop))
    return events, stop


def _toasts(events):
    return [e["message"] for e in events if e["type"] == "toast"]


def test_melding_na_drempel_en_stop_na_grens():
    async def wacht_op_stop(history, stop_event, **kwargs):
        await stop_event.wait()
        return LoopResult(aborted="tools")

    events, stop = _draai(wacht_op_stop)

    assert stop.is_set()  # de route bewaart een gestopte beurt niet in de geschiedenis
    toasts = _toasts(events)
    assert any("langer dan normaal" in t for t in toasts)
    assert any("gestopt" in t for t in toasts)
    assert events[-1] == {"type": "message_end", "aborted": True}


def test_vastgelopen_aanroep_wordt_afgebroken():
    async def negeert_stop(history, **kwargs):
        await asyncio.sleep(60)

    with patch.object(timebox_module, "_UITLOOP_S", 0.05):
        events, _ = _draai(negeert_stop)

    assert any("gestopt" in t for t in _toasts(events))
    assert events[-1] == {"type": "message_end", "aborted": True}


def test_snelle_run_krijgt_geen_meldingen():
    async def snel(history, **kwargs):
        return LoopResult(aborted="stream", text="Klaar.")

    events, stop = _draai(snel, traag_s=5, grens_s=10)

    assert not stop.is_set()
    assert _toasts(events) == []
