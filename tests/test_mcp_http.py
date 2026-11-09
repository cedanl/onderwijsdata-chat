"""/mcp: de catalogustools van mcp_server.py over streamable HTTP in de app (#706).

Eind tot eind: de app uit server.create_app met haar lifespan, een echte MCP-client van de SDK over httpx2 met een
ASGI-transport (initialize, list_tools, call_tool), en losse HTTP-verzoeken voor de statuscodes.
"""

import json

import anyio
import httpx2
import pytest
from fastapi.testclient import TestClient
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

import mcp_server
import server
from core.foutmeldingen import NIET_GEVONDEN
from routes import mcp_http

SLEUTEL = "sleutel-a-0123456789abcdef"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
}
# Wat een MCP-client bij een POST meestuurt; zonder dit weigert de transport van de SDK het verzoek (406).
ACCEPT = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))


@pytest.fixture
def maak_app(monkeypatch, database):
    """Een app uit de fabriek met deze sleutels in MCP_API_KEYS."""

    def maak(*sleutels: str):
        monkeypatch.setattr(mcp_http, "MCP_API_KEYS", sleutels)
        return server.create_app(api_docs=False)

    return maak


def via_mcp(app, actie, *, koppen=None):
    """(initialize-resultaat, uitkomst van actie(sessie)) via een echte MCP-client tegen /mcp, binnen de lifespan."""
    koppen = {"Authorization": f"Bearer {SLEUTEL}"} if koppen is None else koppen

    async def draai():
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), headers=koppen) as http,
            streamable_http_client("http://test/mcp", http_client=http) as (lezen, schrijven),
            ClientSession(lezen, schrijven) as sessie,
        ):
            init = await sessie.initialize()
            return init, await actie(sessie)

    return anyio.run(draai)


# ── Transport (#706) ─────────────────────────────────────────────────────────────────────


def test_initialize_noemt_naam_versie_en_instructies(maak_app):
    init, _ = via_mcp(maak_app(SLEUTEL), lambda sessie: sessie.list_tools())
    assert init.server_info.name == mcp_server.NAAM
    assert init.server_info.version == mcp_server._versie()
    assert init.instructions == mcp_server.INSTRUCTIES


def test_list_tools_geeft_de_catalogustools_met_het_chatschema(maak_app):
    _, resultaat = via_mcp(maak_app(SLEUTEL), lambda sessie: sessie.list_tools())
    per_naam = {t.name: t for t in resultaat.tools}
    assert list(per_naam) == ["search_catalog", "dataset_details", "dataset_counts"]
    for definitie in mcp_server.tooldefinities():
        assert per_naam[definitie["name"]].input_schema == definitie["input_schema"]


def test_call_tool_geeft_hetzelfde_als_stdio(maak_app):
    """Dezelfde voer_uit als stdio: dezelfde envelope met bewijs en vervolg, scopegrens en statussen van de chat."""
    argumenten = {"query": "ingeschrevenen hbo", "top_n": 3}
    _, resultaat = via_mcp(maak_app(SLEUTEL), lambda sessie: sessie.call_tool("search_catalog", argumenten))
    assert not resultaat.is_error
    assert json.loads(resultaat.content[0].text) == json.loads(mcp_server.voer_uit("search_catalog", argumenten)[0])


def test_parameter_buiten_het_schema_is_een_fout(maak_app):
    _, resultaat = via_mcp(
        maak_app(SLEUTEL), lambda sessie: sessie.call_tool("search_catalog", {"query": "hbo", "onzin": 1})
    )
    assert resultaat.is_error
    assert "onbekende parameter: onzin" in resultaat.content[0].text


def test_scopegrens_geldt_ook_over_http(maak_app):
    """Een po/vo-tabel valt buiten mbo/hbo/wo, net als in de chat (#355): geen bron in het bewijs, geen vraag in de link."""
    argumenten = {"dataset_id": "cbs:80040ned"}
    _, resultaat = via_mcp(maak_app(SLEUTEL), lambda sessie: sessie.call_tool("dataset_details", argumenten))
    assert json.loads(resultaat.content[0].text) == json.loads(mcp_server.voer_uit("dataset_details", argumenten)[0])


def test_een_toolaanroep_houdt_de_event_loop_niet_vast(maak_app, monkeypatch):
    """voer_uit is synchroon (de eerste zoekactie laadt het DUO-register); over HTTP draait hij in een thread."""
    import threading

    threads = []

    def voer_uit(naam, argumenten):
        threads.append(threading.current_thread() is threading.main_thread())
        return '{"ok": true, "bewijs": {}, "vervolg": {}}', False

    monkeypatch.setattr(mcp_server, "voer_uit", voer_uit)
    via_mcp(maak_app(SLEUTEL), lambda sessie: sessie.call_tool("dataset_counts", {}))
    assert threads == [False]


def test_zonder_sleutels_is_mcp_er_niet(maak_app, caplog):
    """Fail-closed (#706, #939): zonder MCP_API_KEYS geeft /mcp 404, ook GET (geen index.html), en de start zegt waarom."""
    app = maak_app()
    with caplog.at_level("INFO", logger=mcp_http.__name__), TestClient(app) as client:
        post = client.post("/mcp", json=INITIALIZE, headers=ACCEPT | {"Authorization": f"Bearer {SLEUTEL}"})
        get = client.get("/mcp")
    assert (post.status_code, post.json()) == (404, {"detail": NIET_GEVONDEN})
    assert (get.status_code, get.json()) == (404, {"detail": NIET_GEVONDEN})
    uit = [r for r in caplog.records if "MCP_API_KEYS" in r.getMessage()]
    assert len(uit) == 1, "één keer bij de start, niet per verzoek"


