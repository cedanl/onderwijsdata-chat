"""De bronnen onder een dataantwoord komen uit de toolstappen, niet uit de modeltekst (#416, CH-09).

Vijf keer dezelfde vraag gaf de ene keer één bron, de andere keer twee, met een eigen titel of
zonder periode. De app zet de lijst nu zelf onder het antwoord; de eigen Bronnen-sectie van het
model vervalt, net als zijn Definities bij een teldefinitie uit de bron (#402).
"""

import asyncio
import importlib
import json
import logging
import time
from unittest.mock import patch

import pandas as pd
import pytest

from agent.bronvermelding import bronlinks_van, bronnen_van, buiten_bronnensectie, zonder_eigen_bronnen
from agent.loop import LoopResult
from agent.probleem import INGEHOUDEN
from agent.stream import StreamResult
from agent.vaste_antwoorden import WEIGER_ANTWOORD
from tools import store
from tools.arbeidsmarkt import DATASET, ROA_ID, UWV_ID
from tools.catalog import documentatie_url
from tools.rio_instelling import ERKENNINGEN
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


def test_een_dataset_met_meer_bestanden_noemt_het_bestand(monkeypatch):
    """#540: drie hbo-bestanden van p01hoinges gaven 34.751, 34.754 en 34.755; de bron noemt het bestand."""
    monkeypatch.setattr("agent.selectie.tabelbestanden", lambda _id: [(0, "geslacht"), (2, "niveau"), (3, "vorm")])
    monkeypatch.setattr(
        "agent.selectie.resource_titel", lambda _id, r: {3: "Ingeschrevenen hbo inclusief opleidingsvorm"}.get(r)
    )
    store.put(
        "duo:p01hoinges:3",
        pd.DataFrame({"STUDIEJAAR": [2023], "AANTAL": [34755]}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=3, schooljaren=(2023,)),
    )
    assert bronnen_van([_stap("get_duo_data", data_key="duo:p01hoinges:3")]) == [
        "DUO · Ingeschrevenen hoger onderwijs, bestand Ingeschrevenen hbo inclusief opleidingsvorm, 2023/24 (p01hoinges)"
    ]


def test_een_dataset_met_een_bestand_noemt_het_niet(monkeypatch):
    monkeypatch.setattr("agent.selectie.tabelbestanden", lambda _id: [(0, "het enige bestand")])
    store.put(
        "duo:p01hoinges:0:enkel",
        pd.DataFrame({"AANTAL": [1]}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=0, schooljaren=(2023,)),
    )
    assert bronnen_van([_stap("get_duo_data", data_key="duo:p01hoinges:0:enkel")]) == [
        "DUO · Ingeschrevenen hoger onderwijs, 2023/24 (p01hoinges)"
    ]


def test_het_bestand_komt_uit_de_echte_catalogus(monkeypatch):
    monkeypatch.undo()  # de catalogustitel en de bestanden van p01hoinges zelf, zonder nep
    store.put(
        "duo:p01hoinges:3:echt",
        pd.DataFrame({"AANTAL": [34755]}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=3, schooljaren=(2023,)),
    )
    [bron] = bronnen_van([_stap("get_duo_data", data_key="duo:p01hoinges:3:echt")])
    assert "bestand Ingeschrevenen hoger beroepsonderwijs inclusief opleidingsvorm" in bron
    assert bron.endswith(", 2023/24 (p01hoinges)")


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

    async def fake_execute_tool(call, emit, recept_van=None):
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


def test_valt_de_bronnenlijst_uit_dan_blijft_de_eigen_sectie(monkeypatch):
    """Net als de citaties faalt de lijst zacht: geen bronnen uit code, dan blijven die van het model staan."""

    def kapot(steps):
        raise ValueError("kapot")

    monkeypatch.setattr(run_module, "bronnen_van", kapot)
    antwoord = f"{_ANTWOORD}\n\n**Bronnen**\n- DUO p01hoinges"
    einde = _slot(monkeypatch, [StreamResult(text="", tool_calls=[_LAAD]), StreamResult(text=antwoord, tool_calls=[])])

    assert einde["bronnen"] == []
    assert "**Bronnen**\n- DUO p01hoinges" in einde["content"]


