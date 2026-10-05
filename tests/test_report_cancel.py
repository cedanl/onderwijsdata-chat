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
