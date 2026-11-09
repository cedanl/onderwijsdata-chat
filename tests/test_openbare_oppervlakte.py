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
            platte.append(
                (type(route).__name__, getattr(route, "path", None), sorted(getattr(route, "methods", None) or ()))
            )
    return platte


def test_de_fabriek_bouwt_dezelfde_app_als_server_app():
    import server

    frontend = server._FRONTEND_DIST if server._FRONTEND_DIST.exists() else None
    app = server.create_app(api_docs=True, frontend_dist=frontend)

    assert _routes(app.routes) == _routes(server.app.routes)
    assert {"/health", "/ready", "/version", "/api/version", "/info"} <= set(app.openapi()["paths"])
    assert [(m.cls, m.kwargs) for m in app.user_middleware] == [(m.cls, m.kwargs) for m in server.app.user_middleware]
    assert app.exception_handlers.keys() == server.app.exception_handlers.keys()


def test_de_lifespan_start_en_stopt_de_app(monkeypatch):
    """on_startup en on_shutdown via de lifespan, met daartussen de sessiemanager van /mcp (#706)."""
    import server

    gebeurd: list[str] = []

    async def start() -> None:
        gebeurd.append("start")

    async def stop() -> None:
        gebeurd.append("stop")

    monkeypatch.setattr(server, "on_startup", start)
    monkeypatch.setattr(server, "on_shutdown", stop)
    with TestClient(server.create_app(api_docs=False)):
        assert gebeurd == ["start"]
    assert gebeurd == ["start", "stop"]


def test_de_fabriek_zet_dezelfde_beveiligingsheaders_als_server_app():
    import server

    koppen = ("x-content-type-options", "x-frame-options", "strict-transport-security", "referrer-policy")
    koppen += ("permissions-policy", "content-security-policy", "cross-origin-opener-policy")
    koppen += ("cross-origin-resource-policy",)
    for app in (server.create_app(api_docs=False), server.create_app(api_docs=True)):
        fabriek = TestClient(app).get("/health").headers
        module = TestClient(server.app).get("/health").headers
        assert {k: fabriek.get(k) for k in koppen} == {k: module.get(k) for k in koppen}
        assert all(fabriek.get(k) for k in koppen)


# ── Dashboard-eindpunten ─────────────────────────────────────────────────────

# Pad en de loader in routes.instellingen die het pad aanroept.
DASHBOARDS = {
    "/api/dashboard/regio": "load_dashboard_regio",
    "/api/dashboard/nationaal": "load_dashboard_nationaal",
    "/api/dashboard/rendement": "load_dashboard_rendement",
    "/api/dashboard/arbeidsmarktmatch": "load_dashboard_arbeidsmarktmatch",
    "/api/dashboard/financien": "load_dashboard_financien",
    "/api/dashboard/personeel": "load_dashboard_personeel",
    "/api/dashboard/opleidingen": "load_dashboard_opleidingen",
}
# Eindpunten op een bron met een omgevingsregel (tools/beschikbaarheid.py, #935, #936): pad → de regel die aan moet.
OP_EEN_BRON = {"/api/dashboard/financien": "financien", "/api/dashboard/personeel": "wo_personeel"}


@pytest.fixture
def loaders(monkeypatch):
    """Elke dashboardloader nagebootst (geen DUO-download); de lijst zegt welke paden data laadden. De sleutel van de
    Studiekeuzedatabase staat, zodat ook het dashboard Opleidingen er is (#957)."""
    import routes.instellingen
    from tools import beschikbaarheid

    monkeypatch.setattr(beschikbaarheid, "studiekeuze", lambda: True)
    geladen: list[tuple[str, str]] = []
    for naam in DASHBOARDS.values():
        monkeypatch.setattr(
            routes.instellingen, naam, lambda instelling, naam=naam: geladen.append((naam, instelling)) or {"ok": naam}
        )
    return geladen


def _client(database, monkeypatch, *, login: bool, dashboards: bool, bronnen: bool = True) -> TestClient:
    """De gewone app, zonder modules te herladen: login, de dashboardvlag en de regels van de bronnen via monkeypatch."""
    import routes.instellingen
    import server
    from core import auth
    from persistence import db
    from tools import beschikbaarheid

    db.init_db()
    monkeypatch.setattr(auth, "AUTH_ENABLED", login)
    monkeypatch.setattr(routes.instellingen, "DASHBOARDS_ENABLED", dashboards)
    for regel in OP_EEN_BRON.values():
        monkeypatch.setattr(beschikbaarheid, regel, lambda aan=bronnen: aan)
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


@pytest.mark.parametrize("login", [True, False])
@pytest.mark.parametrize("pad", OP_EEN_BRON)
def test_een_eindpunt_op_een_bron_die_uit_staat_bestaat_niet(database, monkeypatch, loaders, pad, login):
    # WOPI zonder ENABLE_WO_PERSONEEL, de financiën zonder bevestigde licentie: 404, en er wordt niets geladen.
    from routes.instellingen import BRON_UIT

    client = _client(database, monkeypatch, login=login, dashboards=True, bronnen=False)

    resp = client.get(pad, params={"instelling": "Universiteit Utrecht"}, headers=_bearer())

    assert resp.status_code == 404
    assert resp.json() == {"error": BRON_UIT}
    assert loaders == []


