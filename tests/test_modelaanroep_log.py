"""Een logregel per modelaanroep, om de time-out per aanroep op meting te kiezen (#800).

LITELLM_REQUEST_TIMEOUT (1200 s) ligt boven elke grens per run, zodat een nieuwe poging na een time-out er nooit in
past. Een lagere waarde kan alleen op meting: hoe lang een gewone aanroep duurt tot de provider antwoordt, tot de
eerste chunk en tot het einde. De regel bevat geen gebruikerstekst.
"""

import asyncio
import importlib
import logging
import re
from types import SimpleNamespace

import litellm
import pytest

from agent import ratelimit
from agent import stream as stream_module
from agent import timebox as timebox_module
from agent.stream import accumulate_stream

loop_module = importlib.import_module("agent.loop")


class _Klok:
    """Een nepklok voor time.monotonic() in agent.loop en agent.stream; asyncio houdt zijn eigen klok."""

    def __init__(self, *tijden: float):
        self.tijden = list(tijden)

    def monotonic(self) -> float:
        return self.tijden.pop(0)


def _chunk(content=None, finish_reason=None, usage=None):
    delta = SimpleNamespace(content=content, tool_calls=None)
    chunk = SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish_reason)])
    if usage is not None:
        chunk._hidden_params = {"usage": usage}
    return chunk


async def _stream(*chunks):
    for c in chunks:
        yield c


def _run(monkeypatch, completion, klok: _Klok):
    monkeypatch.setattr(loop_module, "acompletion_with_backoff", completion)
    monkeypatch.setattr(loop_module, "time", klok)
    monkeypatch.setattr(stream_module, "time", klok)

    async def emit(event):
        pass

    return asyncio.run(
        loop_module.tool_loop(
            [{"role": "user", "content": "Hoeveel studenten had de HvA geheim?"}],
            model="azure_ai/claude-sonnet-5-5",
            tools=[],
            emit=emit,
            max_iterations=3,
            max_result_chars=1000,
        )
    )


def _regels(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("MODELAANROEP")]


def test_de_stream_onthoudt_wanneer_de_eerste_chunk_kwam(monkeypatch):
    monkeypatch.setattr(stream_module, "time", _Klok(12.5))
    sr = asyncio.run(accumulate_stream(_stream(_chunk("Ja"), _chunk(" hoor", "stop"))))
    assert sr.eerste_chunk == 12.5


def test_zonder_chunks_geen_eerste_chunk():
    assert asyncio.run(accumulate_stream(_stream())).eerste_chunk is None


def test_een_aanroep_logt_open_eerste_chunk_totaal_en_uitvoer_zonder_gebruikerstekst(monkeypatch, caplog):
    usage = SimpleNamespace(prompt_tokens=900, completion_tokens=42)

    async def completion(emit, **kwargs):
        return _stream(_chunk("Het waren er veel.", "stop", usage=usage))

    # start, open, eerste chunk, einde
    with caplog.at_level(logging.INFO, logger="agent.loop"):
        _run(monkeypatch, completion, _Klok(100.0, 101.5, 104.0, 109.5))

    assert _regels(caplog) == [
        "MODELAANROEP  model=azure_ai/claude-sonnet-5-5  uitkomst=ok  open=1.5s  eerste_chunk=4.0s  totaal=9.5s  uitvoer=42"
    ]
    assert not any("geheim" in r or "veel" in r for r in _regels(caplog))


def test_een_fout_logt_het_type_en_gaat_door_naar_de_aanroeper(monkeypatch, caplog):
    async def completion(emit, **kwargs):
        raise litellm.Timeout("traag", model="m", llm_provider="azure_ai")

    with caplog.at_level(logging.INFO, logger="agent.loop"), pytest.raises(litellm.Timeout):
        _run(monkeypatch, completion, _Klok(50.0, 80.0))

    assert _regels(caplog) == [
        "MODELAANROEP  model=azure_ai/claude-sonnet-5-5  uitkomst=Timeout  open=-  eerste_chunk=-  totaal=30.0s  uitvoer=0"
    ]


def test_de_time_outwaarschuwing_zegt_hoe_lang_de_poging_liep(monkeypatch, caplog):
    pogingen = iter([litellm.Timeout("traag", model="m", llm_provider="azure_ai"), None])

    async def acompletion(**_):
        fout = next(pogingen)
        if fout:
            raise fout
        return "ok"

    async def slaap(_sec):
        pass

    monkeypatch.setattr(ratelimit.litellm, "acompletion", acompletion)
    monkeypatch.setattr(ratelimit.asyncio, "sleep", slaap)
    monkeypatch.setattr(ratelimit, "time", _Klok(10.0, 610.0, 612.0))

    async def emit(_event):
        pass

    with caplog.at_level(logging.WARNING, logger=ratelimit.__name__):
        assert asyncio.run(ratelimit.acompletion_with_backoff(emit)) == "ok"

    assert [r.getMessage() for r in caplog.records] == [
        f"Model timeout (poging 1/{ratelimit._MAX_RETRIES}) na 600s: wacht 2 seconden"
    ]


