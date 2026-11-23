"""Een vervolgvraag in een heropend gesprek krijgt na een herstart zijn data terug (#1086).

De store leeft in het geheugen; `store.clear()` plus `recepten.wis()` is hier de herstart. Het gesprek staat met zijn
recept in de database. De chat zette de keys na het heropenen alleen in de sessie: een `query_data` op de oude key gaf
`onbekende_data_key` en het antwoord stond er kaal (geen Bronnen, Telling en citaties; ook het beurtbewijs bleef
bronloos). Nu haalt de chat vóór de beurt terug wat de store kwijt is.
"""

import asyncio
import importlib
import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent import recepten
from agent.session_data import neem_beurtbewijs, record_data_key
from agent.stream import StreamResult
from routes import chat
from tools import duo, store
from tools.schemas import TOOL_GET_DUO_DATA, TOOL_QUERY_DATA

pytestmark = pytest.mark.usefixtures("zonder_scopegrens", "zonder_scopekaart")

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_DF = pd.DataFrame({"STUDIEJAAR": [2024, 2025], "OPLEIDINGSVORM": ["VT", "VT"], "AANTAL": [27135, 26370]})
_KEY = "duo:p01hoinges:0"
_VRAAG = "En hoeveel waren het er in 2025?"
_ANTWOORD = "In 2025 waren het er 26.370."
_QUERY = json.dumps({"data_key": _KEY, "filters": {"STUDIEJAAR": 2025}})


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    db.init_db()


@pytest.fixture
def bron():
    """De DUO-bron nagebootst; `bron.load.side_effect` kan een fout geven (de bron ligt eruit)."""
    with (
        patch("tools.duo._duo.load", side_effect=lambda *_: _DF.copy()) as laden,
        patch("tools.duo_meta.teldefinitie", return_value="natuurlijke personen"),
    ):
        yield laden


def _herstart() -> None:
    store.clear()
    recepten.wis()


def _eerste_beurt(username: str) -> dict:
    """Een databeurt zoals de chat hem doet, en het gesprek zoals de client het opslaat."""
    session = {"username": username}
    resultaat = duo.get_duo_data(dataset_id="p01hoinges", resource=0)
    record_data_key(session, resultaat, {"name": TOOL_GET_DUO_DATA, "arguments": {"dataset_id": "p01hoinges"}})
    recepten.bewaar(username, "c1", [{"role": "assistant", "tools": [{"name": TOOL_GET_DUO_DATA, "dataKey": _KEY}]}])
    return session


def _heropen(username: str) -> dict:
    session = chat._new_session(username)
    messages = [{"role": "user", "content": "Hoeveel studenten?"}, {"role": "assistant", "content": "27.135."}]

    async def emit(_event):
        pass

    msg = {"action": "history", "messages": messages, "conv_id": "c1"}

    async def openen():
        await chat.ACTIES["history"](msg, session, emit, None)

    asyncio.run(openen())
    return session


def _vervolgvraag(monkeypatch, session: dict, antwoord: str = _ANTWOORD) -> tuple[list[dict], list[list[dict]]]:
    """Een vervolgvraag waarop het model `query_data` doet op de key uit het gesprek, met de echte tool."""
    stappen = [
        StreamResult(text="", tool_calls=[{"id": "q1", "name": TOOL_QUERY_DATA, "arguments": _QUERY}]),
        StreamResult(text=antwoord, tool_calls=[]),
    ]
    gezien: list[list[dict]] = []

    async def fake_completion(*args, **kwargs):
        gezien.append(list(kwargs["messages"]))
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    messages = session["messages"]
    messages.append({"role": "user", "content": _VRAAG})
    asyncio.run(run_module.run(messages, session, emit, asyncio.Event(), model="openai/gpt-4o"))
    return events, gezien


def test_de_vervolgvraag_na_een_herstart_krijgt_data_bronnen_en_telling(database, bron, monkeypatch):
    _eerste_beurt("alice")
    _herstart()
    session = _heropen("alice")
    assert store.get(_KEY) is None, "lui: het heropenen haalt niets op"

    events, gezien = _vervolgvraag(monkeypatch, session)

    toolresultaat = next(m for m in gezien[1] if m["role"] == "tool")["content"]
    assert "onbekende_data_key" not in toolresultaat
    assert json.loads(toolresultaat)["rijen"], "de tool geeft data"
    einde = next(e for e in reversed(events) if e["type"] == "message_end")
    assert einde["bronnen"], "Bronnen onder het antwoord"
    assert "Telling" in einde["content"] or "telling" in einde["content"]
    toast = next(e for e in events if e["type"] == "toast")
    assert toast["level"] == "info", "melding: herladen, de bron kan gewijzigd zijn"


def test_het_beurtbewijs_van_dat_antwoord_bevat_de_bronregel(database, bron, monkeypatch):
    _eerste_beurt("alice")
    _herstart()
    session = _heropen("alice")

    _vervolgvraag(monkeypatch, session)

    _, _, bronnen = neem_beurtbewijs(session)
    assert any(regels for regels in bronnen.values()), bronnen


def test_zonder_herstart_wordt_er_niets_opnieuw_opgehaald(database, bron, monkeypatch):
    _eerste_beurt("alice")
    session = _heropen("alice")
    aanroepen = bron.call_count

    events, _ = _vervolgvraag(monkeypatch, session)

    assert bron.call_count == aanroepen
    assert not [e for e in events if e["type"] == "toast"]


def test_lukt_terughalen_niet_dan_meldt_de_chat_dat_de_data_weg_is(database, bron, monkeypatch):
    _eerste_beurt("alice")
    _herstart()
    session = _heropen("alice")
    bron.side_effect = RuntimeError("bron ligt eruit")

    events, gezien = _vervolgvraag(monkeypatch, session, "De data van eerder is er niet meer.")

    [toast] = [e for e in events if e["type"] == "toast"]
    assert toast["level"] == "warning"
    assert "niet meer beschikbaar" in toast["message"] and "rapport" not in toast["message"]
    assert "onbekende_data_key" in next(m for m in gezien[1] if m["role"] == "tool")["content"]
    assert next(e for e in reversed(events) if e["type"] == "message_end")["type"] == "message_end", (
        "de beurt gaat door"
    )
