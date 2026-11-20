"""De websocket-kant van de rapportselectie (#908): de checklist ophalen en de gekozen beurten en figuren (#993)
meesturen.

`report_checklist` leest alleen en kost geen model; `generate_report` controleert de selectie tegen het gesprek voordat
er een run of een berichtlimiet aan te pas komt, en weigert hardop wat niet klopt.
"""

import asyncio
import json
import logging

import pytest

from agent import figuurstappen
from agent.rapportselectie import LEGE_SELECTIE, TE_VEEL_FIGUREN, VEROUDERDE_SELECTIE
from agent.session_data import record_data_key
from routes import chat
from tools.schemas import TOOL_GET_CBS_DATA, TOOL_GET_DUO_DATA

_VRAAG_1 = "Hoeveel studenten heeft de geheime instelling Quokka?"
_VRAAG_2 = "En het rendement?"


@pytest.fixture
def sessie():
    s = chat._new_session(username="tester")
    s["messages"].append({"role": "user", "content": _VRAAG_1})
    duo = {"name": TOOL_GET_DUO_DATA, "arguments": {"dataset_id": "p01hoinges", "resource": 3}}
    record_data_key(s, json.dumps({"data_key": "duo:p01hoinges:3"}), duo)
    s["messages"] += [
        {"role": "assistant", "content": "Zie de tabel."},
        {"role": "user", "content": _VRAAG_2},
    ]
    cbs = {"name": TOOL_GET_CBS_DATA, "arguments": {"dataset_id": "83285NED"}}
    record_data_key(s, json.dumps({"data_key": "cbs:83285NED"}), cbs)
    # De figuur die beurt 2 tekende: de stap zoals run._bewaar_stap haar vastlegt (#993).
    figuurstappen.voeg_toe(s, [_STAP])
    return s


_STAP = {
    "id": "f2a1b3c4d5e6",
    "tool": "create_plot",
    "arguments": {"data_key": "cbs:83285NED", "chart_type": "line", "x": "Startjaar", "y": "Rendement", "title": "R"},
    "titel": "Rendement per startjaar",
    "keys": ["cbs:83285NED"],
}


def _run_tot_einde(action: str, msg: dict, session: dict):
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    async def scenario():
        terug = await chat.ACTIES[action]({"action": action, **msg}, session, emit, None)
        if terug is not None:
            await terug
        return terug

    return asyncio.run(scenario()), events


@pytest.fixture
def rapporten(monkeypatch):
    """Elk rapport dat gestart wordt, zonder model: wat `_generate_report` kreeg."""
    gevraagd: list[dict] = []

    async def opnemen(session, emit, model, author=None, onderzoeksvraag=None, beurten=None, figuren=()):
        gevraagd.append({"onderzoeksvraag": onderzoeksvraag, "beurten": beurten, "figuren": figuren})

    monkeypatch.setattr(chat, "_generate_report", opnemen)
    return gevraagd


def test_de_checklist_komt_als_frame_uit_het_gesprek(sessie):
    terug, events = _run_tot_einde("report_checklist", {}, sessie)

    assert terug is None
    [frame] = events
    assert frame["type"] == "report_checklist"
    assert [(i["beurt"], i["vraag"]) for i in frame["items"]] == [(1, _VRAAG_1), (2, _VRAAG_2)]
    assert "p01hoinges" in frame["items"][0]["bronnen"][0]
    assert [i["figuren"] for i in frame["items"]] == [
        [],
        [{"id": _STAP["id"], "titel": "Rendement per startjaar", "beurten": [2]}],
    ]


def test_zonder_data_is_de_checklist_leeg():
    _, events = _run_tot_einde("report_checklist", {}, chat._new_session())

    assert events == [{"type": "report_checklist", "items": []}]


