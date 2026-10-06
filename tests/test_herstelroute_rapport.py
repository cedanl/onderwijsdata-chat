"""De herstelroute uit de testaudit als regressiescenario (#397, L7).

Weigering → herstelvraag → rapport, in één sessie: het rapport noemt een som die
nergens in de rijen staat en wordt geweigerd; de gebruiker vraagt de chat die som te
berekenen (echte compute_kpi); daarna neemt het rapport hetzelfde getal wel op.
Alleen het model is nagespeeld; toolloop, tool, sessiebewijs en controles zijn echt.
"""

import asyncio
import importlib
import json

import pandas as pd
import pytest

from agent import report
from agent.stream import StreamResult
from tools import store
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_KEY = "duo:p01hoinges:0:hu"
_KPI = {
    "id": "k1",
    "name": "compute_kpi",
    "arguments": json.dumps({"data_key": _KEY, "value_column": "AANTAL", "metric": "sum", "label": "HU"}),
}


@pytest.fixture(autouse=True)
def _hu_in_store():
    store.clear()
    store.put(
        _KEY,
        pd.DataFrame({"OPLEIDINGSVORM": ["VT", "DT"], "AANTAL": [30101, 6100]}),
        KeyMeta(bron="duo", dataset="p01hoinges"),
    )
    yield
    store.clear()


def _model(monkeypatch, stappen: list[StreamResult]):
    async def completion(*args, **kwargs):
        return object()

    async def accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", accumulate)


def _rapport(conclusie: str) -> StreamResult:
    spec = {"title": "HU", "onderzoeksvraag": "Inschrijvingen HU", "beantwoordt": ["Totaal"], "conclusie": conclusie}
    return StreamResult(text=json.dumps(spec), tool_calls=[])


async def _stil(_event):
    pass


def _genereer(session: dict):
    return asyncio.run(report.generate(session, _stil, model="openai/gpt-4o"))


def test_weigering_herstelvraag_rapport(monkeypatch):
    session: dict = {"data_keys": [_KEY]}
    zin = "De HU had 36.201 inschrijvingen."

    _model(monkeypatch, [_rapport(zin), _rapport(zin)])
    with pytest.raises(ValueError, match=r"36\.201"):
        _genereer(session)

    _model(monkeypatch, [StreamResult(text="", tool_calls=[_KPI]), StreamResult(text=zin, tool_calls=[])])
    antwoord = asyncio.run(
        run_module.run(
            [{"role": "user", "content": "Bereken het totaal aantal inschrijvingen van de HU."}],
            session,
            _stil,
            asyncio.Event(),
            model="openai/gpt-4o",
        )
    )
    assert antwoord == zin

    _model(monkeypatch, [_rapport(zin)])
    assert _genereer(session).conclusie == zin


def test_na_de_herstelvraag_blijft_een_ander_getal_geweigerd(monkeypatch):
    session: dict = {"data_keys": [_KEY]}
    _model(monkeypatch, [StreamResult(text="", tool_calls=[_KPI]), StreamResult(text="Totaal 36.201.", tool_calls=[])])
    asyncio.run(run_module.run([{"role": "user", "content": "Totaal?"}], session, _stil, asyncio.Event()))

    _model(monkeypatch, [_rapport("De HU had 36.210 inschrijvingen.")] * 2)
    with pytest.raises(ValueError, match=r"36\.210"):
        _genereer(session)