@pytest.mark.parametrize("vast", [INGEHOUDEN, run_module.LEEG_ANTWOORD, WEIGER_ANTWOORD])
def test_een_vast_antwoord_krijgt_nooit_bronnen(vast):
    """Ook als de beurt data las: een vast antwoord uit code rust er niet op, dus geen dataantwoord."""
    assert run_module._slotbericht(vast, LoopResult(), [], False, [_DUO])["bronnen"] == []


def test_weigering_heeft_lege_bronnen(monkeypatch):
    """Van begin tot eind: een weigering zonder tools stuurt een lege lijst mee."""
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


# --- de link bij elke bronregel (#621): dezelfde catalogus-URL als onder een rapportgrafiek (#569) ---

_CBS_URL = "https://opendata.cbs.nl/#/CBS/nl/dataset/85423NED/table"
_DUO_URL = "https://onderwijsdata.duo.nl/dataset/p01hoinges"


def test_cbs_regel_linkt_naar_de_cbs_tabel():
    steps = [_stap("get_cbs_data", data_key="cbs:85423NED")]

    assert bronlinks_van(steps) == {_CBS: _CBS_URL}
    assert documentatie_url("85423NED") == _CBS_URL


def test_duo_regel_linkt_naar_de_duo_datasetpagina():
    steps = [_stap("get_duo_data", data_key="duo:p01hoinges:0"), _stap("query_data", data_key="duo:p01hoinges:0:sel")]

    assert bronlinks_van(steps) == {_DUO: _DUO_URL}
    assert documentatie_url("p01hoinges") == _DUO_URL


def test_rio_regels_linken_naar_de_rio_dataset():
    """Een get_rio_data-key en de registerregel van get_rio_instelling (dataset erkenningen)."""
    store.put("rio:erkenningen", pd.DataFrame({"x": [1]}), KeyMeta(bron="rio", dataset=ERKENNINGEN))
    register = {"bron": "RIO", "catalogus_titel": "RIO erkenningen", "peildatum": "2026-10-09", "status": "uniek"}
    steps = [_stap("get_rio_data", data_key="rio:erkenningen"), ("get_rio_instelling", json.dumps(register))]
    url = documentatie_url(ERKENNINGEN)

    assert (url or "").startswith("https://")
    assert bronlinks_van(steps) == {"RIO · erkenningen": url, "RIO erkenningen, peildatum 2026-10-09": url}


def test_uwv_en_roa_met_data_key_linken_naar_hun_dataset():
    store.put("uwv:gelderland", pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron="uwv", dataset=UWV_ID, peilmoment="mei"))
    store.put("roa:gelderland", pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron="roa", dataset=ROA_ID, peilmoment="v1"))
    steps = [
        ("get_uwv_vacatures", json.dumps({**json.loads(_UWV), "data_key": "uwv:gelderland"})),
        ("get_roa_benchmark", json.dumps({**json.loads(_ROA), "data_key": "roa:gelderland"})),
    ]

    assert bronlinks_van(steps) == {
        f"UWV · {UWV_ID}, mei": documentatie_url(UWV_ID),
        f"ROA · {ROA_ID}, v1": documentatie_url(ROA_ID),
    }
    assert all((url or "").startswith("https://") for url in bronlinks_van(steps).values())


def test_uwv_en_roa_van_voor_577_linken_naar_de_dataset_van_hun_tool():
    """Zonder data_key staat de bron in woorden; de dataset is die van de tool (tools.arbeidsmarkt.DATASET)."""
    steps = [("get_uwv_vacatures", _UWV), ("get_roa_benchmark", _ROA)]

    assert bronlinks_van(steps) == {
        "UWV Open Match, mei 2023": documentatie_url(DATASET["get_uwv_vacatures"]),
        "ROA, AIS tot 2030 (v20251218)": documentatie_url(DATASET["get_roa_benchmark"]),
    }


def test_een_link_die_geen_http_adres_is_blijft_weg_en_de_regel_blijft():
    record = {"_cbs_id": "85423NED", "documentatie": {"url": "javascript:alert(1)"}}
    steps = [_stap("get_cbs_data", data_key="cbs:85423NED")]
    with patch("tools.catalog._ruw_record", return_value=record):
        assert bronlinks_van(steps) == {}
        assert bronnen_van(steps) == [_CBS]


