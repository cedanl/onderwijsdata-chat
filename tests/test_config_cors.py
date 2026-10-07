"""CORS staat standaard dicht; een wildcard is nooit toegestaan (#421).

De frontend praat via dezelfde origin met de API (in ontwikkeling via de Vite-proxy),
dus geen omgeving heeft cross-origin toegang nodig. Met `allow_credentials=True`
zou `*` elke site namens een ingelogde gebruiker laten aanroepen.
"""

from pathlib import Path

import pytest
import yaml

from config import Config, ConfigError

_ROOT = Path(__file__).resolve().parent.parent
_VALUES = sorted([*_ROOT.glob("manifests/*/values.yaml"), _ROOT / "charts/onderwijsdata-chat/values.yaml"])


def test_zonder_instelling_geen_cross_origin(monkeypatch):
    monkeypatch.setattr(Config, "CORS_ORIGINS", "")
    assert Config.get_parsed_cors_origins() == []


def test_origins_komma_gescheiden(monkeypatch):
    monkeypatch.setattr(Config, "CORS_ORIGINS", " https://a.example , https://b.example ,")
    assert Config.get_parsed_cors_origins() == ["https://a.example", "https://b.example"]


def test_wildcard_wordt_geweigerd(monkeypatch):
    monkeypatch.setattr(Config, "CORS_ORIGINS", "https://a.example,*")
    with pytest.raises(ConfigError, match="CORS_ORIGINS"):
        Config.validate()


@pytest.mark.parametrize("values", _VALUES, ids=lambda p: str(p.relative_to(_ROOT)))
def test_elke_omgeving_noemt_alleen_eigen_host(values):
    doc = yaml.safe_load(values.read_text())
    origins = next(e["value"] for e in doc["env"] if e["name"] == "CORS_ORIGINS").split(",")
    hosts = {h["host"] for h in doc["ingress"]["web"]["hosts"]}
    assert origins == [f"https://{h}" for h in sorted(hosts)]
