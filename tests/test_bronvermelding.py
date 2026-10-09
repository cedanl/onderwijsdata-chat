"""De bronnen onder een dataantwoord komen uit de toolstappen, niet uit de modeltekst (#416, CH-09).

Vijf keer dezelfde vraag gaf de ene keer één bron, de andere keer twee, met een eigen titel of
zonder periode. De app zet de lijst nu zelf onder het antwoord; de eigen Bronnen-sectie van het
model vervalt, net als zijn Definities bij een teldefinitie uit de bron (#402).
"""

import asyncio
import importlib
import json
import time

import pandas as pd
import pytest

from agent.bronvermelding import bronnen_van, zonder_eigen_bronnen
from agent.probleem import INGEHOUDEN
from agent.stream import StreamResult
from agent.vaste_antwoorden import WEIGER_ANTWOORD
from tools import store
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_TITELS = {"p01hoinges": "Ingeschrevenen hoger onderwijs", "85423NED": "Hoger onderwijs; ingeschrevenen"}

_UWV = json.dumps(
    {
        "bron": "UWV Open Match",
        "dataset": "uwv-open-match-data",
        "peildatum": "mei 2023",
        "provincie": "Gelderland",
        "totaal_vacatures": 23574,
    }
)
_ROA = json.dumps(
    {
        "bron": "ROA, AIS tot 2030",
        "dataset": "ais2030",
        "versie": "v20251218",
        "regio": "provincie Gelderland",
        "prognose_tot_2030": {"Bachelor": {"verwachte baanopeningen tot 2030": {"aantal": 435600}}},
    }
)


@pytest.fixture(autouse=True)
def _data(monkeypatch):
    monkeypatch.setattr("agent.selectie.bron_titel", lambda dataset: _TITELS.get(dataset, dataset))
    store.put(
        "duo:p01hoinges:0",
        pd.DataFrame({"STUDIEJAAR": [2019, 2023], "AANTAL": [26000, 26370]}),
        KeyMeta(bron="duo", dataset="p01hoinges", schooljaren=(2019, 2020, 2021, 2022, 2023)),
    )
    store.derive("duo:p01hoinges:0", "duo:p01hoinges:0:sel", pd.DataFrame({"AANTAL": [26370]}), schooljaren=(2023,))
    store.put("cbs:85423NED", pd.DataFrame({"AANTAL": [341720]}), KeyMeta(bron="cbs", dataset="85423NED"))


def _stap(tool: str, **velden) -> tuple[str, str]:
    return tool, json.dumps(velden)


_DUO = "DUO · Ingeschrevenen hoger onderwijs, 2019/20 t/m 2023/24 (p01hoinges)"
_CBS = "CBS · Hoger onderwijs; ingeschrevenen (85423NED)"


def test_een_geladen_dataset_is_een_bron_met_periode_en_id():
    assert bronnen_van([_stap("get_duo_data", data_key="duo:p01hoinges:0")]) == [_DUO]


def test_een_selectie_noemt_de_geladen_dataset_een_keer():
    """De selectie, een KPI en een analyse op dezelfde laadkey geven samen één bron."""
    steps = [
        _stap("get_duo_data", data_key="duo:p01hoinges:0"),
        _stap("query_data", data_key="duo:p01hoinges:0:sel", rijen=[{"AANTAL": 26370}]),
        _stap("compute_kpi", label="Groei", raw=370, bron={"data_key": "duo:p01hoinges:0:sel", "metric": "delta"}),
        _stap("run_analysis", gelezen=["duo:p01hoinges:0:sel"], resultaat=26370),
    ]
    assert bronnen_van(steps) == [_DUO]


def test_in_volgorde_van_eerste_gebruik():
    steps = [
        _stap("get_cbs_data", data_key="cbs:85423NED"),
        _stap("query_data", data_key="duo:p01hoinges:0:sel"),
        _stap("query_data", data_key="cbs:85423NED"),
    ]
    assert bronnen_van(steps) == [_CBS, _DUO]


def test_uwv_en_roa_met_de_bron_van_hun_citatie():
    steps = [("get_uwv_vacatures", _UWV), ("get_roa_benchmark", _ROA), ("get_uwv_vacatures", _UWV)]
    assert bronnen_van(steps) == ["UWV Open Match, mei 2023", "ROA, AIS tot 2030 (v20251218)"]


