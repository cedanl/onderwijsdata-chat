"""Een vage vraag krijgt een zichtbare interpretatie (#514, UX F07b).

"studentenwelzijn" kreeg zonder navraag een grafiek over werkdruk bij gepromoveerden. Komt er
geen verduidelijkingskaart, dan opent het antwoord nu met "Ik ga uit van …" en de datasets
waarop het rust; dat staat in code, niet in de prompt alleen.
"""

import asyncio
import importlib
import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent.interpretatie import interpretatiezin, is_vaag, met_interpretatie
from agent.stream import StreamResult
from tools import store
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")


@pytest.mark.parametrize(
    "vraag", ["studentenwelzijn", "Studentenwelzijn?", "kwaliteit van het onderwijs", "studiesucces", "welzijn"]
)
def test_een_kort_thema_zonder_maat_is_vaag(vraag):
    assert is_vaag(vraag)


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel studenten heeft de HU?",
        "instroom hbo",
        "uitval mbo niveau 2",
        "Zoek datasets over welzijn",
        "wat is het verschil tussen bol en bbl",
        "studentenwelzijn 2024",
        "Hoe gaat het met het onderwijs?",
        "diploma's per sector in de laatste vijf jaar",
        "",
    ],
)
def test_een_maat_vraagwoord_getal_of_lange_vraag_is_niet_vaag(vraag):
    assert not is_vaag(vraag)


_STAP = ("get_cbs_data", json.dumps({"data_key": "cbs:85423NED", "rijen": []}))


@pytest.fixture
def geladen():
    store.put("cbs:85423NED", pd.DataFrame({"a": [1]}), KeyMeta(bron="cbs", dataset="85423NED"))
    with patch(
        "agent.interpretatie.catalogus_titel",
        side_effect=lambda d: {"85423NED": "Hoger onderwijs; ingeschrevenen"}.get(d, d),
    ):
        yield


def test_de_zin_noemt_de_catalogustitels_en_de_vraag(geladen):
    zin = interpretatiezin("studentenwelzijn", [_STAP])
    assert zin is not None
    assert zin.startswith("Ik ga uit van de lezing «Hoger onderwijs; ingeschrevenen» voor je vraag 'studentenwelzijn'.")
    assert "Bedoel je iets anders" in zin


def test_zonder_bekende_dataset_geen_zin():
    assert interpretatiezin("studentenwelzijn", [("get_cbs_data", json.dumps({"data_key": "cbs:onbekend"}))]) is None
    assert interpretatiezin("studentenwelzijn", []) is None


def test_het_antwoord_opent_met_de_zin_voor_een_vage_vraag(geladen):
    tekst = met_interpretatie("Er zijn veel studenten.", "studentenwelzijn", [_STAP], {})
    assert tekst.startswith("Ik ga uit van de lezing «")
    assert tekst.endswith("\n\nEr zijn veel studenten.")


def test_geen_zin_bij_een_duidelijke_vraag_na_een_kaart_of_eigen_lezing(geladen):
    assert met_interpretatie("Antwoord.", "Hoeveel studenten heeft de HU?", [_STAP], {}) == "Antwoord."
    assert met_interpretatie("Antwoord.", "studentenwelzijn", [_STAP], {"clarify_rondes": 1}) == "Antwoord."
    eigen = "Ik ga uit van ingeschrevenen in het hoger onderwijs. Antwoord."
    assert met_interpretatie(eigen, "studentenwelzijn", [_STAP], {}) == eigen


def test_een_titel_met_cijfers_komt_niet_in_de_zin(geladen):
    with patch("agent.interpretatie.catalogus_titel", return_value="Instroom 2019-2024"):
        assert interpretatiezin("welzijn", [_STAP]) is None


# --- de hele beurt: de zin staat vóór het antwoord, en de bronnen blijven eronder ---

_ROWS = json.dumps({"data_key": "duo:p02:a", "rijen": [{"AANTAL": 5943}]})
_LAAD = {"id": "l1", "name": "get_duo_data", "arguments": '{"dataset_id": "duo-a"}'}
_DUO = [{"leverancier": "DUO", "bron": "Ingeschrevenen hbo", "tags": ["hbo"], "_ckan_id": "duo-a"}]


def _run(monkeypatch, steps: list[StreamResult], vraag: str, session: dict | None = None) -> tuple[str, list[dict]]:
    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    async def execute(call, emit):
        return _ROWS, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", execute)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    store.put("duo:p02:a", pd.DataFrame({"AANTAL": [5943]}), KeyMeta(bron="duo", dataset="duo-a"))
    with patch("tools.catalog._cbs", return_value=[]), patch("tools.catalog._rio_duo", return_value=_DUO):
        tekst = asyncio.run(
            run_module.run(
                [{"role": "user", "content": vraag}], session or {}, emit, asyncio.Event(), model="openai/gpt-4o"
            )
        )
    return tekst, events


def test_een_beurt_op_een_vaag_thema_opent_met_de_lezing(monkeypatch):
    tekst, events = _run(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_LAAD]),
            StreamResult(text="Daar heb ik data over gevonden.", tool_calls=[]),
        ],
        "studentenwelzijn",
    )
    assert tekst.startswith("Ik ga uit van de lezing «Ingeschrevenen hbo» voor je vraag 'studentenwelzijn'.")
    assert "Daar heb ik data over gevonden." in tekst
    [einde] = [e for e in events if e.get("type") == "message_end"]
    assert einde["content"] == tekst and einde["bronnen"]


def test_een_duidelijke_vraag_krijgt_geen_lezing(monkeypatch):
    tekst, _ = _run(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_LAAD]),
            StreamResult(text="Daar heb ik data over gevonden.", tool_calls=[]),
        ],
        "Hoeveel studenten heeft de HU?",
    )
    assert not tekst.startswith("Ik ga uit van")


def test_zonder_data_geen_lezing(monkeypatch):
    tekst, _ = _run(monkeypatch, [StreamResult(text="Daar heb ik geen data voor.", tool_calls=[])], "studentenwelzijn")
    assert not tekst.startswith("Ik ga uit van")


def test_de_prompt_noemt_de_regel():
    from prompts import SYSTEM_PROMPT

    assert "**Een vaag thema zonder maat**" in SYSTEM_PROMPT and "Ik ga uit van" in SYSTEM_PROMPT
