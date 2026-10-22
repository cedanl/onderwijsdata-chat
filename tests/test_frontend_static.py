"""Gehashte assets worden één keer geladen; index.html altijd vers, zodat een deploy direct doorkomt (#110)."""

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from core.foutmeldingen import NIET_GEVONDEN
from frontend_static import mount_frontend


def _client(tmp_path) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-Dk14s_LX.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<!doctype html><title>EDUdata</title>")
    app = FastAPI()
    mount_frontend(app, tmp_path)
    return TestClient(app)


def test_gehashte_asset_mag_een_jaar_in_de_cache(tmp_path):
    resp = _client(tmp_path).get("/assets/index-Dk14s_LX.js")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_index_html_wordt_altijd_opnieuw_gevraagd(tmp_path):
    client = _client(tmp_path)
    for pad in ("/", "/login", "/chat/123"):
        resp = client.get(pad)
        assert resp.status_code == 200
        assert "EDUdata" in resp.text
        assert resp.headers["cache-control"] == "no-cache"


def _client_met_pwa(tmp_path) -> TestClient:
    (tmp_path / "icons").mkdir()
    (tmp_path / "icons" / "icon-192.png").write_bytes(b"\x89PNG")
    (tmp_path / "manifest.webmanifest").write_text('{"name": "EDUdata"}')
    return _client(tmp_path)


def test_manifest_heeft_het_manifest_type_en_is_altijd_vers(tmp_path):
    """#669: zonder de route vangt de catch-all het pad en krijgt de browser index.html."""
    client = _client_met_pwa(tmp_path)
    for methode in (client.get, client.head):
        resp = methode("/manifest.webmanifest")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/manifest+json")
        assert resp.headers["cache-control"] == "no-cache"
    assert client.get("/manifest.webmanifest").json() == {"name": "EDUdata"}


def test_icoon_blijft_een_week_in_de_cache_maar_is_niet_immutable(tmp_path):
    resp = _client_met_pwa(tmp_path).get("/icons/icon-192.png")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=604800"


def test_dist_zonder_manifest_en_icons_start_en_geeft_geen_spa_als_manifest(tmp_path):
    # Een dist van vóór #669: de app start nog, en een browser krijgt geen index.html als manifest.
    resp = _client(tmp_path).get("/manifest.webmanifest")
    assert resp.status_code == 404
    assert resp.json() == {"detail": NIET_GEVONDEN}


def test_ontbrekende_asset_is_404_en_niet_de_spa(tmp_path):
    resp = _client(tmp_path).get("/assets/bestaat-niet.js")
    assert resp.status_code == 404
    assert "cache-control" not in resp.headers


def test_onbekende_api_route_is_json_404_en_niet_de_spa(tmp_path):
    """#482: een typfout in een API-pad gaf index.html met 200."""
    client = _client(tmp_path)
    for pad in ("/api", "/api/bestaat-niet", "/api/x/y/z"):
        resp = client.get(pad)
        assert resp.status_code == 404, pad
        assert resp.headers["content-type"].startswith("application/json"), pad
        # Nederlands en zonder het pad (#637); ook zonder geregistreerde foutafhandeling.
        assert resp.json() == {"detail": NIET_GEVONDEN}
        assert "bestaat-niet" not in resp.text
        assert "EDUdata" not in resp.text


def test_spa_route_die_op_api_lijkt_blijft_de_spa(tmp_path):
    # Alleen het segment /api is gereserveerd, niet elk pad dat met die letters begint.
    resp = _client(tmp_path).get("/apidocs")
    assert resp.status_code == 200
    assert "EDUdata" in resp.text


def test_echte_api_route_wint_van_de_catch_all(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>EDUdata</title>")
    app = FastAPI()

    @app.get("/api/ping")
    async def ping() -> dict:
        return {"pong": True}

    mount_frontend(app, tmp_path)
    resp = TestClient(app).get("/api/ping")
    assert resp.status_code == 200
    assert resp.json() == {"pong": True}


def test_websocket_onder_api_blijft_bereikbaar(tmp_path):
    # De catch-all is alleen GET over HTTP; /api/chat is een websocket.
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>EDUdata</title>")
    app = FastAPI()

    @app.websocket("/api/chat")
    async def chat(ws: WebSocket) -> None:
        await ws.accept()
        await ws.send_text("hallo")
        await ws.close()

    mount_frontend(app, tmp_path)
    with TestClient(app).websocket_connect("/api/chat") as ws:
        assert ws.receive_text() == "hallo"


# ── HEAD (#654) ──────────────────────────────────────────────────────────────


def _app_met_eigen_routes(tmp_path) -> FastAPI:
    """Een app met de SPA en een paar echte routes ervoor, zoals server.create_app ze opbouwt."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>EDUdata</title>")
    # Het schema onder /api, zoals in server.create_app: /openapi.json is dan een pad van de app-shell.
    app = FastAPI(openapi_url="/api/openapi.json")

    @app.get("/api/ping")
    async def ping() -> dict:
        return {"pong": True}

    @app.post("/api/bewaar")
    async def bewaar() -> dict:
        return {"ok": True}

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    mount_frontend(app, tmp_path)
    return app


@pytest.mark.parametrize("pad", ["/openapi.json", "/login", "/", "/chat/123", "/apidocs"])
def test_head_op_een_spa_pad_antwoordt_als_get(tmp_path, pad):
    """GET gaf de app-shell, HEAD een JSON-405: de HEAD-respons loog over de inhoud."""
    client = TestClient(_app_met_eigen_routes(tmp_path))

    get, head = client.get(pad), client.head(pad)

    assert get.status_code == head.status_code == 200
    assert head.headers["content-type"] == get.headers["content-type"]
    assert head.headers["content-type"].startswith("text/html")
    assert head.headers["content-length"] == get.headers["content-length"]
    assert head.headers["cache-control"] == get.headers["cache-control"] == "no-cache"
    assert head.content == b""


@pytest.mark.parametrize(
    "pad, allow",
    [("/api/ping", "GET"), ("/api/bewaar", "POST"), ("/api/bestaat-niet", "GET"), ("/api", "GET"), ("/health", "GET")],
)
def test_head_op_een_pad_van_een_echte_route_blijft_405(tmp_path, pad, allow):
    # Een pad dat een andere route kent, krijgt geen app-shell: anders zou HEAD /health of
    # HEAD /api/ping met 200 en text/html antwoorden, terwijl GET JSON geeft.
    resp = TestClient(_app_met_eigen_routes(tmp_path)).head(pad)

    assert resp.status_code == 405
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.headers["allow"] == allow


def test_get_onder_api_blijft_ongewijzigd_naast_head(tmp_path):
    client = TestClient(_app_met_eigen_routes(tmp_path))

    assert client.get("/api/ping").json() == {"pong": True}
    onbekend = client.get("/api/bestaat-niet")
    assert onbekend.status_code == 404
    assert onbekend.json() == {"detail": NIET_GEVONDEN}


def test_head_komt_niet_in_het_schema(tmp_path):
    paden = _app_met_eigen_routes(tmp_path).openapi()["paths"]

    assert paden["/{full_path}"].keys() == {"get"}
    assert not [pad for pad, ops in paden.items() if "head" in ops]
