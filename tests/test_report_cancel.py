"""Een gestopt rapport is geannuleerd, geen half rapport en geen fout (#339)."""

import asyncio

import pytest

from agent import report
from agent.loop import LoopResult
from routes import chat


def test_een_gestopte_rapportrun_geeft_geen_rapport(monkeypatch):
    async def gestopt(*args, **kwargs):
        return LoopResult(text="", aborted="tools")

    monkeypatch.setattr(report, "build_dataset_context", lambda session: {"datasets": [{"data_key": "k"}]})
    monkeypatch.setattr(report, "_build_system_prompt", lambda context: "")
    monkeypatch.setattr(report, "tool_loop", gestopt)

    async def emit(event):
        pass

    with pytest.raises(report.RapportGeannuleerd):
        asyncio.run(report.generate({}, emit, stop_event=asyncio.Event()))


def test_annuleren_meldt_report_cancelled_en_geen_fout(monkeypatch):
    async def geannuleerd(*args, **kwargs):
        raise report.RapportGeannuleerd

    monkeypatch.setattr(chat, "generate_report_spec", geannuleerd)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(chat._generate_report({"username": "u"}, emit, model=None))
    assert [e["type"] for e in events] == ["report_generating", "report_cancelled"]


def _afgebroken_rapport(monkeypatch, emit):
    """Een rapportrun die hangt tot een reset of ander gesprek haar taak afbreekt."""

    async def hangt(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(chat, "generate_report_spec", hangt)

    async def run():
        taak = asyncio.create_task(chat._generate_report({"username": "u"}, emit, model=None))
        await asyncio.sleep(0)
        taak.cancel()
        with pytest.raises(asyncio.CancelledError):
            await taak

    asyncio.run(run())


def test_afgebroken_rapporttaak_meldt_report_cancelled(monkeypatch):
    # #417: een reset breekt de taak af zonder eindbericht; de frontend wachtte dan tot de time-out.
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    _afgebroken_rapport(monkeypatch, emit)
    assert [e["type"] for e in events] == ["report_generating", "report_cancelled"]


def test_afbreken_blijft_afbreken_als_de_verbinding_al_weg_is(monkeypatch):
    async def emit(event):
        if event["type"] != "report_generating":
            raise RuntimeError("socket gesloten")

    _afgebroken_rapport(monkeypatch, emit)