def test_de_checklist_zet_geen_vraag_op_info_in_het_log(sessie, caplog):
    with caplog.at_level(logging.INFO):
        _run_tot_einde("report_checklist", {}, sessie)

    assert "RAPPORT checklist" in caplog.text
    assert "Quokka" not in caplog.text and "rendement" not in caplog.text.lower()
    assert "figuren=1" in caplog.text


def test_de_checklist_start_geen_run_en_telt_niet_mee_voor_de_berichtlimiet(sessie, monkeypatch):
    def limiet(*_):
        raise AssertionError("de checklist raakt de berichtlimiet niet")

    monkeypatch.setattr(chat, "_binnen_limiet", limiet)

    _run_tot_einde("report_checklist", {}, sessie)


def test_een_rapport_met_een_deel_van_de_beurten_geeft_die_door(sessie, rapporten):
    terug, events = _run_tot_einde("generate_report", {"beurten": [2]}, sessie)

    assert isinstance(terug, asyncio.Task) and events == []
    assert rapporten == [{"onderzoeksvraag": None, "beurten": frozenset({2}), "figuren": ()}]


def test_de_gekozen_figuren_gaan_mee_en_trekken_hun_beurt_mee(sessie, rapporten):
    _run_tot_einde("generate_report", {"beurten": [1], "figuren": [_STAP["id"]]}, sessie)

    assert rapporten == [{"onderzoeksvraag": None, "beurten": None, "figuren": (_STAP["id"],)}]


@pytest.mark.parametrize(
    ("figuren", "melding"),
    [
        (["onbekend"], VEROUDERDE_SELECTIE),
        ("f2a1b3c4d5e6", VEROUDERDE_SELECTIE),
        ([1], VEROUDERDE_SELECTIE),
        ([_STAP["id"], _STAP["id"]], VEROUDERDE_SELECTIE),
        ([f"f{i}" for i in range(5)], TE_VEEL_FIGUREN),
    ],
)
def test_een_figuurkeuze_die_niet_klopt_start_geen_rapport(sessie, rapporten, figuren, melding):
    terug, events = _run_tot_einde("generate_report", {"beurten": [1, 2], "figuren": figuren}, sessie)

    assert terug is None and rapporten == []
    assert events == [{"type": "error", "message": melding, "modelafhankelijk": False}]


@pytest.mark.parametrize("msg", [{}, {"beurten": None}, {"beurten": [1, 2]}, {"beurten": [2, 1, 1]}])
def test_zonder_selectie_of_met_alles_aan_is_het_rapport_van_het_hele_gesprek(sessie, rapporten, msg):
    _run_tot_einde("generate_report", msg, sessie)

    assert rapporten == [{"onderzoeksvraag": None, "beurten": None, "figuren": ()}]


@pytest.mark.parametrize(
    ("beurten", "melding"),
    [([], LEGE_SELECTIE), ([3], VEROUDERDE_SELECTIE), (["1"], VEROUDERDE_SELECTIE), ("1", VEROUDERDE_SELECTIE)],
)
def test_een_selectie_die_niet_klopt_start_geen_rapport_en_zegt_waarom(
    sessie, rapporten, monkeypatch, beurten, melding
):
    def limiet(*_):
        raise AssertionError("een geweigerde selectie kost geen berichtlimiet")

    monkeypatch.setattr(chat, "_binnen_limiet", limiet)

    terug, events = _run_tot_einde("generate_report", {"beurten": beurten}, sessie)

    assert terug is None and rapporten == []
    assert events == [{"type": "error", "message": melding, "modelafhankelijk": False}]


def test_een_selectie_bij_een_gesprek_zonder_checklist_wordt_geweigerd(rapporten):
    s = chat._new_session(username="tester")
    s["messages"].append({"role": "user", "content": _VRAAG_1})
    record_data_key(s, json.dumps({"data_key": "duo:p01hoinges:3"}))
    del s["data_vraag"]

    terug, events = _run_tot_einde("generate_report", {"beurten": [1]}, s)

    assert terug is None and rapporten == []
    assert events[0]["message"] == VEROUDERDE_SELECTIE
