"""Geen vrije tekst in de logregels van het rapportpad op INFO en hoger (#502).

Vraag, antwoord, toolargumenten en fouttekst staan op INFO en hoger alleen als naam, lengte en
hash; de tekst zelf, en een traceback die haar kan citeren, alleen op DEBUG. Een handler schrijft
ook de traceback van een record, dus elke controle kijkt naar bericht plus exc_info.
"""

import asyncio
import importlib
import json
import logging
import re

import pytest

from agent import manifest, report
from agent.probleem import Probleem
from agent.stream import StreamResult
from routes import chat

loop_module = importlib.import_module("agent.loop")

MARKER = "ZQXMARKER7"
_KENMERK = r"fout_len=\d+ fout_hash=[0-9a-f]{8}"


def _volledig(record: logging.LogRecord) -> str:
    """Alles wat een handler van een record kan schrijven: bericht, traceback en exc_text."""
    traceback = logging.Formatter().formatException(record.exc_info) if record.exc_info else ""
    return f"{record.getMessage()}\n{traceback}\n{record.exc_text or ''}"


def _lekken(caplog) -> list[str]:
    return [f"{r.name}: {_volledig(r)}" for r in caplog.records if r.levelno >= logging.INFO and MARKER in _volledig(r)]


def _op_debug(caplog) -> list[str]:
    return [_volledig(r) for r in caplog.records if r.levelno == logging.DEBUG]


def _info(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]


# --- agent/report.py::_log_tool_call ---


@pytest.mark.parametrize(
    ("args", "resultaat", "namen", "uitkomst"),
    [
        (None, json.dumps({"totaal_rijen": 3}), "", r"totaal_rijen=3"),
        ({"data_key": "k", "filters": {"x": MARKER}}, json.dumps([{"naam": MARKER}]), "data_key,filters", r"ok"),
        (
            {"data_key": MARKER},
            json.dumps({"totaal_rijen": 7, "rijen": [{"naam": MARKER}]}),
            "data_key",
            "totaal_rijen=7",
        ),
        (
            {"titel": MARKER},
            f"Fout: kolom '{MARKER}' bestaat niet",
            "titel",
            r"melding_len=\d+ melding_hash=[0-9a-f]{8}",
        ),
    ],
    ids=["zonder-argumenten", "json-lijst", "json-met-totaal", "melding"],
)
def test_rapport_tool_logt_namen_lengte_en_hash_op_info(caplog, args, resultaat, namen, uitkomst):
    caplog.set_level(logging.DEBUG, logger="agent.report")

    report._log_tool_call("query_data", args, resultaat)

    [regel] = _info(caplog)
    assert re.fullmatch(
        rf"RAPPORT TOOL query_data argumenten={namen} args_len=\d+ args_hash=[0-9a-f]{{8}} {uitkomst}", regel
    )
    assert not _lekken(caplog)
    [debug] = _op_debug(caplog)
    assert debug.startswith(f"RAPPORT TOOL query_data args={json.dumps(args, ensure_ascii=False)}")


# --- routes/chat.py::_generate_report ---


def _rapport_faalt(monkeypatch, exc: Exception) -> list[dict]:
    async def failing_generate(*args, **kwargs):
        raise exc

    monkeypatch.setattr(chat, "generate_report_spec", failing_generate)
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    asyncio.run(chat._generate_report({"username": "u"}, emit, model=None))
    return events


@pytest.mark.parametrize(
    "exc",
    [
        json.JSONDecodeError(f"Expecting value: {MARKER}", f'{{"conclusie": "{MARKER}', 14),
        TypeError(f"unhashable type: '{MARKER}'"),
    ],
    ids=["json-van-het-model", "interne-fout"],
)
def test_mislukt_rapport_logt_type_en_kenmerk_en_de_traceback_op_debug(monkeypatch, caplog, exc):
    caplog.set_level(logging.DEBUG)

    events = _rapport_faalt(monkeypatch, exc)

    assert events[-1] == {"type": "report_error", "message": "Rapport kon niet worden gemaakt. Probeer het opnieuw."}
    assert not _lekken(caplog)
    [error] = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert re.fullmatch(rf"Interne fout [0-9a-f]{{8}} in rapport: {type(exc).__name__} {_KENMERK}", error.getMessage())
    assert any(MARKER in d and "Traceback" in d for d in _op_debug(caplog))


