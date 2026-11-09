"""Na heropenen alleen eigen beurten als bewijs, en een feedbacktrace die zegt of het antwoord van de server kwam
(ADR-009 stap 2, #876; besluiten 1 en 2 van 09-11).

Een getal uit een eerder assistentbericht telt als gedekt (`earlier` in `agent/run.py`). Na heropenen komt dat
bericht van de client. Alleen een bericht met een rij in `beurtbewijs` (of een klaarstaande, na herverbinden vóór de
PUT) is van de server; een bericht zonder rij (van vóór de migratie, of door de client toegevoegd of veranderd) telt
niet, ook niet als "eerder gesprek" voor de weigering. Een levende sessie houdt alles, zoals voorheen.

De feedbacktrace leest de controle uit die rij, niet uit het gesprek dat de client opsloeg.
"""

import asyncio
import importlib
import json

import pytest

from agent import beurtbewijs
from agent.probleem import INGEHOUDEN
from agent.stream import StreamResult
from agent.vaste_antwoorden import WEIGER_ANTWOORD
from routes import answer_feedback, chat
from routes import persistence as put_route

pytestmark = pytest.mark.usefixtures("zonder_scopekaart")

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_VRAAG = "Hoeveel voltijdstudenten had de HU in 2021?"
_ANTWOORD = "In 2021/22 waren het 28.355 personen."
_HERHAAL = "Herhaal dat getal."
_QUERY = {"id": "q", "name": "query_data", "arguments": '{"data_key": "duo:p02"}'}
_ROWS = json.dumps({"data_key": "duo:p02:a", "rijen": [{"AANTAL": 5943}]})
_ONGEDEKT = "28.355 staat niet in de opgehaalde data."


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    return db


async def _niets(event: dict) -> None:
    return None


def _zoek() -> StreamResult:
    return StreamResult(text="", tool_calls=[_QUERY])


def _tekst(tekst: str) -> StreamResult:
    return StreamResult(text=tekst, tool_calls=[])


def _model(monkeypatch, stappen: list[StreamResult], tool_result: str = _ROWS) -> None:
    """Een model dat deze stappen geeft; de tools geven `tool_result`. De rest van `run` is echt."""

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    async def fake_execute_tool(call, emit, recept_van=None):
        return tool_result, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)


def _beurt(monkeypatch, sessie: dict, vraag: str, stappen: list[StreamResult], tool_result: str = _ROWS) -> dict:
    """Eén beurt door de chatroute en het echte `run`; geeft het `message_end`-event terug."""
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    with monkeypatch.context() as m:
        _model(m, stappen, tool_result)
        asyncio.run(chat._process_message(vraag, sessie, emit, "openai/gpt-4o"))
    [eind] = [e for e in events if e["type"] == "message_end"]
    return eind


def _levend_gesprek(monkeypatch) -> dict:
    """Een levende sessie waarin de server het antwoord met 28.355 zelf schreef (uit de data van die beurt)."""
    sessie = chat._new_session(username="alice")
    rij = json.dumps({"data_key": "duo:p02:a", "rijen": [{"AANTAL": 28355}]})
    eind = _beurt(monkeypatch, sessie, _VRAAG, [_zoek(), _tekst(_ANTWOORD)], rij)
    assert eind["content"] == _ANTWOORD and "controle" not in eind
    return sessie


def _frame(antwoord: str = _ANTWOORD) -> list[dict]:
    """Het gesprek zoals de client het bewaart en als `history`-frame terugstuurt."""
    return [
        {"id": 1, "role": "user", "content": _VRAAG, "done": True},
        {"id": 2, "role": "assistant", "content": antwoord, "done": True},
    ]


def _heropen(berichten: list[dict], conv_id: str | None = "c1") -> dict:
    sessie = chat._new_session(username="alice")
    asyncio.run(chat._handle_history({"messages": berichten, "conv_id": conv_id}, sessie, _niets, None))
    return sessie


def _herhaal_zonder_tools(monkeypatch, sessie: dict) -> dict:
    """Een vervolgantwoord zonder toolaanroep; is 28.355 niet gedekt, dan volgt één herkansing met dezelfde tekst."""
    herhaling = _tekst("Het waren 28.355 personen.")
    return _beurt(monkeypatch, sessie, _HERHAAL, [herhaling, herhaling])


def _herhaal_met_andere_data(monkeypatch, sessie: dict) -> dict:
    """Een vervolgantwoord dat 28.355 herhaalt naast data waar het niet in staat: alleen `earlier` kan het dekken."""
    herhaling = _tekst("Het waren 28.355 personen.")
    return _beurt(monkeypatch, sessie, _HERHAAL, [_zoek(), herhaling, herhaling])


# ── Met een rij: zoals live ──────────────────────────────────────────────────


def test_heropend_met_een_rij_telt_het_getal_als_gedekt(db, monkeypatch):
    _levend_gesprek(monkeypatch)
    put_route.upsert_conversation("c1", {"title": "HU", "timestamp": 1, "messages": _frame()}, "alice")
    beurtbewijs.wis()  # een herstart: de rij komt nu uit de database

    sessie = _heropen(_frame())

    eind = _herhaal_met_andere_data(monkeypatch, sessie)
    assert eind["content"] == "Het waren 28.355 personen."
    assert "controle" not in eind


