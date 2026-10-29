"""Tijdsgrens per run (#90): een signaal na de drempel, netjes stoppen na de grens."""

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


def _traag(events):
    return [e for e in events if e["type"] == "run_slow"]


def _einde_na_grens(events):
    einde = events[-1]
    assert einde["type"] == "message_end"
    assert einde["aborted"] is True
    # Eigen veld naast aborted (#775): de chat ziet het verschil met de stopknop en houdt de reden bij het bericht.
    assert einde["timeout"] is True
    assert "gestopt" in einde["stopreden"]
    return einde


def test_melding_na_drempel_en_stop_na_grens():
    async def wacht_op_stop(history, stop_event, **kwargs):
        await stop_event.wait()
        return LoopResult(aborted="tools")

    events, stop = _draai(wacht_op_stop)

    assert stop.is_set()  # de route bewaart een gestopte beurt niet in de geschiedenis
    # Na de drempel een signaal, geen toast (#599): de chat zet het als vaste regel onder de voortgang.
    assert _traag(events) == [{"type": "run_slow"}]
    # De reden staat in message_end, niet meer in een toast van vier seconden (#775).
    assert _toasts(events) == []
    _einde_na_grens(events)


def test_gestopt_tijdens_het_streamen_houdt_de_tekst_en_de_reden():
    async def stopt_in_stream(history, stop_event, **kwargs):
        await stop_event.wait()
        return LoopResult(aborted="stream", text="Het eerste deel")

    events, _ = _draai(stopt_in_stream)

    assert _toasts(events) == []
    assert _einde_na_grens(events)["content"] == "Het eerste deel"


def test_stopknop_is_geen_tijdsgrens():
    async def gestopt(history, stop_event, **kwargs):
        stop_event.set()
        return LoopResult(aborted="tools")

    events, _ = _draai(gestopt, traag_s=5, grens_s=10)

    assert events[-1] == {"type": "message_end", "aborted": True}


def test_vastgelopen_aanroep_wordt_afgebroken():
    async def negeert_stop(history, **kwargs):
        await asyncio.sleep(60)

    with patch.object(timebox_module, "_UITLOOP_S", 0.05):
        events, _ = _draai(negeert_stop)

    assert _toasts(events) == []
    _einde_na_grens(events)


def test_snelle_run_krijgt_geen_meldingen():
    async def snel(history, **kwargs):
        return LoopResult(aborted="stream", text="Klaar.")

    events, stop = _draai(snel, traag_s=5, grens_s=10)

    assert not stop.is_set()
    assert _toasts(events) == []
    assert _traag(events) == []
