"""Logregels en startfouten: JSON met tijdzone, uvicorn in dezelfde vorm, geen toegangslog (#1186).

Het log van een SDP-omgeving gaat naar een logaggregator: elke regel moet JSON zijn, met een tijdstempel die een zone
noemt, en het toegangslog van uvicorn (client-adres, pad met gespreks- en rapport-ID's) hoort er niet in.
"""

import json
import logging
import logging.config
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import uvicorn.config

import logging_config

_ROOT = Path(__file__).resolve().parent.parent

_UVICORN = ("uvicorn", "uvicorn.error", "uvicorn.access")


def _record(bericht: str = "hallo") -> logging.LogRecord:
    return logging.LogRecord("x", logging.INFO, __file__, 1, bericht, None, None)


# --- #1153: tijdstempel met tijdzone ---


def test_json_tijdstempel_noemt_de_tijdzone():
    tijd = datetime.fromisoformat(json.loads(logging_config.JSONFormatter().format(_record()))["timestamp"])
    assert tijd.utcoffset() == timedelta(0)


def test_json_tijdstempel_volgt_het_moment_van_de_regel():
    record = _record()
    record.created = 1_700_000_000.5
    stempel = json.loads(logging_config.JSONFormatter().format(record))["timestamp"]
    assert stempel == "2023-11-14T22:13:20.500000+00:00"


def test_de_code_gebruikt_geen_utcnow_meer():
    bron = logging_config.__file__
    with open(bron, encoding="utf-8") as f:
        assert "utcnow" not in f.read()


# --- #1152 en #1114: de loggers van uvicorn in dezelfde vorm, zonder toegangslog ---


@pytest.fixture
def logging_zoals_uvicorn_het_laat(capsys):
    """Eerst de logging van uvicorn zelf (die loopt vóór het laden van de app), dan die van de app, op stdout.

    Zet daarna alles terug: setup_logging verandert de root- en uvicorn-loggers voor de hele testrun.
    """
    namen = ("", *_UVICORN)
    voor = {n: (lg.handlers[:], lg.level, lg.propagate, lg.disabled) for n in namen if (lg := logging.getLogger(n))}
    logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)
    yield capsys
    for naam, (handlers, niveau, propagate, disabled) in voor.items():
        logger = logging.getLogger(naam)
        logger.handlers[:] = handlers
        logger.setLevel(niveau)
        logger.propagate, logger.disabled = propagate, disabled


def _stdout_regels(capsys) -> list[str]:
    return [r for r in capsys.readouterr().out.splitlines() if r.strip()]


def _uvicorn_schrijft():
    """Wat uvicorn bij het opstarten, tijdens een verzoek en bij een fout in de app schrijft."""
    logging.getLogger("uvicorn.error").info("Started server process [%d]", 1234)
    logging.getLogger("uvicorn.error").info("Application startup complete.")
    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %d', "203.0.113.7:57334", "PUT", "/api/conversations/conv-abc-123", "1.1", 200
    )
    try:
        raise RuntimeError("kapot")
    except RuntimeError:
        logging.getLogger("uvicorn.error").error("Exception in ASGI application\n", exc_info=True)


def test_buiten_local_is_elke_regel_van_uvicorn_json(logging_zoals_uvicorn_het_laat):
    logging_config.setup_logging(level="INFO", json_format=True)

    _uvicorn_schrijft()

    regels = _stdout_regels(logging_zoals_uvicorn_het_laat)
    assert regels
    records = [json.loads(r) for r in regels]
    assert {r["logger"] for r in records} == {"uvicorn.error"}
    assert any(r["message"] == "Application startup complete." for r in records)


def test_een_onafgevangen_fout_is_buiten_local_een_json_regel_met_de_traceback_erin(logging_zoals_uvicorn_het_laat):
    logging_config.setup_logging(level="INFO", json_format=True)

    _uvicorn_schrijft()

    [fout] = [json.loads(r) for r in _stdout_regels(logging_zoals_uvicorn_het_laat) if "ASGI" in r]
    assert fout["level"] == "ERROR"
    assert "Traceback" in fout["exception"] and "RuntimeError: kapot" in fout["exception"]


