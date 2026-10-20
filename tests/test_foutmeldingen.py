"""Foutmeldingen van de API in het Nederlands, zonder de invoer te herhalen (#637).

De handlers vervangen alleen wat FastAPI en Starlette zelf zeggen: pydantic's lijst bij een 422
en de standaardzinnen bij een 404 of 405. Wat een route zelf meldt, blijft zoals het was.
"""

from typing import Annotated

import pytest
from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel

from core import foutmeldingen
from frontend_static import mount_frontend

_ENGELS = ("Field required", "Input should", "Not Found", "Method Not Allowed")


class _Titel(BaseModel):
    title: str


def _app() -> FastAPI:
    app = FastAPI()
    foutmeldingen.registreer(app)

    @app.get("/api/lijst")
    def lijst(limit: Annotated[int, Query(ge=1, le=50)] = 15) -> dict:
        return {"limit": limit}

    @app.patch("/api/ding/{ding_id}")
    def hernoem(ding_id: str, body: _Titel) -> dict:
        return {"ok": True}

    @app.put("/api/werkboek/{wb_id}")
    def bewaar(wb_id: str) -> dict:
        return {"ok": True}

    @app.get("/api/eigen-404")
    def eigen_404() -> dict:
        raise HTTPException(status_code=404, detail="Gesprek niet gevonden")

    @app.get("/api/eigen-429")
    def eigen_429() -> dict:
        raise HTTPException(status_code=429, detail="Te veel verzoeken", headers={"Retry-After": "7"})

    return app


def _geen_engels_of_invoer(resp, *invoer: str) -> None:
    for tekst in (*_ENGELS, *invoer):
        assert tekst not in resp.text, tekst


@pytest.mark.parametrize("limit", ["999777", "0", "geen-getal"])
def test_ongeldige_query_geeft_een_nederlandse_string(limit):
    resp = TestClient(_app()).get("/api/lijst", params={"limit": limit})

    assert resp.status_code == 422
    assert resp.json() == {"detail": foutmeldingen.ONGELDIGE_INVOER}
    _geen_engels_of_invoer(resp, "999777", "geen-getal", "input", "ctx", "loc")


def test_ontbrekend_veld_in_de_body_geeft_dezelfde_vorm():
    resp = TestClient(_app()).patch("/api/ding/x", json={"titel": "merk-424242"})

    assert resp.status_code == 422
    assert resp.json() == {"detail": foutmeldingen.ONGELDIGE_INVOER}
    _geen_engels_of_invoer(resp, "merk-424242")


@pytest.mark.parametrize("pad", ["/api/bestaat-niet-31337", "/api", "/nergens"])
def test_onbekende_route_is_een_nederlandse_404_zonder_het_pad(pad):
    resp = TestClient(_app()).get(pad)

    assert resp.status_code == 404
    assert resp.json() == {"detail": foutmeldingen.NIET_GEVONDEN}
    _geen_engels_of_invoer(resp, "31337", "nergens")


def test_verkeerde_methode_is_nederlands_en_houdt_de_allow_header():
    resp = TestClient(_app()).get("/api/werkboek/bestaat-niet")

    assert resp.status_code == 405
    assert resp.json() == {"detail": foutmeldingen.METHODE_NIET_TOEGESTAAN}
    assert resp.headers["allow"] == "PUT"
    _geen_engels_of_invoer(resp, "bestaat-niet")


def test_een_eigen_melding_van_een_route_blijft_gelijk():
    resp = TestClient(_app()).get("/api/eigen-404")

    assert resp.status_code == 404
    assert resp.content == b'{"detail":"Gesprek niet gevonden"}'


def test_headers_van_een_eigen_httpexception_blijven_staan():
    resp = TestClient(_app()).get("/api/eigen-429")

    assert resp.status_code == 429
    assert resp.json() == {"detail": "Te veel verzoeken"}
    assert resp.headers["retry-after"] == "7"


def _met_frontend(tmp_path) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>EDUdata</title>")
    app = _app()
    mount_frontend(app, tmp_path)
    return TestClient(app)


@pytest.mark.parametrize("pad", ["/api/bestaat-niet", "/api/werkboek/bestaat-niet"])
def test_met_gebouwde_frontend_is_een_onbekende_api_get_dezelfde_404(tmp_path, pad):
    resp = _met_frontend(tmp_path).get(pad)

    assert resp.status_code == 404
    assert resp.json() == {"detail": foutmeldingen.NIET_GEVONDEN}
    _geen_engels_of_invoer(resp, "bestaat-niet")


# ── De echte app ─────────────────────────────────────────────────────────────


@pytest.fixture
def server_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    db.init_db()
    import server

    return TestClient(server.app)


def test_server_onbekende_api_route_is_nederlands(server_client):
    """Met en zonder frontend/dist: zonder dist antwoordt de handler, met dist de catch-all."""
    resp = server_client.get("/api/bestaat-niet")

    assert resp.status_code == 404
    assert resp.json() == {"detail": foutmeldingen.NIET_GEVONDEN}


def test_server_workbook_zonder_get_route_is_nederlands(server_client):
    """Met dist vangt de catch-all de GET (404); zonder dist bestaat het pad alleen voor PUT en DELETE (405)."""
    resp = server_client.get("/api/workbooks/bestaat-niet")

    verwacht = {404: foutmeldingen.NIET_GEVONDEN, 405: foutmeldingen.METHODE_NIET_TOEGESTAAN}
    assert resp.status_code in verwacht
    assert resp.json() == {"detail": verwacht[resp.status_code]}
    _geen_engels_of_invoer(resp, "bestaat-niet")
