"""Gehashte assets worden één keer geladen; index.html altijd vers, zodat een deploy direct doorkomt (#110)."""

from fastapi import FastAPI
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
