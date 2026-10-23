"""Wat de server zonder inloggen laat zien en berekent (#636).

In productie geen API-documentatie (Swagger UI haalde zijn scripts van cdn.jsdelivr.net), en de
dashboard-eindpunten alleen voor een ingelogde gebruiker en alleen als dashboards aan staan.
"""

import pytest
from fastapi.testclient import TestClient

from core.foutmeldingen import NIET_GEVONDEN

DOCS_PADEN = ("/api/docs", "/docs/oauth2-redirect", "/redoc", "/api/openapi.json")


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))


@pytest.fixture
def productie_app():
    """Een productie-app uit de fabriek, zonder de gebouwde SPA (frontend/dist) en zonder server te herladen."""
    from server import create_app

    return create_app(api_docs=False)


@pytest.fixture
def ontwikkel_app():
    from server import create_app

    return create_app(api_docs=True)


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
        assert resp.json() == {"detail": NIET_GEVONDEN}
    redoc = client.get("/redoc")
    assert redoc.text == "<!doctype html><title>EDUdata</title>"
    for pad in (*DOCS_PADEN, "/", "/dashboards"):
        assert "cdn.jsdelivr.net" not in client.get(pad).text, pad


@pytest.mark.parametrize("productie", [False, True])
def test_head_en_get_op_openapi_json_geven_hetzelfde_type(tmp_path, productie):
    # #654: GET /openapi.json gaf de app-shell, HEAD een JSON-405; het echte schema staat onder /api.
    from server import create_app

    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>EDUdata</title>")
    client = TestClient(create_app(api_docs=not productie, frontend_dist=tmp_path))

    get, head = client.get("/openapi.json"), client.head("/openapi.json")
    assert head.status_code == get.status_code == 200
    assert head.headers["content-type"] == get.headers["content-type"]
    # Een echte route houdt zijn eigen antwoord: HEAD /health wordt geen app-shell.
    assert client.head("/health").headers["content-type"].startswith("application/json")
    schema = client.head("/api/openapi.json")
    if productie:
        assert schema.status_code == 405
    else:
        assert schema.status_code == 200
        assert schema.headers["content-type"] == "application/json"


def test_buiten_productie_blijft_de_api_documentatie(ontwikkel_app):
    client = TestClient(ontwikkel_app)

    assert client.get("/api/docs").status_code == 200
    schema = client.get("/api/openapi.json")
    assert schema.status_code == 200
    assert "/health" in schema.json()["paths"]
    assert client.get("/redoc").status_code == 200


# ── De fabriek en de app van de module ───────────────────────────────────────


def _routes(routes) -> list[tuple]:
    """Elke route op volgorde, ook die van een ingesloten router (FastAPI nest die in app.routes)."""
    platte = []
    for route in routes:
        if hasattr(route, "original_router"):
            platte += _routes(route.original_router.routes)
        else:
            platte.append((type(route).__name__, getattr(route, "path", None), sorted(getattr(route, "methods", ()))))
    return platte


def test_de_fabriek_bouwt_dezelfde_app_als_server_app():
    import server

    frontend = server._FRONTEND_DIST if server._FRONTEND_DIST.exists() else None
    app = server.create_app(api_docs=True, frontend_dist=frontend)

    assert _routes(app.routes) == _routes(server.app.routes)
    assert {"/health", "/ready", "/startup", "/version", "/api/version", "/info"} <= set(app.openapi()["paths"])
    assert [(m.cls, m.kwargs) for m in app.user_middleware] == [(m.cls, m.kwargs) for m in server.app.user_middleware]
    assert app.exception_handlers.keys() == server.app.exception_handlers.keys()
    assert app.router.on_startup == server.app.router.on_startup == [server.on_startup]
    assert app.router.on_shutdown == server.app.router.on_shutdown == [server.on_shutdown]


def test_de_fabriek_zet_dezelfde_beveiligingsheaders_als_server_app():
    import server

    koppen = ("x-content-type-options", "x-frame-options", "strict-transport-security", "referrer-policy")
    koppen += ("permissions-policy", "content-security-policy")
    for app in (server.create_app(api_docs=False), server.create_app(api_docs=True)):
        fabriek = TestClient(app).get("/health").headers
        module = TestClient(server.app).get("/health").headers
        assert {k: fabriek.get(k) for k in koppen} == {k: module.get(k) for k in koppen}
        assert all(fabriek.get(k) for k in koppen)