def test_rio_register_per_instelling_met_peildatum():
    """get_rio_instelling laadt niets in de store; zonder deze regel had een RIO-antwoord geen bronnen meer."""
    kop = {"bron": "RIO", "catalogus_titel": "RIO erkenningen", "peildatum": "2026-10-09", "gezocht": "Mondriaan"}
    steps = [("get_rio_instelling", json.dumps({**kop, "status": "meerdere", "kandidaten": []}))]
    assert bronnen_van(steps) == ["RIO erkenningen, peildatum 2026-10-09"]
    titel = {**kop, "catalogus_titel": "erkenningen"}
    assert bronnen_van([("get_rio_instelling", json.dumps(titel))]) == ["RIO · erkenningen, peildatum 2026-10-09"]
    assert bronnen_van([("get_rio_instelling", "Fout: RIO is niet bereikbaar.")]) == []


def test_zonder_gelezen_data_geen_bronnen():
    steps = [
        _stap("search_catalog", resultaten=[{"id": "p01hoinges"}]),
        _stap("dataset_details", dataset_id="p01hoinges"),
        ("query_data", "Fout: onbekende data_key"),
        _stap("run_analysis", bron=None, resultaat=55555),
    ]
    assert bronnen_van(steps) == []
    assert bronnen_van([]) == []


def test_een_onbekende_key_wordt_geen_bron():
    """De key zelf hoort niet voor de gebruiker (CH-30); zonder metadata is er niets te noemen."""
    assert bronnen_van([_stap("query_data", data_key="duo:weg:0")]) == []


def test_zonder_catalogustitel_staat_het_id_er_een_keer():
    store.put("rio:onbekend", pd.DataFrame({"x": [1]}), KeyMeta(bron="rio", dataset="onbekend"))
    assert bronnen_van([_stap("get_rio_data", data_key="rio:onbekend")]) == ["RIO · onbekend"]


def test_dezelfde_stappen_geven_vijf_keer_dezelfde_lijst():
    steps = [
        _stap("get_duo_data", data_key="duo:p01hoinges:0"),
        _stap("get_cbs_data", data_key="cbs:85423NED"),
        ("get_uwv_vacatures", _UWV),
    ]
    runs = [bronnen_van(steps) for _ in range(5)]
    assert all(run == runs[0] for run in runs)
    assert runs[0] == [_DUO, _CBS, "UWV Open Match, mei 2023"]


# --- de eigen Bronnen-sectie van het model ---

_ANTWOORD = "Het hoger onderwijs had 26.370 ingeschrevenen in 2023/24."
_DEFINITIES = "**Definities**\n- **Ingeschrevenen**: hoofdinschrijvingen op 1 oktober."


@pytest.mark.parametrize(
    "sectie",
    [
        "**Bronnen**\n- DUO — *Ingeschrevenen hoger onderwijs* (**p01hoinges**)\n- CBS 85423NED",
        "**Bronnen:** DUO p01hoinges, CBS 85423NED",
        "**Bronnen**:\n\n- DUO p01hoinges\n\n- CBS 85423NED",
        "**Bronnen**\n1. DUO p01hoinges\n2. CBS 85423NED",
        "**Bronnen**\n- DUO — *Ingeschrevenen hoger onderwijs*\n  resource *Ingeschrevenen*\n- CBS 85423NED",
        "**Bronnen**\nDUO p01hoinges\nCBS 85423NED",
    ],
)
def test_eigen_bronnen_vervallen_als_de_app_ze_geeft(sectie):
    assert zonder_eigen_bronnen(f"{_ANTWOORD}\n\n{sectie}", [_DUO]) == _ANTWOORD
    assert zonder_eigen_bronnen(f"{_ANTWOORD}\n\n{sectie}\n", [_DUO]) == _ANTWOORD


def test_definities_en_slotzin_na_de_bronnen_blijven_staan():
    tekst = f"{_ANTWOORD}\n\n**Bronnen**\n- DUO p01hoinges\n\n{_DEFINITIES}\n\nDe cijfers zijn definitief."
    assert zonder_eigen_bronnen(tekst, [_DUO]) == f"{_ANTWOORD}\n\n{_DEFINITIES}\n\nDe cijfers zijn definitief."


@pytest.mark.parametrize("sectie", ["**Bronnen**\n- DUO p01hoinges", "**Bronnen:** DUO p01hoinges"])
def test_een_kanttekening_direct_onder_de_bronnen_blijft_staan(sectie):
    """Een regel die tegen de lijst aan plakt, hoort er niet bij: de kanttekening blijft een eigen alinea."""
    kanttekening = "Let op: de cijfers over 2024 zijn voorlopig."
    tekst = f"{_ANTWOORD}\n\n{sectie}\n{kanttekening}"
    assert zonder_eigen_bronnen(tekst, [_DUO]) == f"{_ANTWOORD}\n\n{kanttekening}"


def test_een_genummerde_lijst_na_de_bronnen_blijft_staan():
    """Na een lege regel loopt de sectie alleen door met items van dezelfde soort."""
    vervolg = "1. Vergelijk met het mbo.\n2. Kijk per instelling."
    tekst = f"{_ANTWOORD}\n\n**Bronnen**\n- DUO p01hoinges\n\n{vervolg}"
    assert zonder_eigen_bronnen(tekst, [_DUO]) == f"{_ANTWOORD}\n\n{vervolg}"