# Een aanroep die de harde afbraak trof, logde `uitkomst=ok` (meting 04-11 op #800): de CancelledError viel buiten
# `except Exception`. Zo'n aanroep moet in de meting zichtbaar zijn, met de duur tot de afbraak, en de annulering moet
# gewoon doorgaan.

_UITKOMST = re.compile(r"uitkomst=(\S+)  open=(\S+)  eerste_chunk=(\S+)  totaal=(\d+\.\ds)  uitvoer=0$")


async def _hangt_in_de_stream():
    """Een stream die de headers had maar nooit een chunk stuurt: het stopsignaal ziet hij niet."""
    await asyncio.Event().wait()
    yield  # pragma: no cover


async def _opent_maar_hangt(emit, **kwargs):
    return _hangt_in_de_stream()


async def _hangt_voor_de_headers(emit, **kwargs):
    await asyncio.Event().wait()


def _uitkomsten(caplog) -> list[tuple[str, ...]]:
    gevonden = [_UITKOMST.search(r) for r in _regels(caplog)]
    assert all(gevonden), _regels(caplog)
    return [m.groups() for m in gevonden if m]


def test_de_harde_afbraak_na_de_rungrens_logt_afgebroken_runlimiet(monkeypatch, caplog):
    """De chat: de grens zet het stopsignaal, de vastzittende stream ziet het niet, `afbreken_s` breekt hem af."""
    run_module = importlib.import_module("agent.run")
    monkeypatch.setattr(loop_module, "acompletion_with_backoff", _opent_maar_hangt)
    monkeypatch.setattr(run_module, "RUN_SLOW_S", 5)
    monkeypatch.setattr(run_module, "RUN_TIMEOUT_S", 0.05)
    monkeypatch.setattr(timebox_module, "_UITLOOP_S", 0.05)
    # Geen kaart en geen profiel uit het register: alleen de modelaanroep telt hier.
    monkeypatch.setattr(run_module, "scopevraag", lambda vraag, settings, eerder=(): None)
    monkeypatch.setattr(run_module, "build_system", lambda settings, beurt: [])
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    vraag = [{"role": "user", "content": "Hoeveel studenten had de HvA geheim?"}]
    with caplog.at_level(logging.INFO, logger="agent.loop"):
        asyncio.run(asyncio.wait_for(run_module.run(vraag, session={}, emit=emit), timeout=5))

    [(uitkomst, open_, eerste_chunk, totaal)] = _uitkomsten(caplog)
    assert (uitkomst, eerste_chunk) == ("afgebroken_runlimiet", "-")
    assert open_ != "-"
    assert float(totaal.rstrip("s")) >= 0.05  # voorbij de grens, tot de afbraak
    assert events[-1]["timeout"] is True
    assert not any("geheim" in r for r in _regels(caplog))


def test_de_grens_van_het_rapport_logt_afgebroken_runlimiet(monkeypatch, caplog):
    """Het rapport heeft geen stopsignaal van de grens: GENEREER_TIMEOUT_S breekt de aanroep vóór de headers af."""
    from agent import report
    from routes import chat

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", _hangt_voor_de_headers)
    monkeypatch.setattr(report, "build_dataset_context", lambda session: {"datasets": [{"data_key": "k"}]})
    monkeypatch.setattr(report, "_build_system_prompt", lambda context: "")
    monkeypatch.setattr(chat, "GENEREER_TIMEOUT_S", 0.2)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    with caplog.at_level(logging.INFO, logger="agent.loop"):
        asyncio.run(asyncio.wait_for(chat._generate_report(chat._new_session(username="u"), emit, None), timeout=5))

    [(uitkomst, open_, _, totaal)] = _uitkomsten(caplog)
    assert (uitkomst, open_) == ("afgebroken_runlimiet", "-")
    assert float(totaal.rstrip("s")) >= 0.1
    assert events[-1]["herstel"] == "rapport"


def test_een_annulering_van_buitenaf_logt_geannuleerd_en_gaat_door(monkeypatch, caplog):
    """Een gesloten WebSocket, reset of ander gesprek annuleert de taak: geen grens, en de CancelledError blijft."""
    monkeypatch.setattr(loop_module, "acompletion_with_backoff", _opent_maar_hangt)

    async def emit(event):
        pass

    async def scenario():
        taak = asyncio.create_task(
            loop_module.tool_loop(
                [{"role": "user", "content": "vraag"}],
                model="azure_ai/claude-sonnet-5-5",
                tools=[],
                emit=emit,
                stop_event=asyncio.Event(),
                max_iterations=3,
                max_result_chars=1000,
            )
        )
        await asyncio.sleep(0.2)
        taak.cancel()
        with pytest.raises(asyncio.CancelledError):
            await taak

    with caplog.at_level(logging.INFO, logger="agent.loop"):
        asyncio.run(scenario())

    [(uitkomst, open_, eerste_chunk, totaal)] = _uitkomsten(caplog)
    assert (uitkomst, eerste_chunk) == ("geannuleerd", "-")
    assert open_ != "-"
    assert float(totaal.rstrip("s")) >= 0.1
