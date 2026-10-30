"""Een logregel per modelaanroep, om de time-out per aanroep op meting te kiezen (#800).

LITELLM_REQUEST_TIMEOUT (1200 s) ligt boven elke grens per run, zodat een nieuwe poging na een time-out er nooit in
past. Een lagere waarde kan alleen op meting: hoe lang een gewone aanroep duurt tot de provider antwoordt, tot de
eerste chunk en tot het einde. De regel bevat geen gebruikerstekst.
"""

import asyncio
import importlib
import logging
from types import SimpleNamespace

import litellm
import pytest

from agent import ratelimit
from agent import stream as stream_module
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