def test_health_version_en_beveiligingsheaders_blijven(maak_app):
    with TestClient(maak_app(SLEUTEL)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/version").json()["version"]
        antwoord = client.post("/mcp", json=INITIALIZE, headers=ACCEPT | {"Authorization": f"Bearer {SLEUTEL}"})
    assert antwoord.status_code == 200
    assert antwoord.json()["result"]["serverInfo"]["name"] == mcp_server.NAAM
    assert antwoord.headers["content-type"].startswith("application/json"), "stateless met JSON-antwoorden, geen SSE"
    assert "mcp-session-id" not in antwoord.headers, "stateless: geen sessie per client"
    assert antwoord.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("methode", ["GET", "DELETE"])
def test_alleen_post(maak_app, methode):
    """Stateless geen GET-stroom: de SDK hield een GET met Accept text/event-stream open zonder ooit iets te sturen."""
    koppen = {"Accept": "text/event-stream", "Authorization": f"Bearer {SLEUTEL}"}
    with TestClient(maak_app(SLEUTEL)) as client:
        antwoord = client.request(methode, "/mcp", headers=koppen)
    assert antwoord.status_code == 405
    assert antwoord.headers["allow"] == "POST"


def test_de_app_start_vaker_met_dezelfde_fabriek(maak_app):
    """De sessiemanager van de SDK draait maar één keer; een tweede start (tests, herstart) maakt een nieuwe."""
    app = maak_app(SLEUTEL)
    for _ in range(2):
        with TestClient(app) as client:
            koppen = ACCEPT | {"Authorization": f"Bearer {SLEUTEL}"}
            assert client.post("/mcp", json=INITIALIZE, headers=koppen).status_code == 200


# ── API-sleutel (#939) ───────────────────────────────────────────────────────────────────

ANDERE = "sleutel-b-fedcba9876543210"


def _initialize(app, koppen: dict[str, str]):
    with TestClient(app) as client:
        return client.post("/mcp", json=INITIALIZE, headers=ACCEPT | koppen)


@pytest.mark.parametrize(
    "koppen",
    [
        {},
        {"Authorization": "Bearer verkeerd"},
        {"Authorization": f"Bearer {SLEUTEL}x"},
        {"Authorization": f"Basic {SLEUTEL}"},
        {"Authorization": SLEUTEL},
        {"Authorization": "Bearer "},
    ],
    ids=["geen", "ongeldig", "langer", "basic", "zonder-schema", "leeg"],
)
def test_zonder_geldige_sleutel_401(maak_app, koppen):
    antwoord = _initialize(maak_app(SLEUTEL), koppen)
    assert antwoord.status_code == 401
    assert antwoord.headers["www-authenticate"] == "Bearer"
    assert SLEUTEL not in antwoord.text


def test_geldige_sleutel_200(maak_app):
    assert _initialize(maak_app(SLEUTEL), {"Authorization": f"Bearer {SLEUTEL}"}).status_code == 200
    assert _initialize(maak_app(SLEUTEL), {"Authorization": f"bearer {SLEUTEL}"}).status_code == 200


def test_twee_sleutels_tegelijk_geldig(maak_app):
    """Roteren zonder onderbreking: oude en nieuwe sleutel werken naast elkaar, een derde niet."""
    app = maak_app(SLEUTEL, ANDERE)
    for sleutel in (SLEUTEL, ANDERE):
        assert _initialize(app, {"Authorization": f"Bearer {sleutel}"}).status_code == 200
    assert _initialize(app, {"Authorization": "Bearer derde"}).status_code == 401


def test_de_client_van_de_sdk_met_een_foute_sleutel_komt_er_niet_in(maak_app):
    from mcp.shared.exceptions import MCPError

    with pytest.raises((MCPError, ExceptionGroup, httpx2.HTTPStatusError)):
        via_mcp(maak_app(SLEUTEL), lambda sessie: sessie.list_tools(), koppen={"Authorization": "Bearer fout"})


def test_de_sleutel_staat_niet_in_het_log_wel_een_sleutel_id(maak_app, caplog):
    from core.logging_util import tekst_kenmerk

    app = maak_app(SLEUTEL, ANDERE)
    with caplog.at_level("DEBUG"):
        via_mcp(app, lambda sessie: sessie.call_tool("dataset_counts", {}))
        _initialize(app, {"Authorization": f"Bearer {ANDERE}x"})
        _initialize(app, {})
    log = "\n".join(r.getMessage() for r in caplog.records)
    assert SLEUTEL not in log and ANDERE not in log
    tool = [r.getMessage() for r in caplog.records if r.getMessage().startswith("MCP TOOL dataset_counts")]
    assert len(tool) == 1
    assert tekst_kenmerk(SLEUTEL, "sleutel_") in tool[0], "het log noemt welke consument de aanroep deed"
    assert any("MCP 401" in r.getMessage() for r in caplog.records)
