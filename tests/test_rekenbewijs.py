"""Een in de chat berekende KPI is bewijs in de rapportfase (#397, testaudit L7, UX N9).

Na een geslaagde compute_kpi (36.201) weigerde het rapport: 'Deze getallen staan niet in de
opgehaalde data: 36.201.' De rapportcontrole kende alleen zijn eigen toolresultaten en de
datasetcontext, niet wat het gesprek al had berekend.
"""

import asyncio
import json
from types import SimpleNamespace

from agent import report
from agent.report import ReportSpec
from agent.report_checks import report_problems
from agent.session_data import record_rekenbewijs, rekenbewijs

_KPI = json.dumps(
    {
        "label": "Hoofdinschrijvingen HU 2024",
        "value": "36.201",
        "raw": 36201,
        "bron": {"data_key": "duo:p01hoinges:0:ab12", "kolom": "AANTAL", "metric": "sum"},
    }
)
_ANALYSE = json.dumps({"data_key": "analyse:1", "resultaat": {"daling": 43480}})
_KPI_CALL = {"name": "compute_kpi", "arguments": {"data_key": "duo:p01hoinges:0:ab12", "metric": "sum"}}


def _spec(conclusie: str) -> ReportSpec:
    return ReportSpec(
        title="HU",
        onderzoeksvraag="Hoeveel hoofdinschrijvingen heeft de HU?",
        beantwoordt=["Hoofdinschrijvingen HU"],
        conclusie=conclusie,
    )


def test_een_geslaagde_kpi_wordt_bewaard_met_zijn_aanroep():
    session: dict = {}
    record_rekenbewijs(session, _KPI, _KPI_CALL)

    assert rekenbewijs(session) == [{"tool": "compute_kpi", "argumenten": _KPI_CALL["arguments"], "resultaat": _KPI}]


def test_run_analysis_is_ook_rekenbewijs():
    session: dict = {}
    record_rekenbewijs(session, _ANALYSE, {"name": "run_analysis", "arguments": {}})

    assert [b["tool"] for b in rekenbewijs(session)] == ["run_analysis"]


def test_query_data_is_alleen_met_aggregatie_rekenbewijs():
    session: dict = {}
    rijen = json.dumps({"data_key": "q:1", "rijen": [{"AANTAL": 5}]})
    record_rekenbewijs(session, rijen, {"name": "query_data", "arguments": {"filters": {"JAAR": 2024}}})
    record_rekenbewijs(session, rijen, {"name": "query_data", "arguments": {"aggregate": {"AANTAL": "sum"}}})

    assert len(rekenbewijs(session)) == 1


def test_fouten_en_laadtools_zijn_geen_rekenbewijs():
    session: dict = {}
    record_rekenbewijs(session, json.dumps({"fout": "E_KOLOM: kolom bestaat niet"}), _KPI_CALL)
    record_rekenbewijs(session, json.dumps({"data_key": "duo:p01hoinges:0"}), {"name": "get_duo_data"})
    record_rekenbewijs(session, "geen json", _KPI_CALL)

    assert rekenbewijs(session) == []


def test_het_bewijs_blijft_begrensd():
    session: dict = {}
    for i in range(100):
        record_rekenbewijs(session, json.dumps({"raw": i}), _KPI_CALL)

    bewijs = rekenbewijs(session)
    assert len(bewijs) < 100
    assert json.loads(bewijs[-1]["resultaat"]) == {"raw": 99}


def test_rapport_mag_de_kpi_uit_het_gesprek_noemen():
    assert report_problems(_spec("De HU had 36.201 hoofdinschrijvingen."), [], [_KPI]) == []


def test_een_ander_getal_blijft_geweigerd():
    [probleem] = report_problems(_spec("De HU had 36.210 hoofdinschrijvingen."), [], [_KPI])

    assert "36.210" in probleem


def test_de_rapportfase_krijgt_het_rekenbewijs_van_de_sessie(monkeypatch):
    session: dict = {}
    record_rekenbewijs(session, _KPI, _KPI_CALL)
    gezien: dict = {}

    def bronnen_vastleggen(spec, figures, sources):
        gezien["sources"] = sources
        return []

    async def eenmaal_controleren(messages, *, check, **_):
        gezien["prompt"] = messages[0]["content"]
        check("{}", [])
        return SimpleNamespace(aborted=None, partial_error=None, problems=[], text="{}")

    async def emit(_):
        pass

    monkeypatch.setattr(
        report, "build_dataset_context", lambda s: {"datasets": [{"data_key": "k", "row_count": 1, "columns": []}]}
    )
    monkeypatch.setattr(report, "report_problems", bronnen_vastleggen)
    monkeypatch.setattr(report, "tool_loop", eenmaal_controleren)
    monkeypatch.setattr(report, "_parse_spec_from_response", lambda *a: _spec(""))

    asyncio.run(report.generate(session, emit))

    assert _KPI in gezien["sources"]
    assert "36.201" in gezien["prompt"] and "compute_kpi" in gezien["prompt"]
