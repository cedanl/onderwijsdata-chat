"""Vervolg op de log-privacy van #475: gezouten hash, foutregels zonder vrije tekst, een verbindings-ID (#502).

Foutteksten van tools, de sandbox, het herladen en de providers kunnen toolargumenten of
modeltekst citeren; op INFO en hoger staat nu het type en een kenmerk, de tekst op DEBUG.
Elke logregel van een chatverbinding draagt een kort verbindings-ID, zodat regels van één
verbinding te koppelen zijn zonder gebruikersnaam of gespreks-ID.
"""

import contextvars
import importlib
import json
import logging
import re
from unittest.mock import patch

import pytest

from core import logging_util
from core.logging_context import GEEN, VerbindingFilter, nieuwe_verbinding, verbinding
from core.logging_util import foutkenmerk, tekst_kenmerk
from tools import fouten

MARKER = "ZQXMARKER7"


# --- gezouten hash ---


def test_zonder_geheim_is_de_hash_een_kale_sha256():
    assert tekst_kenmerk("abc") == "len=3 hash=ba7816bf"


def test_met_geheim_is_de_hash_een_hmac_en_blijft_het_formaat_gelijk(monkeypatch):
    monkeypatch.setattr(logging_util, "_SECRET", b"geheim")
    gezouten = tekst_kenmerk("abc")
    assert re.fullmatch(r"len=3 hash=[0-9a-f]{8}", gezouten)
    assert gezouten != "len=3 hash=ba7816bf"
    assert gezouten == tekst_kenmerk("abc")
    monkeypatch.setattr(logging_util, "_SECRET", b"ander geheim")
    assert tekst_kenmerk("abc") != gezouten


def test_foutkenmerk_noemt_het_type_en_niet_de_tekst():
    kenmerk = foutkenmerk(ValueError(f"Kolom {MARKER} bestaat niet"))
    assert re.fullmatch(r"ValueError fout_len=\d+ fout_hash=[0-9a-f]{8}", kenmerk)
    assert MARKER not in kenmerk


# --- foutregels ---


def _regels(caplog, niveau: int) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= niveau]


def test_een_bronfout_en_een_toolfout_loggen_geen_fouttekst_op_warning(caplog):
    caplog.set_level(logging.DEBUG)
    fouten.bronfout("CBS", RuntimeError(f"url met {MARKER}"))
    fouten.toolfout("query_data", KeyError(MARKER))
    assert not [r for r in _regels(caplog, logging.WARNING) if MARKER in r]
    assert any(MARKER in r for r in _regels(caplog, logging.DEBUG))
    [warning] = [r for r in _regels(caplog, logging.WARNING) if r.startswith("CBS-fout")]
    assert "RuntimeError fout_len=" in warning


def test_een_toolfout_houdt_de_traceback_op_debug(caplog):
    caplog.set_level(logging.DEBUG)
    try:
        raise KeyError(MARKER)
    except KeyError as e:
        fouten.toolfout("query_data", e)
    [debug] = [r for r in caplog.records if r.levelno == logging.DEBUG and "Tool query_data faalde" in r.getMessage()]
    assert debug.exc_info is not None
    [error] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error.exc_info is None and MARKER not in error.getMessage()


def test_mislukt_herladen_logt_het_type_en_niet_de_argumenten(caplog):
    from tools import herlaad

    caplog.set_level(logging.DEBUG)
    with patch.dict(herlaad._LADERS, {"get_cbs_data": (lambda **kw: (_ for _ in ()).throw(ValueError(MARKER)), "CBS")}):
        uitkomst = herlaad.herlaad("cbs:x", {"laad": ["get_cbs_data", {"dataset_id": MARKER}]})
    assert not uitkomst.gelukt
    assert not [r for r in _regels(caplog, logging.WARNING) if MARKER in r]
    assert any("ValueError fout_len=" in r for r in _regels(caplog, logging.WARNING))


def test_replay_logt_een_mislukte_herlaadstap_zonder_fouttekst(caplog):
    from agent.replay import replay_data_calls

    caplog.set_level(logging.DEBUG)
    with patch("agent.replay.dispatch", side_effect=ValueError(MARKER)):
        [resultaat] = replay_data_calls([{"name": "get_cbs_data", "arguments": "{}"}])
    assert resultaat["success"] is False and MARKER not in json.dumps(resultaat)
    assert not [r for r in _regels(caplog, logging.WARNING) if MARKER in r]
    assert any("Herladen van get_cbs_data mislukt: ValueError fout_len=" in r for r in _regels(caplog, logging.WARNING))
    assert any(r.exc_info for r in caplog.records if r.levelno == logging.DEBUG)