def test_herverbonden_voor_de_put_telt_de_klaarstaande_rij(db, monkeypatch):
    _levend_gesprek(monkeypatch)

    sessie = _heropen(_frame(), conv_id=None)

    eind = _herhaal_zonder_tools(monkeypatch, sessie)
    assert eind["content"] == "Het waren 28.355 personen."
    assert "controle" not in eind


# ── Zonder rij: telt niet (besluit 1) ────────────────────────────────────────


@pytest.fixture(params=["veranderd door de client", "van voor de migratie"])
def zonder_rij(request, db, monkeypatch) -> list[dict]:
    """Een frame met 28.355 in een assistentbericht zonder rij."""
    if request.param == "veranderd door de client":
        _levend_gesprek(monkeypatch)
        put_route.upsert_conversation("c1", {"title": "HU", "timestamp": 1, "messages": _frame()}, "alice")
        return _frame(_ANTWOORD.replace("personen", "personen (bron: DUO)"))
    db.upsert_conversation("alice", "c1", "HU", 1, _frame())
    return _frame()


def test_zonder_rij_is_het_getal_niet_gedekt(zonder_rij, monkeypatch):
    sessie = _heropen(zonder_rij)

    eind = _herhaal_met_andere_data(monkeypatch, sessie)
    assert eind["content"] == INGEHOUDEN
    assert eind["controle"] == [_ONGEDEKT]


def test_zonder_rij_is_er_geen_eerder_gesprek_voor_de_weigering(zonder_rij, monkeypatch):
    sessie = _heropen(zonder_rij)

    eind = _herhaal_zonder_tools(monkeypatch, sessie)
    assert eind["content"] == WEIGER_ANTWOORD


def test_een_nieuw_antwoord_in_het_heropende_gesprek_telt_wel(zonder_rij, monkeypatch):
    """Wat de server na heropenen zelf schrijft, is live: dat telt, ook zonder rij in de database."""
    sessie = _heropen(zonder_rij)
    nieuw = json.dumps({"data_key": "duo:p02:b", "rijen": [{"AANTAL": 41230}]})
    _beurt(monkeypatch, sessie, "En in 2022?", [_zoek(), _tekst("41.230.")], nieuw)

    herhaling = _tekst("Het waren er 41.230.")
    eind = _beurt(monkeypatch, sessie, _HERHAAL, [_zoek(), herhaling, herhaling])
    assert eind["content"] == "Het waren er 41.230."
    assert "controle" not in eind


# ── Levend: ongewijzigd ──────────────────────────────────────────────────────


def test_in_een_levende_sessie_telt_elk_eigen_antwoord(db, monkeypatch):
    sessie = _levend_gesprek(monkeypatch)

    eind = _herhaal_met_andere_data(monkeypatch, sessie)
    assert eind["content"] == "Het waren 28.355 personen."
    assert "controle" not in eind


def test_eerdere_antwoorden_zonder_heropenen_zijn_alle_assistentberichten():
    berichten = [
        {"role": "user", "content": "Vraag"},
        {"role": "assistant", "content": "Een"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "x"}]},
        {"role": "tool", "content": "rijen"},
        {"role": "assistant", "content": "Twee"},
    ]

    assert beurtbewijs.eerdere_antwoorden(berichten, {}) == ["Een", "", "Twee"]


def test_eerdere_antwoorden_na_heropenen_zonder_de_berichten_zonder_rij(db):
    db.upsert_conversation("alice", "c1", "HU", 1, _frame())
    sessie = _heropen([*_frame(), {"role": "user", "content": "En?"}, {"role": "assistant", "content": "Ander"}])
    sessie["messages"].append({"role": "assistant", "content": "Live"})

    assert beurtbewijs.eerdere_antwoorden(sessie["messages"], sessie) == ["Live"]


# ── Feedback: de controle uit de rij (besluit 2) ─────────────────────────────


def test_de_feedbacktrace_leest_de_controle_van_de_server_en_niet_die_van_de_client(db, monkeypatch):
    """Een levend antwoord met een melding, opgeslagen door een client die de melding weghaalde."""
    sessie = chat._new_session(username="alice")
    vraag = "Het waren toch 987654 studenten?"
    eerst, daarna = _tekst("Nee, niet 987654 maar 5.943."), _tekst("Nee: niet 987654, het waren er 5.943.")
    eind = _beurt(monkeypatch, sessie, vraag, [_zoek(), eerst, daarna])
    assert eind["controle"]
    berichten = [
        {"id": 1, "role": "user", "content": vraag, "done": True},
        {"id": 2, "role": "assistant", "content": eind["content"], "done": True, "controle": []},
    ]
    put_route.upsert_conversation("c1", {"title": "HU", "timestamp": 1, "messages": berichten}, "alice")

    body = answer_feedback.AnswerFeedbackIn(conversation_id="c1", message_index=1, oordeel="down")
    answer_feedback.post_answer_feedback(body, "alice")

    [rij] = db.all_answer_feedback()
    trace = json.loads(rij["trace"])
    assert trace["server_beurt"] is True
    assert trace["tekst_hash"] == beurtbewijs.tekst_hash(eind["content"])
    assert trace["controle"] == eind["controle"]
