"""GET /api/settings/config: modellen met platte labels en de provider (#496, F10); met login aan alleen
voor een ingelogde gebruiker (#607)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import config
from routes import instellingen
from tests import test_token_intrekking as intrekking
from tests.test_auth_session import _ingetrokken, _misvormd, _verlopen, _vervalst, _zonder
from tests.test_token_intrekking import _bearer, _token

# De fixtures van de intrekkingstests: client is de hele app met inloggen aan.
database = intrekking.database
client = intrekking.client

SONNET_55 = "azure_ai/claude-sonnet-5-5"
SONNET_55_MODEL = {
    "id": SONNET_55,
    "name": "Sonnet 5.5",
    "description": "voor de meeste vragen",
    "icon": "sparkles",
    "provider": "Microsoft Azure AI Foundry",
}


def _bied_aan(monkeypatch, model_ids: list[str] | None) -> list[str]:
    """De route biedt `model_ids` aan; de lijst krijgt de gebruikersnaam van elke aanroep."""
    monkeypatch.setattr(config, "WILLMA_API_KEY", None)
    offered = config._models_from_ids(model_ids) if model_ids is not None else None
    gevraagd: list[str] = []

    def aanbod(username: str):
        gevraagd.append(username)
        return offered

    monkeypatch.setattr(instellingen, "get_available_models_for_user", aanbod)
    return gevraagd


def _router_client() -> TestClient:
    app = FastAPI()
    app.include_router(instellingen.router)
    return TestClient(app)


def _client(monkeypatch, model_ids: list[str] | None) -> TestClient:
    _bied_aan(monkeypatch, model_ids)
    return _router_client()


def test_settings_config_gives_plain_label_and_provider(monkeypatch):
    body = _client(monkeypatch, [SONNET_55]).get("/api/settings/config").json()
    assert body["models"] == [SONNET_55_MODEL]
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


# ── Met login aan alleen voor een ingelogde gebruiker (#607) ─────────────────


@pytest.mark.parametrize(
    "geval",
    [_zonder, _misvormd, _vervalst, _verlopen, _ingetrokken],
    ids=["zonder-token", "misvormd", "vervalst", "verlopen", "ingetrokken"],
)
def test_met_login_weigert_de_route_zonder_geldig_token(client, monkeypatch, geval):
    gevraagd = _bied_aan(monkeypatch, [SONNET_55])

    resp = client.get("/api/settings/config", headers=geval(client, monkeypatch))

    assert resp.status_code == 401
    assert resp.json() == {"detail": "Niet geautoriseerd"}
    assert gevraagd == []


def test_met_login_geeft_de_route_de_modellen_van_de_ingelogde_gebruiker(client, monkeypatch):
    gevraagd = _bied_aan(monkeypatch, [SONNET_55])

    resp = client.get("/api/settings/config", headers=_bearer(_token("alice")))

    assert resp.status_code == 200
    assert resp.json() == {"models": [SONNET_55_MODEL], "default_model": instellingen.MODEL}
    assert gevraagd == ["alice"]


def test_zonder_login_is_de_gebruiker_gast(monkeypatch):
    from core import auth

    monkeypatch.setattr(auth, "AUTH_ENABLED", False)
    gevraagd = _bied_aan(monkeypatch, [SONNET_55])

    resp = _router_client().get("/api/settings/config")

    assert resp.status_code == 200
    assert gevraagd == [auth.FALLBACK_USER]
