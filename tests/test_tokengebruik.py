"""Tokengebruik per run in het log, aan een gebruiker te koppelen (#678).

Er werd niets gelogd van wat een run kostte, dus geen kostenattributie en geen budgetbewaking. LiteLLM meldt
het gebruik op de laatste chunk: als `usage` met `stream_options.include_usage`, anders in
`_hidden_params["usage"]`. Anthropic en Azure AI kennen `stream_options` niet (drop_params laat het vallen),
dus de app leest beide.
"""

import asyncio
import importlib
import json
import logging
from types import SimpleNamespace

from agent.stream import Tokens, accumulate_stream
from core import logging_util

loop_module = importlib.import_module("agent.loop")


def _chunk(content=None, finish_reason=None, usage=None, verborgen=None, choices=True):
    delta = SimpleNamespace(content=content, tool_calls=None)
    chunk = SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish_reason)] if choices else [])
    if usage is not None:
        chunk.usage = usage
    if verborgen is not None:
        chunk._hidden_params = {"usage": verborgen}
    return chunk


def _usage(invoer, uitvoer, gelezen=0, geschreven=0):
    return SimpleNamespace(
        prompt_tokens=invoer,
        completion_tokens=uitvoer,
        cache_read_input_tokens=gelezen,
        cache_creation_input_tokens=geschreven,
    )


async def _stream(*chunks):
    for c in chunks:
        yield c


def test_het_gebruik_uit_de_verborgen_parameters_van_de_laatste_chunk():
    sr = asyncio.run(
        accumulate_stream(_stream(_chunk("Ant"), _chunk("woord", "stop", verborgen=_usage(1200, 80, gelezen=1000))))
    )
    assert sr.text == "Antwoord"
    assert sr.tokens == Tokens(invoer=1200, uitvoer=80, cache_gelezen=1000, cache_geschreven=0)


def test_een_chunk_met_alleen_gebruik_en_zonder_keuzes():
    """Met include_usage stuurt LiteLLM na de laatste tekst een chunk met `choices=[]`."""
    sr = asyncio.run(accumulate_stream(_stream(_chunk("Ja", "stop"), _chunk(choices=False, usage=_usage(10, 2)))))
    assert sr.text == "Ja"
    assert sr.tokens == Tokens(invoer=10, uitvoer=2)


def test_zonder_gemeld_gebruik_nul():
    sr = asyncio.run(accumulate_stream(_stream(_chunk("Ja", "stop"))))
    assert sr.tokens == Tokens()


def test_tokens_tellen_op():
    assert Tokens(1, 2, 3, 4) + Tokens(10, 20, 30, 40) == Tokens(11, 22, 33, 44)


def test_een_run_logt_het_totaal_over_alle_modelaanroepen(monkeypatch, caplog):
    antwoorden = iter(
        [
            # Eerst een toolaanroep, dan het antwoord: twee modelaanroepen in één run.
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=0, id="t1", function=SimpleNamespace(name="echo", arguments="{}")
                                    )
                                ],
                            ),
                            finish_reason="tool_calls",
                        )
                    ],
                    _hidden_params={"usage": _usage(1000, 50, gelezen=900)},
                )
            ],
            [_chunk("Klaar", "stop", verborgen=_usage(1100, 30, gelezen=1000, geschreven=100))],
        ]
    )

    async def fake_completion(emit, **kwargs):
        return _stream(*next(antwoorden))

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)

    async def emit(event):
        pass

    monkeypatch.setattr(loop_module, "dispatch", lambda name, args: (json.dumps({"ok": True}), None))
    tools = [{"type": "function", "function": {"name": "echo", "parameters": {"type": "object"}}}]
    with caplog.at_level(logging.INFO, logger="agent.loop"):
        result = asyncio.run(
            loop_module.tool_loop(
                [{"role": "user", "content": "vraag"}],
                model="azure_ai/claude-sonnet-5-5",
                tools=tools,
                emit=emit,
                max_iterations=3,
                max_result_chars=1000,
            )
        )
    assert result.tokens == Tokens(invoer=2100, uitvoer=80, cache_gelezen=1900, cache_geschreven=100)
    regels = [r.getMessage() for r in caplog.records if r.getMessage().startswith("TOKENS")]
    assert regels == [
        "TOKENS  model=azure_ai/claude-sonnet-5-5  aanroepen=2  invoer=2100  uitvoer=80  "
        "cache_gelezen=1900  cache_geschreven=100"
    ]


def test_gebruikerskenmerk_alleen_met_een_geheim(monkeypatch):
    """Een gebruikersnaam is te raden; een kale SHA-256 ervan is dus geen pseudoniem."""
    monkeypatch.setattr(logging_util, "_SECRET", b"")
    assert logging_util.gebruiker_kenmerk("docent@hva.nl") == "-"
    monkeypatch.setattr(logging_util, "_SECRET", b"geheim")
    kenmerk = logging_util.gebruiker_kenmerk("docent@hva.nl")
    assert len(kenmerk) == 8 and "docent" not in kenmerk
    assert kenmerk == logging_util.gebruiker_kenmerk("docent@hva.nl")
    assert logging_util.gebruiker_kenmerk(None) == "-"
