"""#759: Annuleer stopte een rapport niet zolang het model nog niets terugstuurde, en rapport en dashboard hadden geen
tijdsgrens aan de serverkant. Een hangende modelaanroep (tot request_timeout, 1200 s) hield de runplaats bezet, en elke
nieuwe vraag kreeg "Er loopt nog een antwoord", ook nadat de frontend na 10 min zelf had opgegeven."""

import asyncio
import time

import pytest

from agent import dashboard, report
from agent import loop as loop_module
from routes import chat


class _Hangt:
    """Een modelaanroep die nooit de eerste byte krijgt; onthoudt of hij geannuleerd werd."""

    def __init__(self):
        self.gestart = asyncio.Event()
        self.geannuleerd = False

    async def __call__(self, *args, **kwargs):
        self.gestart.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.geannuleerd = True
            raise


@pytest.fixture
def hangt(monkeypatch):
    aanroep = _Hangt()
    monkeypatch.setattr(loop_module, "acompletion_with_backoff", aanroep)
    return aanroep


def _verzamel():
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    return events, emit


def test_stop_breekt_een_hangende_modelaanroep_af(hangt):
    stop = asyncio.Event()
    _, emit = _verzamel()

    async def scenario():
        taak = asyncio.create_task(
            loop_module.tool_loop(
                [{"role": "user", "content": "vraag"}],
                model="openai/gpt-4o",
                tools=[],
                emit=emit,
                stop_event=stop,
                max_iterations=3,
                max_result_chars=1000,
            )
        )
        await hangt.gestart.wait()
        begin = time.monotonic()
        stop.set()
        result = await asyncio.wait_for(taak, timeout=2)
        return result, time.monotonic() - begin

    result, duur = asyncio.run(scenario())

    assert result.aborted == "stream"
    assert duur < 0.5
    assert hangt.geannuleerd


def test_afbreken_van_buitenaf_neemt_de_modelaanroep_mee(hangt):
    """Een reset of ander gesprek breekt de taak af: de modelaanroep mag dan niet blijven lopen."""
    _, emit = _verzamel()

    async def scenario():
        taak = asyncio.create_task(
            loop_module.tool_loop(
                [{"role": "user", "content": "vraag"}],
                model="openai/gpt-4o",
                tools=[],
                emit=emit,
                stop_event=asyncio.Event(),
                max_iterations=3,
                max_result_chars=1000,
            )
        )
        await hangt.gestart.wait()
        taak.cancel()
        with pytest.raises(asyncio.CancelledError):
            await taak
        await asyncio.sleep(0)

    asyncio.run(scenario())
    assert hangt.geannuleerd


def _rapport_met_data(monkeypatch):
    monkeypatch.setattr(report, "build_dataset_context", lambda session: {"datasets": [{"data_key": "k"}]})
    monkeypatch.setattr(report, "_build_system_prompt", lambda context: "")


def test_annuleer_tijdens_een_hangende_aanroep_maakt_de_verbinding_binnen_seconden_vrij(hangt, monkeypatch):
    _rapport_met_data(monkeypatch)
    gevraagd: list[str] = []

    async def opnemen(content, session, emit, model):
        gevraagd.append(content)

    monkeypatch.setattr(chat, "_process_message", opnemen)
    session = chat._new_session(username="u")
    events, emit = _verzamel()

    async def scenario():
        taak = await chat.ACTIES["generate_report"]({"action": "generate_report"}, session, emit, None)
        assert taak is not None
        await asyncio.wait_for(hangt.gestart.wait(), timeout=2)
        await chat.ACTIES["stop"]({"action": "stop"}, session, emit, taak)
        await asyncio.wait_for(taak, timeout=2)
        nieuw = await chat.ACTIES["message"]({"action": "message", "content": "Een nieuwe vraag"}, session, emit, taak)
        assert nieuw is not None
        await nieuw

    asyncio.run(scenario())

    soorten = [e["type"] for e in events]
    assert "report_cancelled" in soorten
    assert "busy" not in soorten
    assert gevraagd == ["Een nieuwe vraag"]
    assert hangt.geannuleerd


def test_een_rapport_boven_de_tijdsgrens_eindigt_met_report_error_en_herstel(monkeypatch):
    monkeypatch.setattr(chat, "GENEREER_TIMEOUT_S", 0.05)

    async def hangt_lang(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(chat, "generate_report_spec", hangt_lang)
    events, emit = _verzamel()

    asyncio.run(asyncio.wait_for(chat._generate_report({"username": "u"}, emit, model=None), timeout=2))

    assert [e["type"] for e in events] == ["report_generating", "report_error"]
    assert events[-1]["herstel"] == "rapport"
    assert events[-1]["message"].startswith("Het rapport kwam niet binnen")


def test_een_time_out_binnen_het_rapport_is_niet_de_grens(monkeypatch):
    """Een TimeoutError uit een bron is een gewone fout: geen melding over de tijdsgrens en geen herstel."""

    async def bron_time_out(*args, **kwargs):
        raise TimeoutError("bron")

    monkeypatch.setattr(chat, "generate_report_spec", bron_time_out)
    events, emit = _verzamel()

    asyncio.run(chat._generate_report({"username": "u"}, emit, model=None))

    assert events[-1] == {"type": "report_error", "message": "Rapport kon niet worden gemaakt. Probeer het opnieuw."}


def _dashboard_met_data(monkeypatch):
    monkeypatch.setattr(dashboard, "build_dataset_context", lambda session: {"datasets": [{"data_key": "k"}]})
    monkeypatch.setattr(dashboard, "_build_system_prompt", lambda context: "")


def test_de_stop_actie_stopt_een_dashboardgeneratie(hangt, monkeypatch):
    _dashboard_met_data(monkeypatch)
    session = chat._new_session(username="u")
    events, emit = _verzamel()

    async def scenario():
        taak = asyncio.create_task(chat._generate_dashboard(session, emit, model=None))
        await asyncio.wait_for(hangt.gestart.wait(), timeout=2)
        await chat.ACTIES["stop"]({"action": "stop"}, session, emit, taak)
        await asyncio.wait_for(taak, timeout=2)

    asyncio.run(scenario())

    assert events == [{"type": "dashboard_generating"}, {"type": "error", "message": "Het dashboard is gestopt."}]
    assert hangt.geannuleerd


def test_een_dashboard_boven_de_tijdsgrens_eindigt_met_een_melding(hangt, monkeypatch):
    _dashboard_met_data(monkeypatch)
    monkeypatch.setattr(chat, "GENEREER_TIMEOUT_S", 0.05)
    events, emit = _verzamel()

    asyncio.run(
        asyncio.wait_for(chat._generate_dashboard(chat._new_session(username="u"), emit, model=None), timeout=2)
    )

    assert events[-1]["type"] == "error"
    assert events[-1]["message"].startswith("Het dashboard kwam niet binnen")
