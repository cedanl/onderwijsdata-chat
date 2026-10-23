"""Eén expliciete omgevingsvlag in plaats van "POSTGRES_URI én SESSION_SECRET" (#676).

SESSION_SECRET zette geen enkele omgeving, dus test, playground en productie toonden de API-documentatie
en schreven tekstlogs. APP_ENV noemt de omgeving; de manifests zetten hem, lokaal is hij leeg.
"""

from pathlib import Path

import pytest
import yaml

from config import Config, ConfigError

_ROOT = Path(__file__).resolve().parent.parent
_OMGEVINGEN = sorted(p.parent for p in _ROOT.glob("manifests/*/values.yaml"))


def _app_env(omgeving: Path) -> str | None:
    env = yaml.safe_load((omgeving / "values.yaml").read_text())["env"]
    return next((e.get("value") for e in env if e["name"] == "APP_ENV"), None)


@pytest.mark.parametrize("omgeving", _OMGEVINGEN, ids=lambda p: p.name)
def test_elke_omgeving_noemt_zichzelf(omgeving):
    assert _app_env(omgeving) == omgeving.name


@pytest.mark.parametrize("omgeving", ["playground", "production"])
def test_playground_en_productie_tonen_geen_api_documentatie(monkeypatch, omgeving):
    monkeypatch.setattr(Config, "APP_ENV", _app_env(_ROOT / "manifests" / omgeving))
    assert not Config.api_docs()


@pytest.mark.parametrize("omgeving", ["local", "development", "test"])
def test_waar_ontwikkeld_wordt_blijft_de_documentatie(monkeypatch, omgeving):
    monkeypatch.setattr(Config, "APP_ENV", omgeving)
    assert Config.api_docs()


@pytest.mark.parametrize(("omgeving", "json"), [("local", False), ("test", True), ("playground", True)])
def test_json_logs_op_elke_sdp_omgeving(monkeypatch, omgeving, json):
    monkeypatch.setattr(Config, "APP_ENV", omgeving)
    assert Config.json_logs() is json


def test_een_onbekende_omgeving_start_niet(monkeypatch):
    monkeypatch.setattr(Config, "APP_ENV", "prod")
    with pytest.raises(ConfigError, match="APP_ENV"):
        Config.validate()


def test_session_secret_is_weg():
    assert not hasattr(Config, "SESSION_SECRET")
    assert not hasattr(Config, "is_production")
