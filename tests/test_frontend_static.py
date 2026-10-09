"""Gehashte assets worden één keer geladen; index.html altijd vers, zodat een deploy direct doorkomt (#110)."""

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

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
        assert resp.json() == {"detail": "Not Found"}
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