def test_in_local_blijft_de_tekstvorm_en_gaat_ook_uvicorn_door_het_verbindingsfilter(logging_zoals_uvicorn_het_laat):
    logging_config.setup_logging(level="INFO", json_format=False)

    _uvicorn_schrijft()

    regels = _stdout_regels(logging_zoals_uvicorn_het_laat)
    assert any("uvicorn.error [-] - Application startup complete." in r for r in regels)
    assert not any(r.startswith("{") for r in regels)


@pytest.mark.parametrize("json_format", [True, False])
def test_het_toegangslog_noemt_geen_adres_pad_of_id(logging_zoals_uvicorn_het_laat, json_format):
    logging_config.setup_logging(level="INFO", json_format=json_format)

    _uvicorn_schrijft()

    uitvoer = "\n".join(_stdout_regels(logging_zoals_uvicorn_het_laat))
    for lek in ("203.0.113.7", "57334", "conv-abc-123", "/api/conversations", "PUT"):
        assert lek not in uitvoer


def test_uvicorn_houdt_geen_eigen_handlers_meer(logging_zoals_uvicorn_het_laat):
    logging_config.setup_logging(level="INFO", json_format=True)

    for naam in _UVICORN:
        logger = logging.getLogger(naam)
        assert logger.handlers == [] and logger.propagate


def test_het_logniveau_van_de_app_geldt_ook_voor_uvicorn(logging_zoals_uvicorn_het_laat):
    logging_config.setup_logging(level="WARNING", json_format=True)

    logging.getLogger("uvicorn.error").info("Application startup complete.")

    assert _stdout_regels(logging_zoals_uvicorn_het_laat) == []


# --- #1163: een ongeldige LOG_LEVEL is een configuratiemelding ---


def _start(tmp_path, **env) -> subprocess.CompletedProcess:
    """Importeer server.py in een eigen proces, zoals uvicorn dat doet, met alleen deze configuratie."""
    basis = {
        k: v for k, v in os.environ.items() if k not in ("LOG_LEVEL", "CHAT_USERS", "CHAT_SECRET", "OIDC_PROVIDER")
    }
    return subprocess.run(
        [sys.executable, "-c", "import server"],
        cwd=_ROOT,
        env={**basis, "DATABASE_PATH": str(tmp_path / "start.db"), **env},
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_een_ongeldige_log_level_stopt_de_start_met_een_regel_zonder_traceback(tmp_path):
    uitslag = _start(tmp_path, APP_ENV="local", LOG_LEVEL="garbage")

    assert uitslag.returncode != 0
    assert "Traceback" not in uitslag.stdout + uitslag.stderr
    [regel] = uitslag.stdout.splitlines()
    assert "LOG_LEVEL moet een van DEBUG, INFO, WARNING, ERROR, CRITICAL zijn, kreeg: GARBAGE" in regel


def test_buiten_local_is_die_ene_regel_json(tmp_path):
    uitslag = _start(tmp_path, APP_ENV="test", CHAT_USERS="admin:pw", CHAT_SECRET="s", LOG_LEVEL="garbage")

    assert uitslag.returncode != 0
    assert "Traceback" not in uitslag.stdout + uitslag.stderr
    [regel] = uitslag.stdout.splitlines()
    assert "LOG_LEVEL moet" in json.loads(regel)["message"]


@pytest.mark.parametrize("waarde", ["info", "Warning", " debug "])
def test_een_geldige_log_level_in_kleine_letters_werkt(waarde):
    uitvoer = subprocess.run(
        [sys.executable, "-c", "from config import Config; Config.validate(); print(Config.log_level())"],
        cwd=_ROOT,
        env={**os.environ, "LOG_LEVEL": waarde, "APP_ENV": "local"},
        capture_output=True,
        text=True,
        check=True,
    )

    assert uitvoer.stdout.strip().splitlines()[-1] == waarde.strip().upper()


def test_een_lege_log_level_is_de_standaard():
    uitvoer = subprocess.run(
        [sys.executable, "-c", "from config import Config; print(Config.log_level())"],
        cwd=_ROOT,
        env={**os.environ, "LOG_LEVEL": " "},
        capture_output=True,
        text=True,
        check=True,
    )

    assert uitvoer.stdout.strip() == "INFO"