# De paden die geen dashboard laden, maar zeggen waar het wel kan (#954): de oude instroom (410) en elk ander pad (404).
GEEN_DASHBOARD = {
    "/api/dashboard/instroom",
    "/api/dashboard/{rest:path}",
    "/api/dashboards",
    "/api/dashboards/{rest:path}",
}


def test_elk_dashboardpad_heeft_een_dashboard_dat_het_gebruikt():
    # /api/dashboard/instroom gebruikte geen enkel dashboard en is weg (#930); een nieuw pad hoort in DASHBOARDS en in
    # de hooks van de frontend.
    from pathlib import Path

    import server
    from routes.instellingen import DASHBOARD_EINDPUNTEN

    paden = {pad for _, pad, _ in _routes(server.app.routes) if pad and pad.startswith("/api/dashboard")}
    hooks = (Path(__file__).parent.parent / "frontend/src/components/dashboards/shared/hooks.js").read_text()

    assert paden - GEEN_DASHBOARD == set(DASHBOARDS) == {f"/api/dashboard/{naam}" for naam in DASHBOARD_EINDPUNTEN}
    assert all(f"'{pad}'" in hooks for pad in DASHBOARDS)


def test_de_docs_noemen_dezelfde_dashboard_eindpunten_als_de_api():
    # #954: oudere docs en testprotocollen noemden er nog vijf. docs/api.md heeft een regel per eindpunt.
    import re
    from pathlib import Path

    docs = Path(__file__).parent.parent / "docs"
    in_api = set(re.findall(r"`GET` \| `(/api/dashboard/[a-z]+)`", (docs / "api.md").read_text()))
    in_dashboards = set(re.findall(r"`(/api/dashboard/[a-z]+)`", (docs / "dashboards.md").read_text()))

    assert in_api == set(DASHBOARDS)
    assert in_dashboards - {"/api/dashboard/instroom"} == set(DASHBOARDS)


def test_docs_api_noemt_elk_veld_van_api_config(database):
    # #972: de regel noemde "o.a." vier velden en miste `bronnen` (#956). Een nieuw veld hoort erbij.
    import asyncio
    import re
    from pathlib import Path

    from routes.config import get_config

    tekst = (Path(__file__).parent.parent / "docs" / "api.md").read_text()
    gevonden = re.search(r"^\| `GET` \| `/api/config` \|(.*)$", tekst, flags=re.MULTILINE)
    assert gevonden
    regel = gevonden.group(1)

    assert {veld for veld in asyncio.run(get_config()) if f"`{veld}`" not in regel} == set()


@pytest.mark.parametrize("met_spa", [False, True])
@pytest.mark.parametrize("login", [True, False])
def test_de_oude_instroom_geeft_410_met_waar_de_cijfers_staan(database, monkeypatch, loaders, tmp_path, login, met_spa):
    from routes.instellingen import INSTROOM_WEG

    client = _client(database, monkeypatch, login=login, dashboards=True)
    if met_spa:
        # Met een gebouwde frontend vangt /api/{rest} elk onbekend API-pad; de dashboardroutes gaan daaraan vooraf.
        from server import create_app

        (tmp_path / "assets").mkdir()
        (tmp_path / "index.html").write_text("<!doctype html><title>EDUdata</title>")
        client = TestClient(create_app(api_docs=False, frontend_dist=tmp_path))

    resp = client.get("/api/dashboard/instroom", params={"instelling": "Curio"})

    assert resp.status_code == 410
    assert resp.json() == {"error": INSTROOM_WEG}
    assert "/api/dashboard/regio" in INSTROOM_WEG and "2.6.0" in INSTROOM_WEG
    assert loaders == []


@pytest.mark.parametrize("met_spa", [False, True])
@pytest.mark.parametrize("pad", ["/api/dashboards/Curio/instroom", "/api/dashboards", "/api/dashboard/instromen"])
def test_een_onbekend_dashboardpad_zegt_welke_er_wel_zijn(database, monkeypatch, loaders, tmp_path, pad, met_spa):
    from routes.instellingen import ONBEKEND_EINDPUNT

    client = _client(database, monkeypatch, login=False, dashboards=True)
    if met_spa:
        from server import create_app

        (tmp_path / "assets").mkdir()
        (tmp_path / "index.html").write_text("<!doctype html><title>EDUdata</title>")
        client = TestClient(create_app(api_docs=False, frontend_dist=tmp_path))

    resp = client.get(pad)

    assert resp.status_code == 404
    assert resp.json() == {"error": ONBEKEND_EINDPUNT}
    assert all(p in ONBEKEND_EINDPUNT for p in DASHBOARDS)
    assert loaders == []
