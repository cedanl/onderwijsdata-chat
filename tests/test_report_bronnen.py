"""Bronnen, definities en dataversie van een rapport volgen wat het rapport gebruikte (#738).

Een gebruiker zag bij twee grafieken uit CBS 83285NED ook CBS 83282NED en twee DUO-tabellen in het
blok Bronnen, de definities en de dataversie: die waren eerder in het gesprek opgevraagd, niet in het
rapport gebruikt.
"""

import asyncio
import json

import pandas as pd
import plotly.graph_objects as go
import pytest

from agent import report
from agent.loop import LoopResult, ToolCall
from agent.report_bronnen import gebruikte_datasets
from tools import store
from tools.schemas import TOOL_COMPUTE_KPI, TOOL_CREATE_PLOT, TOOL_GET_CBS_DATA, TOOL_GET_DUO_DATA, TOOL_QUERY_DATA
from tools.store import KeyMeta

_GETOOND = "cbs:83285NED"
_OPGEVRAAGD = "cbs:83282NED"
_DUO = "duo:p01hoinges:3"
_TELDEFINITIE = "Een persoon telt één keer in het domein hoger onderwijs."

_ANTWOORD = json.dumps(
    {
        "onderzoeksvraag": "Hoe ontwikkelt het bachelorrendement in het wo zich?",
        "beantwoordt": ["Het bachelorrendement per startjaar"],
        "beantwoordt_niet": ["De oorzaken"],
        "visualisaties": [{"titel": "Bachelorrendement per startjaar", "toelichting": "Het rendement stijgt."}],
        "conclusie": "Het bachelorrendement stijgt over de startjaren.",
    }
)


@pytest.fixture
def sessie():
    store.put(
        _GETOOND, pd.DataFrame({"Startjaar": ["2018", "2019"], "Rendement": [41.0, 43.5]}), KeyMeta("cbs", "83285NED")
    )
    store.put(_OPGEVRAAGD, pd.DataFrame({"Startjaar": ["2018"], "Diploma": [12000]}), KeyMeta("cbs", "83282NED"))
    store.put(
        _DUO,
        pd.DataFrame({"INSTELLINGSNAAM": ["UU"], "AANTAL": [23456]}),
        KeyMeta("duo", "p01hoinges", resource=3, teldefinitie=_TELDEFINITIE),
    )
    laad = {
        _GETOOND: {"name": TOOL_GET_CBS_DATA, "arguments": {"dataset_id": "83285NED"}},
        _OPGEVRAAGD: {"name": TOOL_GET_CBS_DATA, "arguments": {"dataset_id": "83282NED"}},
        _DUO: {"name": TOOL_GET_DUO_DATA, "arguments": {"dataset_id": "p01hoinges", "resource": 3}},
    }
    return {
        "data_keys": list(laad),
        "data_provenance": laad,
        "turns": [{"question": "Hoe ontwikkelt het bachelorrendement in het wo zich?"}],
    }


def _plot(data_key: str) -> tuple[ToolCall, str, go.Figure]:
    args = {"data_key": data_key, "x": "Startjaar", "y": "Rendement", "chart_type": "line"}
    call = ToolCall(id="p", name=TOOL_CREATE_PLOT, arguments=json.dumps(args), args=args)
    return call, "Lijngrafiek 'Bachelorrendement' aangemaakt (2 datapunten).", go.Figure(go.Scatter(x=[1, 2], y=[1, 2]))


def _query(data_key: str, resultaat: dict) -> tuple[ToolCall, str, None]:
    args = {"data_key": data_key}
    call = ToolCall(id="q", name=TOOL_QUERY_DATA, arguments=json.dumps(args), args=args)
    return call, json.dumps(resultaat), None


def _rapport(sessie, monkeypatch, stappen, antwoord: str = _ANTWOORD):
    async def loop(messages, *, on_tool_result, **_):
        for stap in stappen:
            await on_tool_result(*stap)
        return LoopResult(text=antwoord)

    async def stil(_event):
        pass

    monkeypatch.setattr(report, "tool_loop", loop)
    return asyncio.run(report.generate(sessie, stil))


def _datasets_in(spec) -> set[str]:
    return {d["dataset"] for d in spec.manifest["data_as_of"]}


def test_een_bron_die_het_gesprek_opvroeg_maar_het_rapport_niet_gebruikte_staat_er_niet_in(sessie, monkeypatch):
    spec = _rapport(sessie, monkeypatch, [_plot(_GETOOND)])

    assert len(spec.bronnen) == 1 and "83285NED" in spec.bronnen[0]
    assert not any("83282NED" in b or "p01hoinges" in b for b in spec.bronnen)
    assert _datasets_in(spec) == {"83285NED"}
    assert spec.definities == []


def test_de_definitie_en_dataversie_van_een_gebruikte_bron_blijven(sessie, monkeypatch):
    spec = _rapport(sessie, monkeypatch, [_plot(_GETOOND), _query(_DUO, {"data_key": _DUO, "rijen": []})])

    assert any("p01hoinges" in b for b in spec.bronnen)
    assert not any("83282NED" in b for b in spec.bronnen)
    assert _datasets_in(spec) == {"83285NED", "p01hoinges"}
    assert spec.definities == [{"begrip": "Telling (p01hoinges)", "definitie": _TELDEFINITIE}]


def test_een_selectie_uit_het_rapport_telt_voor_haar_laadkey(sessie, monkeypatch):
    afgeleid = f"{_DUO}:ab12cd34"
    store.derive(_DUO, afgeleid, pd.DataFrame({"INSTELLINGSNAAM": ["UU"], "AANTAL": [23456]}))
    spec = _rapport(sessie, monkeypatch, [_query(afgeleid, {"data_key": afgeleid, "rijen": []})])

    assert [b for b in spec.bronnen if "p01hoinges" in b] and not [b for b in spec.bronnen if "NED" in b]
    assert _datasets_in(spec) == {"p01hoinges"}


def test_een_grafiek_die_niet_in_het_rapport_komt_telt_niet(sessie, monkeypatch):
    stappen = [_plot(_GETOOND), _plot(_GETOOND), _plot(_OPGEVRAAGD)]
    spec = _rapport(sessie, monkeypatch, stappen)

    assert len(spec.visualisaties) == report._MAX_VISUALISATIES
    assert _datasets_in(spec) == {"83285NED"}


def test_een_berekening_uit_het_gesprek_die_het_rapport_citeert_telt_mee(sessie, monkeypatch):
    kpi = {"waarde": 23456, "bron": {"data_key": _DUO}}
    sessie["rekenbewijs"] = [{"tool": TOOL_COMPUTE_KPI, "argumenten": {"data_key": _DUO}, "resultaat": json.dumps(kpi)}]
    geciteerd = json.dumps({**json.loads(_ANTWOORD), "conclusie": "De UU telt 23.456 ingeschrevenen."})

    assert _datasets_in(_rapport(sessie, monkeypatch, [_plot(_GETOOND)], geciteerd)) == {"83285NED", "p01hoinges"}
    assert _datasets_in(_rapport(sessie, monkeypatch, [_plot(_GETOOND)])) == {"83285NED"}


def test_zonder_herleidbare_key_blijven_de_datasets_van_het_gesprek():
    datasets = [{"data_key": _GETOOND}, {"data_key": _OPGEVRAAGD}]
    assert gebruikte_datasets(datasets, [None, "bestaat:niet"], [], "") == datasets
