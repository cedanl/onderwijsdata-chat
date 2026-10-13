"""Vervolg op de log-privacy van #475: gezouten hash, foutregels zonder vrije tekst, een verbindings-ID (#502).

Foutteksten van tools, de sandbox, het herladen, de providers, interne fouten en CBS-calls kunnen
toolargumenten of modeltekst citeren; op INFO en hoger staat nu het type en een kenmerk, de tekst
(en een traceback) op DEBUG.
Elke logregel van een chatverbinding draagt een kort verbindings-ID, zodat regels van één
verbinding te koppelen zijn zonder gebruikersnaam of gespreks-ID.
"""

import contextvars
import importlib
import json
import logging
import re
from unittest.mock import patch

import litellm
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


# --- interne fout, CBS-meldingen en de sandbox: type en kenmerk, tekst op DEBUG ---


def _volledig(record: logging.LogRecord) -> str:
    """Alles wat een handler van een record kan schrijven: bericht, traceback en exc_text."""
    traceback = logging.Formatter().formatException(record.exc_info) if record.exc_info else ""
    return f"{record.getMessage()}\n{traceback}\n{record.exc_text or ''}"


def _lekt_op_warning(caplog) -> list[str]:
    return [_volledig(r) for r in caplog.records if r.levelno >= logging.WARNING and MARKER in _volledig(r)]


def _op_debug(caplog) -> list[str]:
    return [_volledig(r) for r in caplog.records if r.levelno == logging.DEBUG]


_KENMERK = r"fout_len=\d+ fout_hash=[0-9a-f]{8}"


def test_een_interne_fout_logt_op_error_het_type_en_een_kenmerk(caplog):
    from core.errors import log_interne_fout

    caplog.set_level(logging.DEBUG)
    exc = ValueError(f"x {MARKER}")
    fout_id = log_interne_fout(exc, "waar")
    assert re.fullmatch(r"[0-9a-f]{8}", fout_id)
    [error] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert re.fullmatch(rf"Interne fout {fout_id} in waar: ValueError {_KENMERK}", error.getMessage())
    assert error.exc_info is None
    assert not _lekt_op_warning(caplog)


def test_een_interne_fout_houdt_de_traceback_onder_hetzelfde_id_op_debug(caplog):
    from core.errors import log_interne_fout

    caplog.set_level(logging.DEBUG)
    try:
        raise ValueError(f"x {MARKER}")
    except ValueError as e:
        fout_id = log_interne_fout(e, "waar")
    [debug] = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert debug.exc_info is not None and fout_id in debug.getMessage()
    assert MARKER in caplog.text and "Traceback" in caplog.text
    # Eerst DEBUG: het laatste record is de ERROR-regel met het ID als eerste argument.
    assert caplog.records[-1].levelno == logging.ERROR
    assert caplog.records[-1].args[0] == fout_id


def test_het_kenmerk_van_een_interne_fout_is_gezouten_met_het_loggeheim(caplog, monkeypatch):
    from core.errors import log_interne_fout

    exc = ValueError(f"x {MARKER}")
    ongezouten = foutkenmerk(exc)
    monkeypatch.setattr(logging_util, "_SECRET", b"geheim")
    caplog.set_level(logging.DEBUG)
    log_interne_fout(exc, "waar")
    [error] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error.getMessage().endswith(f": {foutkenmerk(exc)}")
    assert foutkenmerk(exc) != ongezouten


@pytest.mark.parametrize(
    ("exc", "waar"),
    [
        (ValueError(f"zip() {MARKER}"), "verwerking"),
        (litellm.BadRequestError(f"detail {MARKER}", llm_provider="azure_ai", model="claude-sonnet-5-5"), "model/API"),
    ],
)
def test_het_fout_id_voor_de_gebruiker_staat_in_de_error_en_de_debugregel(caplog, exc, waar):
    from core.errors import error_event

    caplog.set_level(logging.DEBUG)
    melding = error_event(exc)["message"]
    [fout_id] = re.findall(r"fout-ID ([0-9a-f]{8})", melding)
    [error] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error.getMessage().startswith(f"Interne fout {fout_id} in {waar}: ")
    assert any(fout_id in r for r in _op_debug(caplog))
    assert MARKER not in melding and not _lekt_op_warning(caplog)


