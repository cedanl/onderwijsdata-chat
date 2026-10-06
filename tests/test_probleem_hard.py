"""Harde en zachte controleproblemen (#207, besluit optie C)."""

import asyncio

import pytest

from agent import report
from agent.loop import LoopResult
from agent.probleem import Probleem, hard, harde, meldingen
from agent.report import ReportSpec
from agent.report_checks import report_problems


def test_hard_behoudt_tekst_en_melding():
    (p,) = hard([Probleem("2025/26 staat niet in de selectie.", "Selecteer 2025.")])
    assert p == "2025/26 staat niet in de selectie. Selecteer 2025."
    assert p.melding == "2025/26 staat niet in de selectie."
    assert p.hard


def test_hard_markeert_ook_een_gewone_str():
    (p,) = hard(["kenmerk hoort bij een andere instelling"])
    assert p.hard and p.melding == "kenmerk hoort bij een andere instelling"


def test_harde_filtert_alleen_harde_problemen():
    zacht = Probleem("Label klopt niet.")
    (streng,) = hard([Probleem("6.340 staat niet in de data.")])
    assert harde([zacht, "los", streng]) == [streng]
    assert meldingen([zacht, streng]) == ["Label klopt niet.", "6.340 staat niet in de data."]


# ── Rapport: alleen een hard probleem houdt het tegen ────────────────────────


def _rapport(monkeypatch, problemen: list[str]) -> list[dict]:
    async def loop(*args, **kwargs):
        return LoopResult(text='{"title": "T", "conclusie": "C"}', problems=problemen)

    monkeypatch.setattr(report, "build_dataset_context", lambda session: {"datasets": [{"data_key": "k"}]})
    monkeypatch.setattr(report, "_build_system_prompt", lambda context: "")
    monkeypatch.setattr(report, "tool_loop", loop)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(report.generate({}, emit, stop_event=asyncio.Event()))
    return events


def test_rapport_met_alleen_een_zacht_probleem_komt_er_met_waarschuwing(monkeypatch):
    events = _rapport(monkeypatch, [Probleem("De tekst verwijst naar 'resource 3'.", "Noem het bestand.")])
    [toast] = [e for e in events if e["type"] == "toast"]
    assert toast["level"] == "warning"
    assert "resource 3" in toast["message"] and "Noem" not in toast["message"]


def test_rapport_met_een_hard_probleem_wordt_geweigerd(monkeypatch):
    with pytest.raises(ValueError, match=r"6\.340"):
        _rapport(monkeypatch, [*hard(["6.340 staat niet in de opgehaalde data."]), "zacht"])


def test_report_checks_markeren_een_ongedekt_getal_als_hard():
    spec = ReportSpec(conclusie="Er waren 6.340 studenten.", beantwoordt=["aantal"])
    problemen = report_problems(spec, [], ['{"rijen": [{"AANTAL": 5943}]}'])
    assert harde(problemen) and all("6.340" in p for p in harde(problemen))