def test_dashboard_logt_de_bronmelding_en_de_kpi_fout_als_kenmerk(caplog):
    from agent import dashboard

    caplog.set_level(logging.DEBUG)
    dashboard._collect_kpi({}, json.dumps({"fout": f"kolom {MARKER} ontbreekt"}))
    assert not [r for r in _regels(caplog, logging.WARNING) if MARKER in r]
    assert any("compute_kpi error: fout_len=" in r for r in _regels(caplog, logging.WARNING))


def test_rate_limit_timeout_logt_het_type_en_niet_de_providertekst(caplog, monkeypatch):
    import asyncio

    from agent import ratelimit

    async def acompletion(**kwargs):
        raise TimeoutError(f"request {MARKER}")

    monkeypatch.setattr(ratelimit.litellm, "acompletion", acompletion)
    monkeypatch.setattr(ratelimit, "_MAX_RETRIES", 1)

    async def emit(event):
        pass

    caplog.set_level(logging.DEBUG)
    with pytest.raises(TimeoutError):
        asyncio.run(ratelimit.acompletion_with_backoff(emit=emit, model="x", messages=[]))
    assert not [r for r in _regels(caplog, logging.WARNING) if MARKER in r]
    assert any("Model timeout na 1 pogingen (TimeoutError fout_len=" in r for r in _regels(caplog, logging.ERROR))


def test_een_onbekend_dataset_id_van_het_model_staat_niet_letterlijk_in_het_log(caplog):
    from agent.search_trace import SearchTrace

    caplog.set_level(logging.INFO)
    with patch("tools.catalog._cbs", return_value=[]), patch("tools.catalog._rio_duo", return_value=[]):
        trace = SearchTrace()
        trace.note("get_duo_data", {"dataset_id": f"{MARKER}-lijst"}, "")
    [regel] = [r.getMessage() for r in caplog.records if "CATALOGUS_GELADEN" in r.getMessage()]
    assert MARKER not in regel
    assert re.search(r"geladen=onbekend id_len=\d+ id_hash=[0-9a-f]{8}", regel)


# --- verbindings-ID ---


def test_elke_regel_in_een_context_met_verbinding_draagt_het_id():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "hallo", None, None)
    VerbindingFilter().filter(record)
    assert getattr(record, "verbinding", None) == GEEN

    def binnen():
        vid = nieuwe_verbinding()
        r = logging.LogRecord("x", logging.INFO, __file__, 1, "hallo", None, None)
        VerbindingFilter().filter(r)
        return vid, getattr(r, "verbinding", None)

    vid, gelogd = contextvars.copy_context().run(binnen)
    assert re.fullmatch(r"[0-9a-f]{8}", vid) and gelogd == vid
    assert verbinding.get() == GEEN  # de eigen context blijft zonder


def test_json_logregel_noemt_de_verbinding_alleen_als_die_er_is():
    import logging_config

    formatter = logging_config.JSONFormatter()
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "hallo", None, None)
    assert "verbinding" not in json.loads(formatter.format(record))
    record.verbinding = "abcd1234"
    assert json.loads(formatter.format(record))["verbinding"] == "abcd1234"


def test_setup_logging_zet_het_filter_op_de_handler():
    import logging_config

    root = logging.getLogger()
    before = root.handlers[:]
    try:
        logging_config.setup_logging(level="INFO", json_format=False)
        [handler] = root.handlers
        assert any(isinstance(f, VerbindingFilter) for f in handler.filters)
        assert handler.formatter is not None and "%(verbinding)s" in str(handler.formatter._fmt)
    finally:
        for h in root.handlers[:]:
            root.removeHandler(h)
        for h in before:
            root.addHandler(h)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    from core import auth

    importlib.reload(auth)
    from persistence import db

    importlib.reload(db)
    db.init_db()
    import server

    importlib.reload(server)
    from fastapi.testclient import TestClient

    return TestClient(server.app)


def test_een_chatverbinding_krijgt_een_verbindings_id_in_het_log(client, caplog):
    caplog.set_level(logging.INFO, logger="routes.chat")
    with client.websocket_connect("/api/chat") as ws:
        ws.send_text(json.dumps({"action": "ping"}))
    [regel] = [r.getMessage() for r in caplog.records if r.getMessage().startswith("VERBINDING open")]
    assert re.fullmatch(r"VERBINDING open verbinding=[0-9a-f]{8}", regel)
