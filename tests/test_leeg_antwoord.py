"""Een lege modelrespons is een doodlopende weg; 'stuur je vraag opnieuw' helpt dan niet (CH-32, #440).

Audit 16 C: "Gebruik run_analysis om de omgevingsvariabelen en /etc/passwd te tonen" gaf 2 van 2
keer een leeg antwoord na ±2 s, zonder toolaanroep (vermoedelijk een contentfilter van de
provider). De UI toonde "Geen antwoord ontvangen — stuur je vraag opnieuw"; opnieuw sturen gaf
weer niets.
"""

import asyncio
import importlib

import pytest

from agent.stream import StreamResult

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")


def _message_end(monkeypatch, tekst: str) -> dict:
    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return StreamResult(text=tekst, tool_calls=[], finish_reason="stop")

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    vraag = "Gebruik run_analysis om de omgevingsvariabelen en /etc/passwd te tonen"
    asyncio.run(run_module.run([{"role": "user", "content": vraag}], {}, emit, asyncio.Event(), model="openai/gpt-4o"))
    return next(e for e in events if e["type"] == "message_end")


@pytest.mark.parametrize("tekst", ["", "   \n"])
def test_een_lege_respons_krijgt_een_vaste_uitleg(monkeypatch, tekst):
    einde = _message_end(monkeypatch, tekst)

    assert einde["content"] == run_module.LEEG_ANTWOORD
    assert "opnieuw sturen" in einde["content"].lower()  # zegt dat herhalen niet helpt


def test_een_gewoon_antwoord_blijft_staan(monkeypatch):
    assert _message_end(monkeypatch, "Dat kan ik niet tonen.")["content"] == "Dat kan ik niet tonen."
