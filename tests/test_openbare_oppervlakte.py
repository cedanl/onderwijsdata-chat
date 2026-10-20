"""Wat de server zonder inloggen laat zien en berekent (#636).

In productie geen API-documentatie (Swagger UI haalde zijn scripts van cdn.jsdelivr.net), en de
dashboard-eindpunten alleen voor een ingelogde gebruiker en alleen als dashboards aan staan.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

DOCS_PADEN = ("/api/docs", "/docs/oauth2-redirect", "/redoc", "/api/openapi.json")


def _herlaad_server(monkeypatch, productie: bool):
    """server opnieuw opgebouwd, zonder de gebouwde SPA (frontend/dist), met of zonder productie."""
    import frontend_static
    import server
    from config import Config

    with monkeypatch.context() as m:
        m.setattr(frontend_static, "mount_frontend", lambda app, dist: None)
        if productie:
            m.setattr(Config, "POSTGRES_URI", "postgresql://test")
            m.setattr(Config, "SESSION_SECRET", "test")
        importlib.reload(server)
    return server.app


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))


@pytest.fixture
def productie_app(database, monkeypatch):
    app = _herlaad_server(monkeypatch, productie=True)
    yield app
    # De volgende test krijgt weer de gewone app; DATABASE_PATH staat dan nog op de tijdelijke map.
    importlib.reload(importlib.import_module("server"))


@pytest.fixture
def ontwikkel_app(database, monkeypatch):
    app = _herlaad_server(monkeypatch, productie=False)
    yield app
    importlib.reload(importlib.import_module("server"))


# ── API-documentatie ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("pad", DOCS_PADEN)
def test_productie_biedt_geen_api_documentatie(productie_app, pad):
    resp = TestClient(productie_app).get(pad)

    assert resp.status_code == 404
    assert "cdn.jsdelivr.net" not in resp.text


def test_productie_publiceert_geen_openapi_schema(productie_app):
    assert productie_app.openapi_url is None
    assert productie_app.docs_url is None
    assert productie_app.redoc_url is None


def test_productie_met_spa_geeft_voor_docs_geen_documentatie(productie_app, tmp_path):
    # Met een gebouwde frontend vangt /api/{rest} de docs-paden op met een JSON-404, en /redoc krijgt
    # index.html van de SPA, net als elk onbekend pad. Geen van beide noemt de CDN of de API.
    from frontend_static import mount_frontend

    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>EDUdata</title>")
    mount_frontend(productie_app, tmp_path)
    client = TestClient(productie_app)

    for pad in ("/api/docs", "/api/openapi.json"):
        resp = client.get(pad)
        assert resp.status_code == 404, pad
        assert resp.json() == {"detail": "Not Found"}
    redoc = client.get("/redoc")
    assert redoc.text == "<!doctype html><title>EDUdata</title>"
    for pad in (*DOCS_PADEN, "/", "/dashboards"):
        assert "cdn.jsdelivr.net" not in client.get(pad).text, pad


def test_buiten_productie_blijft_de_api_documentatie(ontwikkel_app):
    client = TestClient(ontwikkel_app)

    assert client.get("/api/docs").status_code == 200
    schema = client.get("/api/openapi.json")
    assert schema.status_code == 200
    assert "/health" in schema.json()["paths"]
    assert client.get("/redoc").status_code == 200