# ── Dashboard-eindpunten ─────────────────────────────────────────────────────

# Pad en de loader in routes.instellingen die het pad aanroept.
DASHBOARDS = {
    "/api/dashboard/instroom": "load_dashboard_data",
    "/api/dashboard/regio": "load_dashboard_regio",
    "/api/dashboard/nationaal": "load_dashboard_nationaal",
    "/api/dashboard/rendement": "load_dashboard_rendement",
    "/api/dashboard/arbeidsmarktmatch": "load_dashboard_arbeidsmarktmatch",
}


@pytest.fixture
def loaders(monkeypatch):
    """Elke dashboardloader nagebootst (geen DUO-download); de lijst zegt welke paden data laadden."""
    import routes.instellingen

    geladen: list[tuple[str, str]] = []
    for naam in DASHBOARDS.values():
        monkeypatch.setattr(
            routes.instellingen, naam, lambda instelling, naam=naam: geladen.append((naam, instelling)) or {"ok": naam}
        )
    return geladen


def _client(database, monkeypatch, *, login: bool, dashboards: bool) -> TestClient:
    """De gewone app, zonder modules te herladen: login en de dashboardvlag via monkeypatch."""
    import routes.instellingen
    import server
    from core import auth
    from persistence import db

    db.init_db()
    monkeypatch.setattr(auth, "AUTH_ENABLED", login)
    monkeypatch.setattr(routes.instellingen, "DASHBOARDS_ENABLED", dashboards)
    return TestClient(server.app)


def _bearer(username: str = "alice") -> dict:
    # Het token direct, niet via /api/auth/login: de loginlimiet geldt voor de hele testrun.
    from core import auth

    return {"Authorization": f"Bearer {auth.make_token(username)}"}


@pytest.mark.parametrize("pad", DASHBOARDS)
def test_dashboard_zonder_token_geeft_401(database, monkeypatch, loaders, pad):
    client = _client(database, monkeypatch, login=True, dashboards=True)

    resp = client.get(pad, params={"instelling": "Hogeschool Utrecht"})

    assert resp.status_code == 401
    assert loaders == []


@pytest.mark.parametrize("pad", DASHBOARDS)
def test_dashboard_met_ongeldig_token_geeft_401(database, monkeypatch, loaders, pad):
    client = _client(database, monkeypatch, login=True, dashboards=True)

    resp = client.get(pad, params={"instelling": "Hogeschool Utrecht"}, headers={"Authorization": "Bearer nep.sig"})

    assert resp.status_code == 401
    assert loaders == []


@pytest.mark.parametrize("pad, loader", DASHBOARDS.items())
def test_dashboard_met_token_geeft_de_data(database, monkeypatch, loaders, pad, loader):
    client = _client(database, monkeypatch, login=True, dashboards=True)

    resp = client.get(pad, params={"instelling": "Hogeschool Utrecht"}, headers=_bearer())

    assert resp.status_code == 200
    assert resp.json() == {"ok": loader}
    assert loaders == [(loader, "Hogeschool Utrecht")]


@pytest.mark.parametrize("login", [True, False])
@pytest.mark.parametrize("pad", DASHBOARDS)
def test_dashboard_uit_geeft_403_en_laadt_niets(database, monkeypatch, loaders, pad, login):
    client = _client(database, monkeypatch, login=login, dashboards=False)

    resp = client.get(pad, params={"instelling": "Hogeschool Utrecht"}, headers=_bearer())

    assert resp.status_code == 403
    assert resp.json() == {"error": "Dashboards zijn niet beschikbaar"}
    assert loaders == []


@pytest.mark.parametrize("pad, loader", DASHBOARDS.items())
def test_dashboard_zonder_login_werkt_als_voorheen(database, monkeypatch, loaders, pad, loader):
    client = _client(database, monkeypatch, login=False, dashboards=True)

    resp = client.get(pad, params={"instelling": "VU"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": loader}
    assert loaders == [(loader, "VU")]
