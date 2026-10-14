"""GET /api/auth/session: geldt dit token nog? In beide modi, zonder gebruikersgegevens (#499).

De frontend vraagt het na een geweigerde chat-socket (een kale close 1006). /api/auth/user bestaat alleen
met OIDC, dus in wachtwoordmodus bleef die vraag onbeantwoord en eindigde de sessie niet.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from tests import test_token_intrekking as intrekking
from tests.test_token_intrekking import _bearer, _token, _zet_klok

# De fixtures van de intrekkingstests: client is wachtwoordmodus, oidc_client heeft de OIDC-routes.
database = intrekking.database
client = intrekking.client
oidc_client = intrekking.oidc_client

START = 1_800_000_000


def _geldig(c, monkeypatch) -> dict:
    return _bearer(_token())


def _zonder(c, monkeypatch) -> dict:
    return {}


def _misvormd(c, monkeypatch) -> dict:
    return _bearer("onzin")


def _vervalst(c, monkeypatch) -> dict:
    payload = _token().rsplit(".", 1)[0]
    return _bearer(f"{payload}.{'0' * 64}")


def _verlopen(c, monkeypatch) -> dict:
    from core import auth

    klok = _zet_klok(monkeypatch, START)
    token = _token()
    klok.t = START + auth.SESSION_TTL + 1
    return _bearer(token)


def _ingetrokken(c, monkeypatch) -> dict:
    token = _token()
    assert c.post("/api/auth/logout", headers=_bearer(token)).status_code == 204
    return _bearer(token)


GEVALLEN = [
    pytest.param(_geldig, 204, id="geldig"),
    pytest.param(_zonder, 401, id="zonder-token"),
    pytest.param(_misvormd, 401, id="misvormd"),
    pytest.param(_vervalst, 401, id="vervalst"),
    pytest.param(_verlopen, 401, id="verlopen"),
    pytest.param(_ingetrokken, 401, id="ingetrokken"),
]


# ── Criterium 1 en 4: wachtwoordmodus ────────────────────────────────────────


@pytest.mark.parametrize(("geval", "status"), GEVALLEN)
def test_wachtwoordmodus(client, monkeypatch, geval, status):
    resp = client.get("/api/auth/session", headers=geval(client, monkeypatch))

    assert resp.status_code == status
    assert resp.content == b""
    assert resp.headers["cache-control"] == "no-store"


# ── Criterium 2 en 4: OIDC-modus geeft hetzelfde oordeel als /api/auth/user ──


@pytest.mark.parametrize(("geval", "status"), GEVALLEN)
def test_oidc_modus_volgt_de_gebruikersroute(oidc_client, monkeypatch, geval, status):
    headers = geval(oidc_client, monkeypatch)

    sessie = oidc_client.get("/api/auth/session", headers=headers)
    gebruiker = oidc_client.get("/api/auth/user", headers=headers)

    assert sessie.status_code == status
    assert sessie.content == b""
    assert gebruiker.status_code == {204: 200, 401: 401}[status]


# ── Criterium 3: zonder login ────────────────────────────────────────────────


@pytest.mark.parametrize("headers", [{}, _bearer("wat-dan-ook")])
def test_zonder_login_geeft_204(monkeypatch, headers):
    import server
    from core import auth

    monkeypatch.setattr(auth, "AUTH_ENABLED", False)

    resp = TestClient(server.app).get("/api/auth/session", headers=headers)

    assert resp.status_code == 204
    assert resp.content == b""


# ── Criterium 5: de OIDC-routes blijven weg in wachtwoordmodus ───────────────


def test_wachtwoordmodus_heeft_nog_steeds_geen_gebruikers_of_ververs_route(client):
    # De geregistreerde routes, niet de statuscode van een POST: met een gebouwde frontend (frontend/dist) vangt
    # de GET-catch-all /api/{rest} de POST op /refresh en geeft dan 405 in plaats van 404. Het OpenAPI-schema,
    # omdat app.routes ingesloten routers niet uitvouwt; /session bewijst dat de auth-routes erin staan.
    paden = client.app.openapi()["paths"]

    assert "/api/auth/session" in paden
    assert "/api/auth/user" not in paden
    assert "/api/auth/refresh" not in paden
    assert client.get("/api/auth/user", headers=_bearer(_token())).status_code == 404


# ── Een databasestoring is geen "sessie voorbij" ────────────────────────────


def test_databasestoring_geeft_500_en_geen_401(client, monkeypatch):
    from persistence import db

    def storing(token_hash):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "is_token_revoked", storing)
    client = TestClient(client.app, raise_server_exceptions=False)

    assert client.get("/api/auth/session", headers=_bearer(_token())).status_code == 500