def test_een_dataset_die_de_catalogus_niet_kent_krijgt_geen_link():
    store.put("rio:onbekend", pd.DataFrame({"x": [1]}), KeyMeta(bron="rio", dataset="onbekend"))
    steps = [_stap("get_rio_data", data_key="rio:onbekend"), _stap("get_cbs_data", data_key="cbs:85423NED")]

    assert bronnen_van(steps) == ["RIO · onbekend", _CBS]
    assert bronlinks_van(steps) == {_CBS: _CBS_URL}


def test_zonder_gelezen_data_geen_links():
    assert bronlinks_van([_stap("search_catalog", resultaten=[{"id": "p01hoinges"}])]) == {}
    assert bronlinks_van([]) == {}


def test_elke_link_hoort_bij_een_regel_uit_de_bronnenlijst():
    steps = [
        _stap("get_duo_data", data_key="duo:p01hoinges:0"),
        _stap("get_cbs_data", data_key="cbs:85423NED"),
        ("get_uwv_vacatures", _UWV),
        ("get_uwv_vacatures", _UWV),
    ]

    assert list(bronlinks_van(steps)) == bronnen_van(steps)


# --- message_end: bronlinks naast bronnen, alleen als er links zijn ---


def test_slotbericht_draagt_de_links_naast_de_bronnen():
    einde = run_module._slotbericht(_ANTWOORD, LoopResult(), [], False, [_DUO, _CBS], bronlinks={_DUO: _DUO_URL})

    assert einde["bronnen"] == [_DUO, _CBS]
    assert einde["bronlinks"] == {_DUO: _DUO_URL}


def test_slotbericht_zonder_links_heeft_geen_bronlinks():
    assert "bronlinks" not in run_module._slotbericht(_ANTWOORD, LoopResult(), [], False, [_DUO], bronlinks={})
    assert "bronlinks" not in run_module._slotbericht(_ANTWOORD, LoopResult(), [], False, [_DUO])


@pytest.mark.parametrize("vast", [INGEHOUDEN, run_module.LEEG_ANTWOORD, WEIGER_ANTWOORD])
def test_een_vast_antwoord_krijgt_nooit_links(vast):
    einde = run_module._slotbericht(vast, LoopResult(), [], False, [_DUO], bronlinks={_DUO: _DUO_URL})

    assert einde["bronnen"] == [] and "bronlinks" not in einde


def test_dataantwoord_krijgt_de_links_bij_de_bronnen(monkeypatch):
    einde = _slot(monkeypatch, [StreamResult(text="", tool_calls=[_LAAD]), StreamResult(text=_ANTWOORD, tool_calls=[])])

    assert einde["bronnen"] == [_DUO]
    assert einde["bronlinks"] == {_DUO: _DUO_URL}


def test_vallen_de_links_uit_dan_blijven_antwoord_en_bronnen(monkeypatch, caplog):
    """Net als bij de bronnen: een fout in de links breekt het antwoord niet, en logt alleen een kenmerk."""

    def kapot(steps):
        raise ValueError("kapot")

    monkeypatch.setattr(run_module, "bronlinks_van", kapot)
    caplog.set_level(logging.ERROR)
    antwoord = f"{_ANTWOORD}\n\n**Bronnen**\n- DUO p01hoinges"
    einde = _slot(monkeypatch, [StreamResult(text="", tool_calls=[_LAAD]), StreamResult(text=antwoord, tool_calls=[])])

    assert einde["content"] == _ANTWOORD
    assert einde["bronnen"] == [_DUO]
    assert "bronlinks" not in einde
    assert any(r.levelno == logging.ERROR and "in bronlinks" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    ("tekst", "verwacht"),
    [
        ("Wat u ziet.\n\n**Bronnen**\n- Wat u moet weten", "WAT U ZIET.\n\n**Bronnen**\n- Wat u moet weten"),
        (
            "Wat u ziet.\n\n**Bronnen:**\n- Wat u moet weten\n\nTot slot u.",
            "WAT U ZIET.\n\n**Bronnen:**\n- Wat u moet weten\n\nTOT SLOT U.",
        ),
        ("Geen bronnen hier.", "GEEN BRONNEN HIER."),
    ],
)
def test_buiten_de_bronnensectie_gaat_om_en_de_sectie_blijft_letterlijk(tekst, verwacht):
    """Een brontitel is een citaat: de je-vorm (#536) zet alleen het antwoord zelf om."""
    assert buiten_bronnensectie(tekst, str.upper) == verwacht
