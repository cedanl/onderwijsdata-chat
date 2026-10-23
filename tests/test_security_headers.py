"""De beveiligingsheaders van elk antwoord (SECURITY.md S13, #486).

De CSP stond `cdn.plot.ly` en `cdn.jsdelivr.net` toe in `script-src`; Plotly voor rapporten
en dashboards komt nu van de eigen server, dus er hoort geen derde partij meer in.
"""

import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

DOCKERFILE = Path(__file__).parent.parent / "Dockerfile"


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


# #534: de middleware zette een lege `Server`-header naast uvicorns eigen `Server: uvicorn`, zodat
# het antwoord er twee had. Uvicorn start nu met `--no-server-header` en de middleware zet er geen meer.
# TestClient gaat buiten uvicorn om, dus de vlag zelf staat in een aparte test op de Dockerfile.
def test_antwoord_heeft_geen_server_header(client):
    assert "server" not in client.get("/health").headers


def _dockerfile_cmd() -> list[str]:
    regels = [r for r in DOCKERFILE.read_text().splitlines() if r.startswith("CMD ")]
    return json.loads(regels[-1].removeprefix("CMD "))


def test_dockerfile_start_uvicorn_zonder_server_header():
    cmd = _dockerfile_cmd()
    assert cmd[:2] == [".venv/bin/uvicorn", "server:app"]
    assert "--no-server-header" in cmd


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


# #632: maplibre (de kaart van create_choropleth_map) start zijn worker vanaf een blob:-URL. Zonder worker-src viel
# dat terug op script-src, waar blob: niet in staat, en bleef de kaart leeg. Alleen worker-src krijgt blob:.
def test_csp_staat_de_kaartworker_toe_vanaf_blob(client):
    csp = _richtlijnen(client.get("/health").headers["Content-Security-Policy"])
    assert csp["worker-src"] == "'self' blob:"
    assert "blob:" not in csp["script-src"]
    assert "http" not in csp["script-src"]


def test_csp_wijzigt_naast_worker_src_geen_andere_richtlijn(client):
    csp = _richtlijnen(client.get("/health").headers["Content-Security-Policy"])
    csp.pop("connect-src")  # hangt af van SERVER_URL, zie hierboven
    assert csp == {
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline'",
        "style-src": "'self' 'unsafe-inline'",
        "img-src": "'self' data: blob:",
        "worker-src": "'self' blob:",
        "font-src": "'self'",
        "frame-ancestors": "'none'",
        "base-uri": "'self'",
        "form-action": "'self'",
    }


# #682: een geïnjecteerde <base href> zou elke relatieve URL (ook /assets voor Plotly) naar een andere host sturen,
# en een geïnjecteerd <form> kan ingevulde tekst naar buiten posten. default-src dekt geen van beide.
def test_csp_sluit_base_en_formulieren_naar_buiten_uit(client):
    csp = _richtlijnen(client.get("/health").headers["Content-Security-Policy"])
    assert csp["base-uri"] == "'self'"
    assert csp["form-action"] == "'self'"


# #682: API-antwoorden (gesprekken, werkboeken, instellingen) horen niet in de browsercache of een proxy.
@pytest.mark.parametrize("pad", ["/api/conversations", "/api/workbooks", "/api/bestaat-niet"])
def test_api_antwoorden_worden_niet_bewaard(client, pad):
    assert client.get(pad).headers["Cache-Control"] == "no-store"


def test_buiten_de_api_geen_no_store(client):
    """De build en index.html houden hun eigen cachebeleid (frontend_static.py)."""
    assert "no-store" not in client.get("/health").headers.get("Cache-Control", "")


# #636: de app gebruikt geen camera, microfoon, locatie, betalingen of usb; een ingesloten of
# geïnjecteerd script mag ze dan ook niet vragen.
def test_permissions_policy_zet_ongebruikte_browserfuncties_uit(client):
    beleid = {
        naam.strip(): waarde.strip()
        for naam, _, waarde in (
            r.partition("=") for r in client.get("/health").headers["Permissions-Policy"].split(",")
        )
    }
    for functie in ("camera", "microphone", "geolocation", "payment", "usb"):
        assert beleid[functie] == "()", functie


def test_permissions_policy_staat_ook_op_een_foutantwoord(client):
    assert "Permissions-Policy" in client.get("/api/bestaat-niet").headers


# #690: COOP en CORP. Het rapportframe heeft een opake origin (alleen allow-scripts) en laadt Plotly van /assets,
# dus daar cross-origin; de rest, ook de API en de SPA, alleen voor de eigen origin.
def test_geen_window_referentie_naar_een_andere_origin(client):
    assert client.get("/health").headers["Cross-Origin-Opener-Policy"] == "same-origin"


@pytest.mark.parametrize("pad", ["/health", "/api/bestaat-niet", "/version"])
def test_andere_origins_sluiten_geen_antwoord_in(client, pad):
    assert client.get(pad).headers["Cross-Origin-Resource-Policy"] == "same-origin"


def test_het_rapportframe_mag_de_build_onder_assets_laden(tmp_path):
    from server import create_app

    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "plotly-rapport.min-abc.js").write_text("/* plotly */")
    (tmp_path / "index.html").write_text("<!doctype html><title>EDUdata</title>")
    client = TestClient(create_app(frontend_dist=tmp_path))

    assert client.get("/assets/plotly-rapport.min-abc.js").headers["Cross-Origin-Resource-Policy"] == "cross-origin"
    assert client.get("/").headers["Cross-Origin-Resource-Policy"] == "same-origin"
    # Geen COEP: zie SECURITY.md S3.
    assert "Cross-Origin-Embedder-Policy" not in client.get("/").headers
