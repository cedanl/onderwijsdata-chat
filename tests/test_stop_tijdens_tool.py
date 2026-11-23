"""Stop genereren werkt ook tijdens een lopende tool (#1087).

#759 loste dat op voor de modelaanroep; de tools liepen in een thread zonder stopcontrole. Een stop tijdens een
`run_analysis` die tot de sandboxgrens rekende (10 s), kwam pas aan het einde van de tool door, en het kindproces
rekende door. Nu wacht de loop niet meer op de tool, en het sandboxproces wordt gedood.
"""

import asyncio
import importlib
import json
import subprocess
import threading
import time

import pandas as pd
import pytest

from agent.stream import StreamResult
from tools import afbreken, sandbox, store

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_OPLOOP = "while True:\n    pass"
# run_analysis weigert een script dat geen data leest; dit rekent door zolang er rijen zijn.
_REKENT = "while len(df):\n    pass"
_KEY = "test:stop"


def _model(monkeypatch, stappen: list[StreamResult]) -> None:
    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)


def _stop_na(stop: asyncio.Event, seconden: float) -> asyncio.Task:
    async def wacht_en_stop():
        await asyncio.sleep(seconden)
        stop.set()

    return asyncio.ensure_future(wacht_en_stop())


async def _beurt(stop: asyncio.Event, na: float) -> tuple[list[dict], float]:
    """De chatbeurt `vraag` met een stop na `na` seconden; geeft de events en de duur."""
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    stopper = _stop_na(stop, na)
    start = time.monotonic()
    await run_module.run([{"role": "user", "content": "vraag"}], {}, emit, stop, model="openai/gpt-4o")
    await stopper
    return events, time.monotonic() - start


@pytest.mark.usefixtures("zonder_scopekaart")
def test_stop_tijdens_een_trage_tool_beeindigt_de_beurt_meteen(monkeypatch):
    _model(monkeypatch, [StreamResult(text="", tool_calls=[{"id": "t1", "name": "search_catalog", "arguments": "{}"}])])

    async def trage_tool(call, emit, recept_van=None):
        await asyncio.sleep(30)
        return "resultaat", None

    monkeypatch.setattr(loop_module, "_execute_tool", trage_tool)

    events, duur = asyncio.run(_beurt(asyncio.Event(), na=0.3))

    assert events[-1]["type"] == "message_end" and events[-1]["aborted"] is True
    assert "error" not in [e["type"] for e in events]
    assert duur < 2.5, f"de stop wachtte {duur:.1f} s op de tool"


@pytest.mark.usefixtures("zonder_scopekaart")
def test_een_stop_tijdens_run_analysis_komt_binnen_een_paar_seconden_aan_en_doodt_het_kindproces(monkeypatch):
    """Het echte pad: dispatch, `run_analysis`, het sandboxproces; een script dat de volle 10 s zou rekenen."""
    store.put(_KEY, pd.DataFrame({"N": [1]}), store.KeyMeta(bron="test", dataset="stop", volledig=True))
    arguments = json.dumps({"code": _REKENT, "data_key": _KEY})
    _model(
        monkeypatch, [StreamResult(text="", tool_calls=[{"id": "a1", "name": "run_analysis", "arguments": arguments}])]
    )
    kinderen: list[subprocess.Popen] = []

    class Gevolgd(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            kinderen.append(self)

    monkeypatch.setattr(sandbox.subprocess, "Popen", Gevolgd)

    try:
        events, duur = asyncio.run(_beurt(asyncio.Event(), na=2.0))
    finally:
        store.clear()

    assert events[-1]["type"] == "message_end" and events[-1]["aborted"] is True
    assert duur < 4, f"de stop wachtte {duur:.1f} s"
    assert len(kinderen) == 1
    # asyncio.run wacht op de thread van de tool: het kindproces is dan al gedood.
    assert kinderen[0].returncode is not None and kinderen[0].returncode != 0


def test_het_sandboxproces_stopt_zodra_de_aanroep_wordt_geannuleerd():
    kinderen: list[subprocess.Popen] = []

    class Gevolgd(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            kinderen.append(self)

    async def scenario() -> float:
        taak = asyncio.ensure_future(afbreken.in_thread(sandbox.voer_uit, _OPLOOP, pd.DataFrame({"N": [1]}), {}))
        await asyncio.sleep(1.0)
        start = time.monotonic()
        taak.cancel()
        with pytest.raises(asyncio.CancelledError):
            await taak
        return start

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sandbox.subprocess, "Popen", Gevolgd)
        start = time.monotonic()
        asyncio.run(scenario())  # wacht op de thread van de tool
        totaal = time.monotonic() - start

    assert len(kinderen) == 1 and kinderen[0].returncode is not None
    assert totaal < 3, f"het kindproces rekende {totaal:.1f} s door"


def test_zonder_afbreeksignaal_blijft_de_tijdgrens_van_de_sandbox_gelden(monkeypatch):
    monkeypatch.setattr(sandbox, "TIMEOUT_SECONDS", 1)

    uitkomst = sandbox.voer_uit(_OPLOOP, pd.DataFrame({"N": [1]}), {})

    assert uitkomst.fout is not None and "langer dan 1 seconden" in uitkomst.fout


def test_het_afbreeksignaal_is_er_alleen_binnen_een_toolaanroep():
    assert afbreken.gevraagd() is False

    async def scenario() -> list[bool]:
        gezien: list[bool] = []
        gestart = threading.Event()

        def tool() -> None:
            gestart.set()
            while not afbreken.gevraagd():
                time.sleep(0.01)
            gezien.append(True)

        taak = asyncio.ensure_future(afbreken.in_thread(tool))
        while not gestart.is_set():
            await asyncio.sleep(0.01)
        taak.cancel()
        with pytest.raises(asyncio.CancelledError):
            await taak
        return gezien

    assert asyncio.run(scenario()) == [True]
    assert afbreken.gevraagd() is False


def test_een_tool_die_klaar_is_voor_de_stop_houdt_zijn_uitkomst():
    assert asyncio.run(afbreken.in_thread(lambda: "klaar")) == "klaar"
