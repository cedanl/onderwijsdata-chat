"""Tokengebruik per run in het log, aan een gebruiker te koppelen (#678).

Er werd niets gelogd van wat een run kostte, dus geen kostenattributie en geen budgetbewaking. LiteLLM meldt
het gebruik op de laatste chunk: als `usage` met `stream_options.include_usage`, anders in
`_hidden_params["usage"]`; de app leest beide. Bij streaming zijn de cachevelden bovenin leeg en staat de cache
alleen in `prompt_tokens_details` (#1027).
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


def _streaminggebruik(invoer, uitvoer, details):
    """Zoals LiteLLM het gebruik bij streaming meldt: de cachevelden bovenin leeg, de cache in de details (#1027)."""
    return SimpleNamespace(
        prompt_tokens=invoer,
        completion_tokens=uitvoer,
        cache_read_input_tokens=None,
        cache_creation_input_tokens=None,
        prompt_tokens_details=details,
    )


def _tokens_van(usage):
    return asyncio.run(accumulate_stream(_stream(_chunk("Ja", "stop", verborgen=usage)))).tokens


def test_bij_streaming_komt_de_gelezen_cache_uit_de_details():
    usage = _streaminggebruik(34620, 412, SimpleNamespace(cached_tokens=34535))
    assert _tokens_van(usage) == Tokens(invoer=34620, uitvoer=412, cache_gelezen=34535, cache_geschreven=0)


def test_gebruik_en_details_als_gewone_dicts():
    usage = {
        "prompt_tokens": 34620,
        "completion_tokens": 412,
        "cache_read_input_tokens": None,
        "cache_creation_input_tokens": None,
        "prompt_tokens_details": {"cached_tokens": 34535, "cache_write_tokens": 85},
    }
    assert _tokens_van(usage) == Tokens(invoer=34620, uitvoer=412, cache_gelezen=34535, cache_geschreven=85)


def test_details_als_dict_in_een_gebruiksobject():
    usage = _streaminggebruik(500, 20, {"cached_tokens": 400})
    assert _tokens_van(usage) == Tokens(invoer=500, uitvoer=20, cache_gelezen=400)


def test_geschreven_cache_uit_cache_write_tokens():
    usage = _streaminggebruik(2000, 10, SimpleNamespace(cached_tokens=0, cache_write_tokens=1800))
    assert _tokens_van(usage) == Tokens(invoer=2000, uitvoer=10, cache_geschreven=1800)


def test_geschreven_cache_uit_cache_creation_tokens():
    """Oudere LiteLLM-versies noemen het veld `cache_creation_tokens`."""
    usage = _streaminggebruik(2000, 10, SimpleNamespace(cached_tokens=0, cache_creation_tokens=1700))
    assert _tokens_van(usage) == Tokens(invoer=2000, uitvoer=10, cache_geschreven=1700)


def test_cache_write_tokens_gaat_voor_cache_creation_tokens():
    details = SimpleNamespace(cached_tokens=0, cache_write_tokens=1800, cache_creation_tokens=1700)
    assert _tokens_van(_streaminggebruik(2000, 10, details)).cache_geschreven == 1800


def test_de_velden_bovenin_gaan_voor_de_details():
    """Beide beschrijven dezelfde tokens: bovenin wint, ook een echte 0, en er wordt nooit opgeteld."""
    usage = _usage(1200, 80, gelezen=1000, geschreven=0)
    usage.prompt_tokens_details = SimpleNamespace(cached_tokens=999, cache_write_tokens=7)
    assert _tokens_van(usage) == Tokens(invoer=1200, uitvoer=80, cache_gelezen=1000, cache_geschreven=0)


def test_zonder_details_geen_cache():
    assert _tokens_van(_streaminggebruik(300, 5, None)) == Tokens(invoer=300, uitvoer=5)
    zonder_veld = SimpleNamespace(prompt_tokens=300, completion_tokens=5)
    assert _tokens_van(zonder_veld) == Tokens(invoer=300, uitvoer=5)
    assert _tokens_van({"prompt_tokens": 300, "completion_tokens": 5}) == Tokens(invoer=300, uitvoer=5)


def test_details_met_lege_velden_geven_nul():
    details = SimpleNamespace(cached_tokens=None, cache_write_tokens=None, cache_creation_tokens=None)
    assert _tokens_van(_streaminggebruik(300, 5, details)) == Tokens(invoer=300, uitvoer=5)


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
    geboekt = []  # wat de run meetelt voor het tokenbudget van de gebruiker (#678)
    monkeypatch.setattr(loop_module.tokenbudget, "boek", geboekt.append)
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
    assert geboekt == [result.tokens], "het totaal van de run telt één keer mee voor het budget"
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
