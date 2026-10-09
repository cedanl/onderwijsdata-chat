"""Geen vraag- of antwoordtekst in het log op default-niveau (#475).

Het stdout-log gaat naar de logaggregatie, buiten "gesprek verwijderen" om. Op INFO
en hoger staan daarom alleen model, lengtes en een korte hash; de tekst zelf alleen
op DEBUG.
"""

import asyncio
import hashlib
import importlib
import json
import logging
import re
from unittest.mock import patch

from agent import dashboard, report
from agent.loop import ToolCall
from agent.probleem import INGEHOUDEN
from agent.stream import StreamResult
from core.logging_util import tekst_kenmerk

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

MARKER = "ZQXMARKER7"
_ROWS = json.dumps({"data_key": "duo:p02:a", "rijen": [{"AANTAL": 5943}]})
_ZOEK = {"id": "z", "name": "search_catalog", "arguments": json.dumps({"query": f"{MARKER} hbo", "source": "duo"})}
_QUERY = {"id": "q", "name": "query_data", "arguments": '{"data_key": "duo:p02"}'}
_DUO = [{"leverancier": "DUO", "bron": f"{MARKER} ingeschrevenen hbo", "tags": ["hbo"]}]


def _run(monkeypatch, steps: list[StreamResult], vraag: str) -> str:
    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    real_execute = loop_module._execute_tool

    async def execute(call, emit):
        if call.name == "search_catalog":
            return await real_execute(call, emit)
        return _ROWS, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", execute)

    async def emit(event):
        pass

    with patch("tools.catalog._cbs", return_value=[]), patch("tools.catalog._rio_duo", return_value=_DUO):
        return asyncio.run(
            run_module.run([{"role": "user", "content": vraag}], {}, emit, asyncio.Event(), model="openai/gpt-4o")
        )


def _zonder_marker(caplog) -> None:
    lekken = [f"{r.name}: {r.getMessage()}" for r in caplog.records if MARKER in r.getMessage()]
    assert not lekken


# --- tekst_kenmerk ---


def test_tekst_kenmerk_is_lengte_en_een_korte_sha256():
    kenmerk = tekst_kenmerk("Hoeveel studenten?")

    assert kenmerk == f"len=18 hash={hashlib.sha256(b'Hoeveel studenten?').hexdigest()[:8]}"
    assert re.fullmatch(r"len=\d+ hash=[0-9a-f]{8}", kenmerk)


def test_tekst_kenmerk_is_deterministisch_en_toont_de_tekst_niet():
    assert tekst_kenmerk(MARKER) == tekst_kenmerk(MARKER)
    assert tekst_kenmerk(MARKER) != tekst_kenmerk(MARKER + "x")
    assert MARKER not in tekst_kenmerk(MARKER)


def test_tekst_kenmerk_met_voorvoegsel():
    assert re.fullmatch(r"vraag_len=3 vraag_hash=[0-9a-f]{8}", tekst_kenmerk("abc", "vraag_"))


def test_tekst_kenmerk_kan_een_losse_surrogaat_aan():
    assert re.fullmatch(r"len=1 hash=[0-9a-f]{8}", tekst_kenmerk("\ud800"))


# --- agent/run.py ---


def test_run_start_logt_lengte_en_hash_maar_niet_de_vraag(monkeypatch, caplog):
    vraag = f"Hoeveel eerstejaars {MARKER}?"
    caplog.set_level(logging.INFO)

    _run(monkeypatch, [StreamResult(text="Daar heb ik geen data voor.", tool_calls=[])], vraag)

    [start] = [r.getMessage() for r in caplog.records if "RUN START" in r.getMessage()]
    assert re.fullmatch(r"RUN START  model=openai/gpt-4o  vraag_len=\d+ vraag_hash=[0-9a-f]{8}", start)
    assert tekst_kenmerk(vraag, "vraag_") in start
    _zonder_marker(caplog)