def test_een_falende_controle_toont_het_gelogde_id_zonder_fouttekst_op_warning(caplog):
    from agent.probleem import veilig

    def controle_die_faalt(*_):
        raise ValueError(f"kolom {MARKER} ontbreekt")

    caplog.set_level(logging.DEBUG)
    [probleem] = veilig(controle_die_faalt, "tekst")
    fout_id = caplog.records[-1].args[0]
    assert f"fout-ID {fout_id}" in probleem.melding
    assert not _lekt_op_warning(caplog)
    assert any(MARKER in r for r in _op_debug(caplog))


def test_falende_citaties_en_bronnen_loggen_geen_fouttekst_op_warning(caplog, monkeypatch):
    run = importlib.import_module("agent.run")  # `from agent import run` geeft de functie, niet de module

    def kapot(*_):
        raise ValueError(f"antwoord met {MARKER}")

    monkeypatch.setattr(run, "citaties", kapot)
    monkeypatch.setattr(run, "bronnen_van", kapot)
    caplog.set_level(logging.DEBUG)
    assert run._veilige_citaties("tekst", []) == []
    assert run._veilige_bronnen([]) == []
    assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 2
    assert not _lekt_op_warning(caplog)


def _cbs_fout(*_args, **_kwargs):
    raise RuntimeError(f"GET https://x/{MARKER}")


def _cbs_waarschuwingen_zijn_kenmerken(caplog) -> None:
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings and all(re.search(rf"RuntimeError {_KENMERK}", w) for w in warnings)
    assert not _lekt_op_warning(caplog)
    assert any(MARKER in r for r in _op_debug(caplog))


def test_cbs_dataproperties_mislukt_logt_type_en_kenmerk(caplog, monkeypatch):
    from tools import cbs

    monkeypatch.setattr(cbs, "definitions", _cbs_fout)
    caplog.set_level(logging.DEBUG)
    assert cbs._load_definitions("85423NED") is None
    _cbs_waarschuwingen_zijn_kenmerken(caplog)


def test_cbs_tableinfos_voor_de_bijwerkdatum_mislukt_logt_type_en_kenmerk(caplog, monkeypatch):
    from tools import cbs

    monkeypatch.setattr(cbs, "catalogus_laatste_update", lambda _id: "2026-01-01")
    monkeypatch.setattr(cbs, "get", _cbs_fout)
    caplog.set_level(logging.DEBUG)
    assert cbs.bron_laatste_update("85423NED") is None
    _cbs_waarschuwingen_zijn_kenmerken(caplog)


def test_cbs_tableinfos_voor_de_afronding_mislukt_logt_type_en_kenmerk(caplog, monkeypatch):
    from tools import cbs

    monkeypatch.setattr(cbs, "get", _cbs_fout)
    caplog.set_level(logging.DEBUG)
    assert cbs._afronding("85423NED") == (None, False)
    _cbs_waarschuwingen_zijn_kenmerken(caplog)


def test_cbs_dimensie_mislukt_logt_type_en_kenmerk_en_zet_geen_label(caplog, monkeypatch):
    import pandas as pd

    from tools import cbs

    monkeypatch.setattr(cbs, "_dimension_rows", _cbs_fout)
    df = pd.DataFrame({"Geslacht": ["T001038"], "Waarde": [1]})
    caplog.set_level(logging.DEBUG)
    uit = cbs._add_dimension_context(df, "85423NED", {"Geslacht": {"type": "Dimension"}})
    assert list(uit.columns) == ["Geslacht", "Waarde"]
    _cbs_waarschuwingen_zijn_kenmerken(caplog)


def test_een_gecrashte_sandbox_logt_code_en_kenmerk_van_stderr(caplog):
    import subprocess

    from tools import sandbox

    stderr = f"Traceback (most recent call last):\n  ValueError: {MARKER}"
    proces = subprocess.CompletedProcess(args=[], returncode=-9, stdout=b"", stderr=stderr.encode())
    caplog.set_level(logging.DEBUG)
    uitkomst = sandbox._lees(proces)
    assert uitkomst == sandbox.Uitkomst(
        fout="Script is afgebroken: het overschreed de geheugen- of tijdslimiet van de sandbox."
    )
    [warning] = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert re.search(rf"code -9\b.*stderr_len={len(stderr)} stderr_hash=[0-9a-f]{{8}}", warning)
    assert not _lekt_op_warning(caplog)
    assert any(MARKER in r for r in _op_debug(caplog))


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