_VIJANDIG = {
    "lege regels zonder sectie": "a" + "\n" * 50_000 + "b",
    "lege regels voor de sectie": "a" + "\n" * 50_000 + "**Bronnen**\n- x",
    "lege regels in de sectie": "a\n\n**Bronnen**\n- x" + "\n" * 50_000 + "b",
    "lege regels na een kale kop": "**Bronnen**" + "\n" * 50_000 + "b",
    "spaties en lege regels": "a" + " \n" * 25_000 + "**Bronnen**\n- x",
    "veel koppen": "**Bronnen**\n" * 20_000,
    "veel lijstitems": "**Bronnen**\n" + "- x\n\n" * 20_000,
}


@pytest.mark.parametrize("tekst", list(_VIJANDIG.values()), ids=list(_VIJANDIG))
def test_vijandige_invoer_blijft_snel(tekst):
    """zonder_eigen_bronnen draait synchroon in run(): traag zoeken bevriest elke sessie op de worker."""
    start = time.perf_counter()
    zonder_eigen_bronnen(tekst, [_DUO])
    assert time.perf_counter() - start < 0.5


def test_lange_reeks_lege_regels_voor_de_sectie():
    assert zonder_eigen_bronnen("a" + "\n" * 50_000 + "**Bronnen**\n- x", [_DUO]) == "a"


def test_eigen_bronnen_blijven_zonder_bronnen_uit_code():
    tekst = f"{_ANTWOORD}\n\n**Bronnen**\n- DUO p01hoinges"
    assert zonder_eigen_bronnen(tekst, []) == tekst


def test_het_woord_bronnen_in_de_lopende_tekst_blijft():
    tekst = "Zie de **Bronnen** hieronder. Bronnen: p01hoinges en CBS 85423NED."
    assert zonder_eigen_bronnen(tekst, [_DUO]) == tekst


# --- message_end: altijd een lijst, leeg bij een vast antwoord ---

_LAAD = {"id": "l", "name": "get_duo_data", "arguments": '{"dataset_id": "p01hoinges"}'}
_RIJEN = json.dumps({"data_key": "duo:p01hoinges:0:sel", "rijen": [{"AANTAL": 26370}]})


_VRAAG = "Hoeveel ingeschrevenen had het hoger onderwijs in 2023/24?"


def _slot(monkeypatch, steps: list[StreamResult], vraag: str = _VRAAG) -> dict:
    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    async def fake_execute_tool(call, emit):
        return _RIJEN, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(run_module.run([{"role": "user", "content": vraag}], {}, emit, asyncio.Event(), model="openai/gpt-4o"))
    return next(e for e in reversed(events) if e["type"] == "message_end")


def test_dataantwoord_krijgt_de_bronnen_en_verliest_de_eigen_sectie(monkeypatch):
    antwoord = f"{_ANTWOORD}\n\n**Bronnen**\n- DUO — *Ingeschrevenen* (**p01hoinges**)"
    einde = _slot(monkeypatch, [StreamResult(text="", tool_calls=[_LAAD]), StreamResult(text=antwoord, tool_calls=[])])

    assert einde["bronnen"] == [_DUO]
    assert "**Bronnen**" not in einde["content"] and einde["content"].startswith(_ANTWOORD)


def test_weigering_heeft_lege_bronnen(monkeypatch):
    weigering = [StreamResult(text="Dat valt buiten mijn domein.", tool_calls=[])]
    einde = _slot(monkeypatch, weigering, vraag="Wie wint het WK?")

    assert einde["content"] == WEIGER_ANTWOORD
    assert einde["bronnen"] == []


def test_ingehouden_antwoord_heeft_lege_bronnen(monkeypatch):
    einde = _slot(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_LAAD]),
            StreamResult(text="Het waren 99.999 ingeschrevenen.", tool_calls=[]),
            StreamResult(text="Toch 99.999.", tool_calls=[]),
        ],
    )

    assert einde["content"] == INGEHOUDEN
    assert einde["bronnen"] == []


def test_leeg_antwoord_heeft_lege_bronnen(monkeypatch):
    einde = _slot(monkeypatch, [StreamResult(text="", tool_calls=[_LAAD]), StreamResult(text="", tool_calls=[])])

    assert einde["content"] == run_module.LEEG_ANTWOORD
    assert einde["bronnen"] == []


def test_vast_antwoord_over_min_een_heeft_lege_bronnen(monkeypatch):
    einde = _slot(monkeypatch, [], vraag="Wat betekent -1 in DUO-data?")

    assert einde["bronnen"] == []
