"""Buiten lokaal start de app niet zonder login, tenzij dat bewust is aangezet (#787).

Zonder CHAT_USERS en OIDC heet elke bezoeker `gast` en delen ze alle gesprekken en rapporten. Lokaal is dat bedoeld;
een leeg geworden secret mag een uitgerolde omgeving er niet stil in brengen (de pod start, /health is groen).
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from config import Config, ConfigError
from core import auth

_ROOT = Path(__file__).resolve().parent.parent
_OMGEVINGEN = sorted(p.parent for p in _ROOT.glob("manifests/*/values.yaml"))
_BUITEN_LOKAAL = [omgeving for omgeving in Config.OMGEVINGEN if omgeving != "local"]


def _stel_in(monkeypatch, *, omgeving: str, login: bool, anoniem: bool = False) -> None:
    monkeypatch.setattr(Config, "APP_ENV", omgeving)
    monkeypatch.setattr(Config, "ALLOW_ANONYMOUS", anoniem)
    monkeypatch.setattr(auth, "AUTH_ENABLED", login)


# ─── de vier combinaties ─────────────────────────────────────────────────────


@pytest.mark.parametrize("login", [False, True])
def test_lokaal_start_met_en_zonder_login(monkeypatch, login):
    _stel_in(monkeypatch, omgeving="local", login=login)

    Config.validate()


@pytest.mark.parametrize("omgeving", _BUITEN_LOKAAL)
def test_buiten_lokaal_start_met_login(monkeypatch, omgeving):
    _stel_in(monkeypatch, omgeving=omgeving, login=True)

    Config.validate()


@pytest.mark.parametrize("omgeving", _BUITEN_LOKAAL)
def test_buiten_lokaal_start_niet_zonder_login(monkeypatch, omgeving):
    _stel_in(monkeypatch, omgeving=omgeving, login=False)

    with pytest.raises(ConfigError) as fout:
        Config.validate()

    melding = str(fout.value)
    assert "CHAT_USERS" in melding and "OIDC_PROVIDER" in melding and "ALLOW_ANONYMOUS" in melding
    assert omgeving in melding


# ─── de bewuste uitzondering ─────────────────────────────────────────────────


def test_allow_anonymous_laat_een_openbare_demo_starten_met_een_waarschuwing(monkeypatch, caplog):
    _stel_in(monkeypatch, omgeving="playground", login=False, anoniem=True)

    with caplog.at_level(logging.WARNING, logger="config"):
        Config.validate()

    waarschuwingen = [r for r in caplog.records if r.levelno == logging.WARNING and "ALLOW_ANONYMOUS" in r.getMessage()]
    assert len(waarschuwingen) == 1
    assert "playground" in waarschuwingen[0].getMessage()


def test_allow_anonymous_waarschuwt_niet_als_er_een_login_is(monkeypatch, caplog):
    _stel_in(monkeypatch, omgeving="test", login=True, anoniem=True)

    with caplog.at_level(logging.WARNING, logger="config"):
        Config.validate()

    assert not [r for r in caplog.records if "ALLOW_ANONYMOUS" in r.getMessage()]


@pytest.mark.parametrize(
    ("waarde", "verwacht"), [("true", "True"), (" TRUE ", "True"), ("1", "False"), ("yes", "False")]
)
def test_allow_anonymous_leest_alleen_true(waarde, verwacht):
    # In een eigen proces: Config leest de omgeving bij import, en herladen zou de klasse vervangen die andere tests houden.
    uitvoer = subprocess.run(
        [sys.executable, "-c", "from config import Config; print(Config.ALLOW_ANONYMOUS)"],
        cwd=_ROOT,
        env={**os.environ, "ALLOW_ANONYMOUS": waarde},
        capture_output=True,
        text=True,
        check=True,
    )

    assert uitvoer.stdout.strip() == verwacht


def test_de_melding_noemt_geen_geheimen(monkeypatch):
    monkeypatch.setenv("CHAT_USERS", "alice:geheim-wachtwoord")
    monkeypatch.setenv("CHAT_SECRET", "geheim-token")
    _stel_in(monkeypatch, omgeving="production", login=False)

    with pytest.raises(ConfigError) as fout:
        Config.validate()

    assert "geheim" not in str(fout.value)


# ─── de manifests ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("omgeving", _OMGEVINGEN, ids=lambda p: p.name)
def test_elk_manifest_zet_een_login_of_kiest_bewust_anoniem(omgeving):
    env = {e["name"] for e in yaml.safe_load((omgeving / "values.yaml").read_text())["env"]}

    assert env & {"CHAT_USERS", "OIDC_PROVIDER", "ALLOW_ANONYMOUS"}, (
        f"{omgeving.name} zet geen login: de app start daar niet meer (#787)"
    )