def test_volledige_run_logt_geen_vraag_of_antwoord_op_info(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    antwoord = f"De dataset {MARKER} is gevonden. Mijn tussenzin over {MARKER} was onjuist."

    tekst = _run(
        monkeypatch,
        [StreamResult(text="", tool_calls=[_ZOEK]), StreamResult(text=antwoord, tool_calls=[])],
        f"Zoek {MARKER} hbo",
    )

    assert MARKER in tekst
    berichten = [r.getMessage() for r in caplog.records]
    assert any(b.startswith("search_catalog ") for b in berichten)
    [finale] = [b for b in berichten if "FINALE ANTWOORD" in b]
    assert re.fullmatch(r"FINALE ANTWOORD  len=\d+ hash=[0-9a-f]{8}", finale)
    [zelf] = [b for b in berichten if "ZELFCORRECTIE" in b]
    assert "herzien=1" in zelf
    _zonder_marker(caplog)


def test_antwoordtekst_staat_alleen_op_debug(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="agent.run")

    _run(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_QUERY]),
            StreamResult(text=f"Over {MARKER}: in totaal 5.943 eerstejaars.", tool_calls=[]),
        ],
        "Hoeveel eerstejaars?",
    )

    debug = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG and MARKER in r.getMessage()]
    assert any("FINALE ANTWOORD TEKST" in b for b in debug)
    assert all(r.levelno < logging.INFO for r in caplog.records if MARKER in r.getMessage())


def test_ingehouden_antwoord_logt_model_lengte_en_hash(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    tekst = _run(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_QUERY]),
            StreamResult(text=f"{MARKER}: in totaal 6.340 eerstejaars.", tool_calls=[]),
            StreamResult(text=f"{MARKER}: toch 6.340.", tool_calls=[]),
        ],
        f"Hoeveel eerstejaars {MARKER}?",
    )

    assert tekst == INGEHOUDEN
    berichten = [r.getMessage() for r in caplog.records]
    [ingehouden] = [b for b in berichten if "ANTWOORD INGEHOUDEN" in b]
    assert re.fullmatch(r"ANTWOORD INGEHOUDEN  model=openai/gpt-4o  len=\d+ hash=[0-9a-f]{8}", ingehouden)
    [controle] = [b for b in berichten if "CONTROLE niet in orde" in b]
    assert "ongedekte_getallen" in controle and "6.340" not in controle
    [mislukt] = [b for b in berichten if "CONTROLE MISLUKT" in b]
    assert "ongedekte_getallen" in mislukt and "6.340" not in mislukt
    _zonder_marker(caplog)


# --- agent/loop.py ---


def test_reproduceer_logt_de_snippet_alleen_op_debug(monkeypatch, caplog):
    monkeypatch.setattr(loop_module, "dispatch", lambda name, args: ("{}", None))
    monkeypatch.setattr(loop_module, "_generate_snippet", lambda name, args, result: f"zoek('{MARKER}')")
    caplog.set_level(logging.INFO)

    async def emit(event):
        pass

    call = ToolCall(id="t", name="search_catalog", arguments="{}", args={"query": MARKER})
    asyncio.run(loop_module._execute_tool(call, emit))

    [reproduceer] = [r.getMessage() for r in caplog.records if "REPRODUCEER" in r.getMessage()]
    assert "search_catalog" in reproduceer and re.search(r"len=\d+ hash=[0-9a-f]{8}", reproduceer)
    _zonder_marker(caplog)


# --- agent/report.py ---


def test_rapport_tool_logt_geen_argumenten_of_melding_op_info(caplog):
    caplog.set_level(logging.INFO, logger="agent.report")

    report._log_tool_call("search_catalog", {"query": MARKER}, f"Geen resultaten voor '{MARKER}'")

    [regel] = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
    assert "RAPPORT TOOL search_catalog" in regel
    assert "argumenten=query" in regel
    assert re.search(r"melding_len=\d+ melding_hash=[0-9a-f]{8}", regel)
    _zonder_marker(caplog)


# --- agent/dashboard.py ---


def test_geweigerde_kpi_logt_geen_label_of_waarde(caplog):
    caplog.set_level(logging.INFO, logger="agent.dashboard")

    assert dashboard._validate_kpis([{"label": MARKER, "value": "42"}], {}) == []

    assert any("KPI geweigerd" in r.getMessage() for r in caplog.records)
    _zonder_marker(caplog)


def test_ongeldige_kpi_json_logt_geen_toolresultaat(caplog):
    caplog.set_level(logging.INFO, logger="agent.dashboard")

    dashboard._collect_kpi({}, f"geen json {MARKER}")

    [regel] = [r.getMessage() for r in caplog.records]
    assert "invalid JSON" in regel and re.search(r"len=\d+ hash=[0-9a-f]{8}", regel)
    _zonder_marker(caplog)
