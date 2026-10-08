"""Harde en zachte controleproblemen (#207, besluit optie C)."""

import asyncio

import pytest

from agent import report
from agent.loop import LoopResult
from agent.probleem import Probleem, hard, harde, meldingen, niet_gecontroleerd, uitkomsten, veilig
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


def verkeerde_kpi_periodes():
    return ["2023/24 valt buiten de KPI."]


def test_hard_behoudt_de_naam_van_de_controle():
    """CH-01: het HERKANSING-log noemde bij een harde controle None in plaats van haar naam."""
    (p,) = hard(veilig(verkeerde_kpi_periodes))
    assert p.hard and p.controle == "verkeerde_kpi_periodes"


def test_uitkomsten_noemen_elke_controle_ook_zonder_bevinding():
    """CH-01: per antwoord loggen welke controles draaiden en met welke uitkomst."""
    (streng,) = hard(veilig(verkeerde_kpi_periodes))
    zacht = Probleem("Label klopt niet.")
    zacht.controle = "verkeerde_dimensielabels"
    stuk = niet_gecontroleerd("abc123")
    stuk.controle = "metatekst"
    namen = ["ongedekte_getallen", "verkeerde_kpi_periodes", "verkeerde_dimensielabels", "metatekst"]
    assert uitkomsten(namen, [streng, zacht, stuk]) == {
        "ongedekte_getallen": "ok",
        "verkeerde_kpi_periodes": "hard",
        "verkeerde_dimensielabels": "zacht",
        "metatekst": "niet gecontroleerd",
    }


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
