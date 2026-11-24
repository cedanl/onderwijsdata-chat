"""Foutmeldingen van de API in het Nederlands, zonder de invoer te herhalen (#637).

De handlers vervangen alleen wat FastAPI en Starlette zelf zeggen: pydantic's lijst bij een 422
en de standaardzinnen bij een 404 of 405. Wat een route zelf meldt, blijft zoals het was.
"""

import logging
import re
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


def test_server_verkeerde_methode_op_een_werkboek_is_nederlands(server_client):
    """Het werkboekpad kent GET, PUT en DELETE; een POST is 405, met en zonder dist (de catch-all is alleen GET)."""
    resp = server_client.post("/api/workbooks/bestaat-niet-424242")

    assert resp.status_code == 405
    assert resp.json() == {"detail": foutmeldingen.METHODE_NIET_TOEGESTAAN}
    # Starlette noemt de methoden van de eerste route die op het pad past; de header moet blijven staan.
    assert set(resp.headers["allow"].split(", ")) <= {"GET", "PUT", "DELETE"}
    _geen_engels_of_invoer(resp, "bestaat-niet", "424242")


def test_server_onbekend_werkboek_houdt_de_eigen_melding_van_de_route(server_client, monkeypatch):
    """Sinds #633 heeft het werkboekpad een GET; die meldt zelf een 404, de handler laat die tekst staan."""
    import server
    from core.auth import get_current_user

    monkeypatch.setitem(server.app.dependency_overrides, get_current_user, lambda: "demo")
    resp = server_client.get("/api/workbooks/bestaat-niet-424242")

    assert resp.status_code == 404
    assert resp.content == b'{"detail":"Rapport niet gevonden"}'


# ── Een onverwachte fout (#1154) ─────────────────────────────────────────────


@pytest.fixture
def storing(server_client, monkeypatch):
    """PUT /api/workbooks met een fout in de opslag, als `attempt to write a readonly database`; geen uitzondering in de test."""
    import server
    from persistence import db

    def stuk(*args, **kwargs):
        raise RuntimeError("geheim-host-424242 database geheim-db")

    monkeypatch.setattr(db, "upsert_workbook", stuk)
    return TestClient(server.app, raise_server_exceptions=False)


def test_een_onverwachte_fout_geeft_een_nederlandse_json_500_met_fout_id(storing, caplog):
    with caplog.at_level(logging.DEBUG):
        resp = storing.put("/api/workbooks/wb1", json={"title": "t"})

    assert resp.status_code == 500
    assert resp.headers["content-type"] == "application/json"
    fout_id = re.fullmatch(r"Er ging intern iets mis \(fout-ID (\w{8})\)\. .*", resp.json()["detail"])
    assert fout_id, resp.text
    _geen_engels_of_invoer(resp, "Internal Server Error", "geheim", "424242")
    # Het ID uit het antwoord staat in het log: één ERROR-regel met type en kenmerk, de traceback op DEBUG.
    fouten = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(fouten) == 1
    regel = fouten[0].getMessage()
    assert fout_id[1] in regel
    assert "RuntimeError fout_len=" in regel
    assert "geheim" not in regel
    assert [r for r in caplog.records if r.levelname == "DEBUG" and fout_id[1] in r.getMessage() and r.exc_info]


def test_de_500_draagt_dezelfde_headers_als_een_gewoon_api_antwoord(storing, server_client):
    gewoon = server_client.get("/api/config")
    resp = storing.put("/api/workbooks/wb1", json={"title": "t"})

    assert resp.status_code == 500
    assert resp.headers["cache-control"] == "no-store"
    for naam in (
        "content-security-policy",
        "x-content-type-options",
        "x-frame-options",
        "strict-transport-security",
        "referrer-policy",
        "permissions-policy",
        "cross-origin-opener-policy",
        "cross-origin-resource-policy",
    ):
        assert resp.headers[naam] == gewoon.headers[naam], naam


# ── Een body die niet te lezen is (#1162) ────────────────────────────────────


_ONLEESBAAR = {
    "ongeldige-utf8": b'{"title": "\xff\xfe"}',
    "te-diep-genest": b"[" * 100_000 + b"]" * 100_000,
    "kapotte-json": b"{bad json",
}


@pytest.mark.parametrize("inhoud", _ONLEESBAAR.values(), ids=_ONLEESBAAR)
def test_een_onleesbare_body_geeft_dezelfde_nederlandse_melding(inhoud):
    resp = TestClient(_app()).patch("/api/ding/x", content=inhoud, headers={"Content-Type": "application/json"})

    assert resp.status_code == 422
    assert resp.json() == {"detail": foutmeldingen.ONGELDIGE_INVOER}
    assert "parsing the body" not in resp.text
    _geen_engels_of_invoer(resp)


@pytest.mark.parametrize(
    "inhoud",
    [b'{"title":"\xff\xfe","timestamp":1,"messages":[]}', b"[" * 100_000 + b"]" * 100_000],
    ids=["ongeldige-utf8", "te-diep-genest"],
)
def test_server_onleesbare_body_op_een_gesprek_is_nederlands(server_client, inhoud):
    resp = server_client.put("/api/conversations/y", content=inhoud, headers={"Content-Type": "application/json"})

    assert resp.status_code == 422
    assert resp.json() == {"detail": foutmeldingen.ONGELDIGE_INVOER}
