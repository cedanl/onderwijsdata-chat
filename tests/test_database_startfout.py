"""Een mislukte databasestart noemt een veilige oorzaak in het log (#1155).

Een driverfout citeert host, gebruiker en databasenaam; op ERROR staat daarom een vaste categorie ("verbinding
geweigerd", "authenticatie mislukt", ...) en nooit de fouttekst zelf. Zonder dat moest een beheerder met een pod in
CrashLoopBackOff LOG_LEVEL=DEBUG zetten, en dat zet ook vraag- en antwoordtekst in het log.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from persistence import db

_ROOT = Path(__file__).resolve().parent.parent
HOST, GEBRUIKER, DATABASE, WACHTWOORD = "db-geheim.intern", "admin-geheim", "klantdb-geheim", "wachtwoord-geheim"


class OperationalError(Exception):
    """Zoals psycopg2.OperationalError: de naam van de klasse is wat telt, de driver hoeft niet geïnstalleerd."""


class ProgrammingError(Exception):
    pass


def _oorzaak(fout: BaseException) -> str:
    tekst = db.startfout_oorzaak(fout)
    assert tekst is not None
    return tekst


def _pg(monkeypatch) -> None:
    monkeypatch.setattr(db, "_USE_POSTGRES", True)


@pytest.mark.parametrize(
    ("fout", "oorzaak"),
    [
        (
            OperationalError(
                f'connection to server at "{HOST}" (10.0.0.4), port 5432 failed: Connection refused\n'
                "\tIs the server running on that host and accepting TCP/IP connections?"
            ),
            "verbinding geweigerd",
        ),
        (OperationalError(f'connection to server at "{HOST}", port 5432 failed: timeout expired'), "time-out"),
        (OperationalError(f'could not translate host name "{HOST}" to address: Name or service not known'), "hostnaam"),
        (
            OperationalError(
                f'connection to server at "{HOST}", port 5432 failed: FATAL:  '
                f'password authentication failed for user "{GEBRUIKER}"'
            ),
            "authenticatie mislukt",
        ),
        (OperationalError(f'FATAL:  database "{DATABASE}" does not exist'), "database bestaat niet"),
        (OperationalError(f'FATAL:  role "{GEBRUIKER}" does not exist'), "authenticatie mislukt"),
        (ProgrammingError('invalid dsn: missing "=" after "' + HOST + '" in connection info string'), "ongeldige URI"),
        (OperationalError("server does not support SSL, but SSL was required"), "TLS"),
    ],
)
def test_een_postgresfout_noemt_een_categorie_zonder_host_gebruiker_of_database(monkeypatch, fout, oorzaak):
    _pg(monkeypatch)

    tekst = _oorzaak(fout)

    assert oorzaak in tekst
    for geheim in (HOST, GEBRUIKER, DATABASE, WACHTWOORD, "10.0.0.4"):
        assert geheim not in tekst


def test_een_onbekende_postgresfout_heeft_geen_categorie(monkeypatch):
    _pg(monkeypatch)

    assert db.startfout_oorzaak(OperationalError("iets nieuws van de driver")) is None


def test_een_ontbrekende_driver_zegt_hoe_je_hem_installeert(monkeypatch):
    _pg(monkeypatch)
    monkeypatch.setitem(sys.modules, "psycopg2", None)
    monkeypatch.setenv("POSTGRES_URI", f"postgresql://{GEBRUIKER}:{WACHTWOORD}@{HOST}:1/{DATABASE}")

    with pytest.raises(db.DatabaseStartFout) as fout:
        db._connect()

    tekst = _oorzaak(fout.value)
    assert "psycopg2" in tekst and "uv sync --extra postgres" in tekst
    assert WACHTWOORD not in tekst and HOST not in tekst


def test_een_sqlite_pad_dat_niet_open_kan_wordt_met_het_pad_genoemd(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "_USE_POSTGRES", False)
    pad = tmp_path / "bestaat-niet" / "x.db"
    monkeypatch.setenv("DATABASE_PATH", str(pad))

    with pytest.raises(Exception) as fout:
        db._connect()

    tekst = _oorzaak(fout.value)
    assert "SQLite-pad" in tekst and str(pad) in tekst


def test_een_sqlite_pad_dat_een_map_is_wordt_ook_genoemd(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "_USE_POSTGRES", False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path))

    with pytest.raises(Exception) as fout:
        db._connect()

    assert str(tmp_path) in _oorzaak(fout.value)


def test_een_andere_sqlitefout_heeft_geen_categorie(monkeypatch):
    monkeypatch.setattr(db, "_USE_POSTGRES", False)

    assert db.startfout_oorzaak(RuntimeError("iets anders")) is None


# --- het opstartlog ---


# `sys.modules["psycopg2"] = None` laat elke `import psycopg2` falen, ook waar de driver wel geïnstalleerd is (CI).
_IMPORT_ZONDER_DRIVER = "import sys; sys.modules['psycopg2'] = None; import server"


def _start(tmp_path, code: str = "import server", **env) -> subprocess.CompletedProcess:
    basis = {k: v for k, v in os.environ.items() if k not in ("POSTGRES_URI", "DATABASE_PATH", "LOG_LEVEL")}
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=_ROOT,
        env={**basis, "APP_ENV": "test", "ALLOW_ANONYMOUS": "true", **env},
        capture_output=True,
        text=True,
        timeout=120,
    )


def _fout_regel(uitslag: subprocess.CompletedProcess) -> dict:
    [regel] = [r for r in uitslag.stdout.splitlines() if "Failed to initialize database" in r]
    return json.loads(regel)


def test_postgres_zonder_driver_logt_op_error_dat_de_driver_ontbreekt(tmp_path):
    uitslag = _start(
        tmp_path, _IMPORT_ZONDER_DRIVER, POSTGRES_URI=f"postgresql://{GEBRUIKER}:{WACHTWOORD}@{HOST}:1/{DATABASE}"
    )

    assert uitslag.returncode == 1
    regel = _fout_regel(uitslag)
    assert regel["level"] == "ERROR"
    assert "psycopg2 ontbreekt" in regel["message"] and "uv sync --extra postgres" in regel["message"]
    for geheim in (HOST, GEBRUIKER, DATABASE, WACHTWOORD):
        assert geheim not in uitslag.stdout + uitslag.stderr


def test_een_onschrijfbaar_sqlitepad_logt_het_pad(tmp_path):
    pad = tmp_path / "bestaat-niet" / "x.db"

    uitslag = _start(tmp_path, DATABASE_PATH=str(pad))

    assert uitslag.returncode == 1
    assert str(pad) in _fout_regel(uitslag)["message"]
    assert "Traceback" not in uitslag.stdout + uitslag.stderr
