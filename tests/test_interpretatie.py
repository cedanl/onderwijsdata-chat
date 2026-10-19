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

from agent.interpretatie import interpretatie_bij, interpretatiezin, is_vaag, is_vervolgvraag
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


def test_een_vage_vraag_krijgt_de_zin(geladen):
    zin = interpretatie_bij("Er zijn veel studenten.", "studentenwelzijn", [_STAP], {}, vervolg=False)
    assert zin is not None
    assert zin.startswith("Ik ga uit van de lezing «Hoger onderwijs; ingeschrevenen» voor je vraag 'studentenwelzijn'.")


def test_geen_zin_bij_een_duidelijke_vraag_na_een_kaart_of_eigen_lezing(geladen):
    assert interpretatie_bij("Antwoord.", "Hoeveel studenten heeft de HU?", [_STAP], {}, vervolg=False) is None
    assert interpretatie_bij("Antwoord.", "studentenwelzijn", [_STAP], {"clarify_rondes": 1}, vervolg=False) is None
    eigen = "Ik ga uit van ingeschrevenen in het hoger onderwijs. Antwoord."
    assert interpretatie_bij(eigen, "studentenwelzijn", [_STAP], {}, vervolg=False) is None


# --- een vervolgvraag: de lezing lag al vast bij de eerste vraag (#545) ---


def _gebruiker(tekst) -> dict:
    return {"role": "user", "content": tekst}


def _assistent(tekst: str) -> dict:
    return {"role": "assistant", "content": tekst}


def test_geen_zin_bij_een_vage_vervolgvraag(geladen):
    gesprek = [
        _gebruiker("Hoeveel mbo-studenten in 2024/25?"),
        _assistent("Er zijn er veel."),
        _gebruiker("Alleen vrouwen"),
    ]
    session: dict = {}
    assert interpretatie_bij("Antwoord.", "Alleen vrouwen", [_STAP], session, vervolg=is_vervolgvraag(gesprek)) is None
    assert session == {}


def test_alleen_de_eerste_gebruikersbeurt_is_geen_vervolgvraag():
    assert not is_vervolgvraag([_gebruiker("studentenwelzijn")])
    assert not is_vervolgvraag([_assistent("Welkom."), _gebruiker("studentenwelzijn")])
    assert is_vervolgvraag([_gebruiker("mbo 2024/25"), _assistent("Antwoord."), _gebruiker("Alleen vrouwen")])
    # Een blokkenlijst telt als beurt als er tekst in staat.
    assert is_vervolgvraag([_gebruiker([{"type": "text", "text": "mbo"}]), _gebruiker("Alleen vrouwen")])


@pytest.mark.parametrize("leeg", ["", "   ", None, [], [{"type": "text", "text": " "}]])
def test_een_lege_gebruikersbeurt_telt_niet(leeg):
    assert not is_vervolgvraag([_gebruiker(leeg), _gebruiker("studentenwelzijn")])


def test_een_titel_met_cijfers_komt_niet_in_de_zin(geladen):
    with patch("agent.interpretatie.catalogus_titel", return_value="Instroom 2019-2024"):
        assert interpretatiezin("welzijn", [_STAP]) is None


# --- de hele beurt: de zin staat vóór het antwoord, en de bronnen blijven eronder ---

_ROWS = json.dumps({"data_key": "duo:p02:a", "rijen": [{"AANTAL": 5943}]})
_LAAD = {"id": "l1", "name": "get_duo_data", "arguments": '{"dataset_id": "duo-a"}'}
_DUO = [{"leverancier": "DUO", "bron": "Ingeschrevenen hbo", "tags": ["hbo"], "_ckan_id": "duo-a"}]


def _run(
    monkeypatch, steps: list[StreamResult], vraag: str | list[dict], session: dict | None = None
) -> tuple[str, list[dict]]:
    """Eén beurt door run(); `vraag` is één vraag of het hele gesprek tot en met de laatste gebruikersbeurt."""
    messages = [{"role": "user", "content": vraag}] if isinstance(vraag, str) else vraag

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    async def execute(call, emit, recept_van=None):
        return _ROWS, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", execute)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    store.put("duo:p02:a", pd.DataFrame({"AANTAL": [5943]}), KeyMeta(bron="duo", dataset="duo-a"))
    with patch("tools.catalog._cbs", return_value=[]), patch("tools.catalog._rio_duo", return_value=_DUO):
        tekst = asyncio.run(run_module.run(messages, session or {}, emit, asyncio.Event(), model="openai/gpt-4o"))
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


def _datastappen() -> list[StreamResult]:
    return [
        StreamResult(text="", tool_calls=[_LAAD]),
        StreamResult(text="Daar heb ik data over gevonden.", tool_calls=[]),
    ]


_KETEN = ["mbo 2024/25", "En in 2021?", "Alleen vrouwen"]


def _gesprek_tot(beurt: int) -> list[dict]:
    """Het gesprek uit de keten tot en met gebruikersbeurt `beurt` (0-based), met een antwoord tussen de beurten."""
    gesprek: list[dict] = []
    for vraag in _KETEN[:beurt]:
        gesprek += [_gebruiker(vraag), _assistent("Daar heb ik data over gevonden.")]
    return [*gesprek, _gebruiker(_KETEN[beurt])]


def test_een_vage_vervolgvraag_krijgt_geen_lezing(monkeypatch):
    tekst, events = _run(monkeypatch, _datastappen(), _gesprek_tot(2))
    [einde] = [e for e in events if e.get("type") == "message_end"]
    assert "Bedoel je iets anders" not in tekst
    assert "Bedoel je iets anders" not in einde["content"]
    assert einde["bronnen"]


def test_een_vaag_thema_als_eerste_beurt_houdt_de_lezing(monkeypatch):
    tekst, events = _run(monkeypatch, _datastappen(), [_gebruiker("studentenwelzijn")])
    [einde] = [e for e in events if e.get("type") == "message_end"]
    assert "Bedoel je iets anders" in tekst and "Bedoel je iets anders" in einde["content"]


@pytest.mark.parametrize("beurt", range(len(_KETEN)))
def test_geen_beurt_in_de_keten_krijgt_een_lezing(monkeypatch, beurt):
    tekst, events = _run(monkeypatch, _datastappen(), _gesprek_tot(beurt))
    [einde] = [e for e in events if e.get("type") == "message_end"]
    assert "Bedoel je iets anders" not in tekst and "Bedoel je iets anders" not in einde["content"]


def test_de_prompt_noemt_de_regel():
    from prompts import SYSTEM_PROMPT

    assert "**Een vaag thema zonder maat**" in SYSTEM_PROMPT and "Ik ga uit van" in SYSTEM_PROMPT