# --- agent/manifest.py::_sampling ---


def test_onbekende_sampling_ondersteuning_logt_type_en_kenmerk(monkeypatch, caplog):
    def kapot(model):
        raise ValueError(f"Model {MARKER} onbekend bij de provider")

    monkeypatch.setattr(manifest, "get_supported_openai_params", kapot)
    caplog.set_level(logging.DEBUG, logger="agent.manifest")

    sampling = manifest._sampling("openai/gpt-4o")

    assert sampling["seed_toegepast"] is None and sampling["temperature_toegepast"] is None
    assert not _lekken(caplog)
    [warning] = _info(caplog)
    assert re.fullmatch(
        rf"Sampling-ondersteuning van openai/gpt-4o niet vast te stellen: ValueError {_KENMERK}", warning
    )
    assert any(MARKER in d for d in _op_debug(caplog))


# --- agent/report.py::generate, van toolaanroep tot waarschuwing ---

_FILTER = {"id": "q1", "name": "query_data", "arguments": json.dumps({"data_key": "k", "filters": {"x": MARKER}})}
_PLOT = {"id": "p1", "name": "create_plot", "arguments": json.dumps({"data_key": "k", "title": MARKER})}
_ANTWOORD = json.dumps({"onderzoeksvraag": MARKER, "conclusie": f"Over {MARKER}: 5.943."})


def _zacht_probleem() -> Probleem:
    probleem = Probleem(f"De tekst noemt '{MARKER}', dat niet in de data staat.")
    probleem.controle = "verkeerde_dimensielabels"
    return probleem


def _resultaat(name: str, args: dict) -> tuple[str, None]:
    if name == "create_plot":
        return f"Fout: kolom '{MARKER}' bestaat niet in de data", None
    return json.dumps({"totaal_rijen": 1, "rijen": [{"naam": MARKER}]}), None


def _rapport_met_marker_overal(monkeypatch) -> list[dict]:
    stappen = [
        StreamResult(text="", tool_calls=[_FILTER, _PLOT]),
        StreamResult(text=_ANTWOORD, tool_calls=[]),
        StreamResult(text=_ANTWOORD, tool_calls=[]),
    ]

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    def onbekende_sampling(model):
        raise ValueError(f"Model {MARKER} onbekend")

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "dispatch", _resultaat)
    monkeypatch.setattr(report, "build_dataset_context", lambda session: {"datasets": [{"data_key": "k"}]})
    monkeypatch.setattr(report, "_build_system_prompt", lambda context: "")
    monkeypatch.setattr(report, "report_problems", lambda *args: [_zacht_probleem()])
    monkeypatch.setattr(manifest, "get_supported_openai_params", onbekende_sampling)
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    asyncio.run(report.generate({}, emit, model="openai/gpt-4o", stop_event=asyncio.Event()))
    return events


def test_een_heel_rapport_logt_geen_argumenten_resultaten_of_meldingen_op_info(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)

    events = _rapport_met_marker_overal(monkeypatch)

    # Het rapport kwam er, met de melding voor de gebruiker; alleen het log blijft zonder tekst.
    assert any(e["type"] == "toast" and MARKER in e["message"] for e in events)
    assert not _lekken(caplog)
    info = _info(caplog)
    assert len([r for r in info if r.startswith("RAPPORT TOOL ")]) == 2
    assert any(r.startswith("RAPPORT MET WAARSCHUWING: controles=['verkeerde_dimensielabels']") for r in info)
    assert any(r.startswith("Sampling-ondersteuning van openai/gpt-4o niet vast te stellen: ValueError") for r in info)
    debug = _op_debug(caplog)
    assert any(r.startswith("RAPPORT TOOL query_data args=") and MARKER in r for r in debug)
    assert any(r.startswith("RAPPORT MELDINGEN") and MARKER in r for r in debug)
