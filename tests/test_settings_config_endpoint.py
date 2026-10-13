"""GET /api/settings/config: modellen met platte labels en de provider (#496, F10)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import config
from routes import instellingen

SONNET_55 = "azure_ai/claude-sonnet-5-5"


def _client(monkeypatch, model_ids: list[str] | None) -> TestClient:
    monkeypatch.setattr(config, "WILLMA_API_KEY", None)
    offered = config._models_from_ids(model_ids) if model_ids is not None else None
    monkeypatch.setattr(instellingen, "get_available_models_for_user", lambda username: offered)
    app = FastAPI()
    app.include_router(instellingen.router)
    return TestClient(app)


def test_settings_config_gives_plain_label_and_provider(monkeypatch):
    body = _client(monkeypatch, [SONNET_55]).get("/api/settings/config").json()
    assert body["models"] == [
        {
            "id": SONNET_55,
            "name": "Sonnet 5.5",
            "description": "voor de meeste vragen",
            "icon": "sparkles",
            "provider": "Microsoft Azure AI Foundry",
        }
    ]
    assert body["default_model"] == instellingen.MODEL


@pytest.mark.parametrize(
    ("mid", "name", "provider"),
    [("anthropic/claude-nieuw", "claude-nieuw", "Anthropic"), ("mistral/large-latest", "large-latest", "")],
)
def test_settings_config_unknown_model_keeps_its_id_name(monkeypatch, mid, name, provider):
    [model] = _client(monkeypatch, [mid]).get("/api/settings/config").json()["models"]
    assert model == {"id": mid, "name": name, "description": "", "icon": "cpu", "provider": provider}


def test_settings_config_keeps_offered_ids_in_order(monkeypatch):
    ids = [SONNET_55, "azure_ai/claude-opus-5-5", "openai/gpt-nieuw"]
    body = _client(monkeypatch, ids).get("/api/settings/config").json()
    assert [m["id"] for m in body["models"]] == ids


def test_settings_config_without_picker_offers_no_models(monkeypatch):
    body = _client(monkeypatch, None).get("/api/settings/config").json()
    assert body == {"models": [], "default_model": instellingen.MODEL}
