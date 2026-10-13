"""De beveiligingsheaders van elk antwoord (SECURITY.md S13, #486).

De CSP stond `cdn.plot.ly` en `cdn.jsdelivr.net` toe in `script-src`; Plotly voor rapporten
en dashboards komt nu van de eigen server, dus er hoort geen derde partij meer in.
"""

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    from core import auth

    importlib.reload(auth)
    from persistence import db

    importlib.reload(db)
    db.init_db()
    import server

    importlib.reload(server)
    return TestClient(server.app)


def _richtlijnen(csp: str) -> dict[str, str]:
    return {naam: rest for naam, _, rest in (r.strip().partition(" ") for r in csp.split(";") if r.strip())}


def test_csp_laat_geen_derde_partij_toe_voor_scripts(client):
    csp = _richtlijnen(client.get("/health").headers["Content-Security-Policy"])
    assert csp["default-src"] == "'self'"
    assert "http" not in csp["script-src"], csp["script-src"]
    assert "'self'" in csp["script-src"]
    assert csp["frame-ancestors"] == "'none'"


def test_overige_beveiligingsheaders_staan_op_elk_antwoord(client):
    headers = client.get("/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "max-age=" in headers["Strict-Transport-Security"]


# #506: `connect-src 'self' wss: ws:` liet WebSockets naar elke host toe. De chat praat alleen met
# de eigen server (frontend/src/auth.js), dus alleen die: 'self' plus de expliciete wss-origin van
# SERVER_URL, omdat oudere Safari-versies 'self' niet op wss: laten slaan.
@pytest.mark.parametrize(
    "server_url, verwacht",
    [
        ("https://onderwijsdata-chat.test.sdp.surf.nl", "'self' wss://onderwijsdata-chat.test.sdp.surf.nl"),
        ("https://onderwijsdata-chat.test.sdp.surf.nl/", "'self' wss://onderwijsdata-chat.test.sdp.surf.nl"),
        ("http://localhost:8000", "'self' ws://localhost:8000"),
        (None, "'self'"),
        ("", "'self'"),
        ("geen-url", "'self'"),
    ],
)
def test_connect_src_alleen_de_eigen_server(server_url, verwacht):
    from server import connect_src

    assert connect_src(server_url) == verwacht


def test_csp_laat_geen_websocket_naar_een_andere_host_toe(client):
    csp = _richtlijnen(client.get("/health").headers["Content-Security-Policy"])
    bronnen = csp["connect-src"].split()
    assert "wss:" not in bronnen
    assert "ws:" not in bronnen
    assert bronnen[0] == "'self'"
