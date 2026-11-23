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
from agent.report_bronnen import bewijsbronnen
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


# ── De mbo-indicatoren: een toolresultaat zonder tabel in de store is zelf het bewijs (#1077) ──────────────────────

_MBO = json.dumps(
    {
        "dataset": "duo:mbo_indicatoren",
        "instelling": {"naam": "ROC Midden Nederland", "instellingscode": "25LH"},
        "jaarresultaat": [
            {"schooljaar": "2024/25", "instelling": 70.1, "vergelijkingsgroep": 71.8, "verschil_procentpunt": -1.7}
        ],
        "toelichting": "Een lange tekst vóór het diplomaresultaat. " * 50,
        "diplomaresultaat": [
            {"schooljaar": "2024/25", "instelling": 70.6, "vergelijkingsgroep": 72.4, "verschil_procentpunt": -1.8}
        ],
        "bron": {
            "naam": "DUO, Indicatoren per instelling (jaardocument mbo)",
            "url": "https://duo.nl/open_onderwijsdata/images/2026-indicatoren-per-instelling.xlsx",
            "editie": 2026,
            "peildatum": "1 oktober 2025",
        },
    }
)
_MBO_CALL = {"name": "get_mbo_indicatoren", "arguments": {"instelling": "ROC Midden Nederland"}}


def test_get_mbo_indicatoren_is_bewijs_met_het_nummer_van_de_vraag():
    session: dict = {"messages": [{"role": "user", "content": "Hoe doen wij het?"}]}
    record_rekenbewijs(session, _MBO, _MBO_CALL)

    assert rekenbewijs(session) == [
        {"tool": "get_mbo_indicatoren", "argumenten": _MBO_CALL["arguments"], "resultaat": _MBO, "vraag": 1}
    ]


def test_een_melding_van_get_mbo_indicatoren_is_geen_bewijs():
    session: dict = {"messages": [{"role": "user", "content": "Hoe doen wij het?"}]}
    record_rekenbewijs(session, "Onbekende instelling 'X': het register kent deze naam niet.", _MBO_CALL)
    record_rekenbewijs(session, json.dumps({"fout": "E_BRON: onbereikbaar"}), _MBO_CALL)

    assert rekenbewijs(session) == []


def test_een_rapport_mag_de_percentages_uit_get_mbo_indicatoren_noemen():
    conclusie = "Het diplomaresultaat is 70,6% tegen 72,4% bij de roc's; het jaarresultaat 70,1% tegen 71,8%."

    assert report_problems(_spec(conclusie), [], [_MBO]) == []


def test_een_percentage_dat_niet_in_get_mbo_indicatoren_staat_blijft_geweigerd():
    [probleem] = report_problems(_spec("Het diplomaresultaat is 71,6%."), [], [_MBO])

    assert "71,6" in probleem


def test_de_rapportfase_krijgt_de_uitvoer_van_get_mbo_indicatoren_als_bewijs_en_in_de_prompt(monkeypatch):
    session: dict = {"messages": [{"role": "user", "content": "Hoe doen wij het?"}]}
    record_rekenbewijs(session, _MBO, _MBO_CALL)
    gezien: dict = {}

    def bronnen_vastleggen(spec, figures, sources):
        gezien["sources"] = sources
        return []

    async def eenmaal_controleren(messages, *, check, **_):
        gezien["prompt"] = messages[0]["content"]
        check("{}", [])
        return SimpleNamespace(aborted=None, exhausted=False, partial_error=None, problems=[], text="{}")

    async def emit(_):
        pass

    monkeypatch.setattr(
        report, "build_dataset_context", lambda s: {"datasets": [{"data_key": "k", "row_count": 1, "columns": []}]}
    )
    monkeypatch.setattr(report, "report_problems", bronnen_vastleggen)
    monkeypatch.setattr(report, "tool_loop", eenmaal_controleren)
    monkeypatch.setattr(report, "_parse_spec_from_response", lambda *a, **kw: _spec(""))

    asyncio.run(report.generate(session, emit))

    assert _MBO in gezien["sources"]
    # Ook het diplomaresultaat, dat na de eerste 1.500 tekens van de uitvoer staat.
    assert "70.6" in gezien["prompt"] and "get_mbo_indicatoren" in gezien["prompt"]


def test_een_rapport_noemt_de_bron_van_de_mbo_indicatoren_als_het_er_een_getal_uit_citeert():
    citeert = bewijsbronnen(rekenbewijs_van(_MBO), "Het diplomaresultaat is 70,6%.")

    assert citeert == [
        "DUO · Indicatoren per instelling (jaardocument mbo), editie 2026, peildatum 1 oktober 2025",
    ]
    assert bewijsbronnen(rekenbewijs_van(_MBO), "Het rapport noemt geen getal.") == []


def rekenbewijs_van(resultaat: str) -> list[dict]:
    session: dict = {"messages": [{"role": "user", "content": "Hoe doen wij het?"}]}
    record_rekenbewijs(session, resultaat, _MBO_CALL)
    return rekenbewijs(session)


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
        return SimpleNamespace(aborted=None, exhausted=False, partial_error=None, problems=[], text="{}")

    async def emit(_):
        pass

    monkeypatch.setattr(
        report, "build_dataset_context", lambda s: {"datasets": [{"data_key": "k", "row_count": 1, "columns": []}]}
    )
    monkeypatch.setattr(report, "report_problems", bronnen_vastleggen)
    monkeypatch.setattr(report, "tool_loop", eenmaal_controleren)
    monkeypatch.setattr(report, "_parse_spec_from_response", lambda *a, **kw: _spec(""))

    asyncio.run(report.generate(session, emit))

    assert _KPI in gezien["sources"]
    assert "36.201" in gezien["prompt"] and "compute_kpi" in gezien["prompt"]
