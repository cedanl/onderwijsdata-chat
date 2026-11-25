"""GET /metrics voor de productiemonitoring (#678; core/metrics.py, routes/metrics.py).

Toegang: zonder METRICS_TOKEN 404, met token alleen met de juiste bearer. Inhoud: HTTP-verzoeken per routesjabloon, de
tellers per pod uit core/gelijktijdig.py, modelaanroepen, sandbox, limieten en de terugval van een limiet naar het
geheugen. Geen label draagt een gebruikersnaam, pseudoniem of vraagtekst.

De metrics zijn van het proces en tellen over tests heen: elke test kijkt naar het verschil.
"""

import asyncio
import urllib.parse
from typing import Any

import pytest
from prometheus_client import REGISTRY
from prometheus_client.parser import text_string_to_metric_families

from agent import loop
from agent.stream import Tokens
from core import metrics
from core.gelijktijdig import Procesplaatsen, Runplaatsen, Verbindingen
from core.rate_limit import RateLimiter
from tools import sandbox

TOKEN = "metrics-test-token-1"
GEBRUIKER = "anna.devries@hu.nl"
VRAAG = "Hoeveel studenten volgen geheimvak-xyz aan de HU?"

# De labels die een reeks van de app mag dragen; alles daarbuiten kan groeien met gebruikers of tekst.
_LABELS = {
    "method",
    "route",
    "status",
    "model",
    "outcome",
    "direction",
    "limiter",
    "pool",
    "counter",
    "le",
    "controle",
    "uitkomst",
    "tool",
    "reden",
}


def _waarde(naam: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(naam, labels) or 0.0


def _bearer(token: str = TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ingelogd() -> dict[str, str]:
    """De header van GEBRUIKER, zonder /api/auth/login.

    routes.auth leest CHAT_USERS bij het importeren; heeft een eerdere test die module met andere gebruikers geladen,
    dan geeft de login in de volle testrun 401. Ook telt de login-limiter over de hele testrun mee.
    """
    from core import auth

    return {"Authorization": f"Bearer {auth.make_token(GEBRUIKER)}"}


@pytest.fixture
def client(app_client, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", TOKEN)
    return app_client(users=f"{GEBRUIKER}:wachtwoord-a")


# ── Toegang ──────────────────────────────────────────────────────────────────


def test_zonder_token_bestaat_het_eindpunt_niet(app_client, monkeypatch):
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    monkeypatch.setattr(metrics_route().config, "METRICS_TOKEN", None)
    c = app_client()
    for headers in ({}, _bearer()):
        resp = c.get("/metrics", headers=headers)
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Niet gevonden"}


def test_een_token_uit_de_config_telt_ook(app_client, monkeypatch):
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    monkeypatch.setattr(metrics_route().config, "METRICS_TOKEN", TOKEN)
    c = app_client()
    assert c.get("/metrics", headers=_bearer()).status_code == 200
    assert c.get("/metrics").status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        {},
        _bearer("fout"),
        _bearer(TOKEN + "x"),
        _bearer(""),
        {"Authorization": TOKEN},
        {"Authorization": f"Basic {TOKEN}"},
    ],
    ids=["zonder", "fout", "langer", "leeg", "zonder-bearer", "basic"],
)
def test_met_token_zonder_de_juiste_bearer_401(client, headers):
    resp = client.get("/metrics", headers=headers)
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"
    assert "edudata" not in resp.text


def test_met_de_juiste_bearer_het_tekstformaat_van_prometheus(client):
    resp = client.get("/metrics", headers=_bearer())
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert resp.headers["cache-control"] == "no-store"
    namen = {f.name for f in text_string_to_metric_families(resp.text)}
    assert {"edudata_http_requests", "edudata_websockets_open", "edudata_runs_running"} <= namen


def test_niet_in_het_openapi_schema():
    from server import create_app

    schema = create_app(api_docs=True).openapi()
    assert "/metrics" not in schema["paths"]


# ── HTTP per routesjabloon ───────────────────────────────────────────────────


def test_een_verzoek_telt_onder_zijn_routesjabloon(client):
    voor = _waarde("edudata_http_requests_total", method="GET", route="/health", status="200")
    duur_voor = _waarde("edudata_http_request_duration_seconds_count", method="GET", route="/health")
    assert client.get("/health").status_code == 200

    tekst = client.get("/metrics", headers=_bearer()).text
    assert 'edudata_http_requests_total{method="GET",route="/health",status="200"}' in tekst
    assert _waarde("edudata_http_requests_total", method="GET", route="/health", status="200") == voor + 1
    assert _waarde("edudata_http_request_duration_seconds_count", method="GET", route="/health") == duur_voor + 1


def test_een_pad_met_parameter_telt_onder_het_sjabloon_niet_onder_het_pad(client):
    resp = client.get("/api/conversations/gesprek-van-anna-123", headers=_ingelogd())
    assert resp.status_code == 404

    tekst = client.get("/metrics", headers=_bearer()).text
    assert 'route="/api/conversations/{conv_id}"' in tekst
    assert "gesprek-van-anna-123" not in tekst


def test_een_5xx_telt_in_de_5xx_reeks(client, monkeypatch):
    import health

    async def kapot():
        raise RuntimeError("stuk")

    monkeypatch.setattr(health, "health_check", kapot)
    voor = _waarde("edudata_http_server_errors_total", method="GET", route="/health")
    voor_500 = _waarde("edudata_http_requests_total", method="GET", route="/health", status="500")

    assert client.get("/health").status_code == 500

    assert _waarde("edudata_http_server_errors_total", method="GET", route="/health") == voor + 1
    assert _waarde("edudata_http_requests_total", method="GET", route="/health", status="500") == voor_500 + 1


def test_een_503_van_ready_telt_ook_als_5xx(client, monkeypatch):
    import health

    async def niet_klaar():
        return {"status": "not_ready", "checks": {}}, 503

    monkeypatch.setattr(health, "readiness_check", niet_klaar)
    voor = _waarde("edudata_http_server_errors_total", method="GET", route="/ready")
    assert client.get("/ready").status_code == 503
    assert _waarde("edudata_http_server_errors_total", method="GET", route="/ready") == voor + 1


def test_een_onbekende_methode_krijgt_geen_eigen_label():
    assert metrics.methode_label("GET") == "GET"
    assert metrics.methode_label("VERZIN-IETS") == "ANDERS"


# ── Gauges per pod (core/gelijktijdig.py) ────────────────────────────────────


def test_open_verbindingen_en_lopende_runs_als_gauges(monkeypatch):
    verbindingen = Verbindingen(per_sleutel=3, totaal=10)
    monkeypatch.setattr(metrics, "_verbindingen", [])
    monkeypatch.setattr(metrics, "_plaatsen", {})
    metrics.volg_verbindingen(verbindingen)
    runs = Runplaatsen(max_tegelijk=2, wacht_s=0.1)
    metrics.volg_plaatsen("chat", runs)
    processen = Procesplaatsen(max_tegelijk=1, wacht_s=0.1)
    metrics.volg_plaatsen("sandbox", processen)

    assert verbindingen.open(GEBRUIKER) and verbindingen.open(GEBRUIKER) and verbindingen.open(None)

    async def in_een_run():
        async with runs.plaats():
            return _waarde("edudata_runs_running", pool="chat")

    with processen.plaats() as vrij:
        assert vrij
        assert _waarde("edudata_sandbox_running") == 1
    assert asyncio.run(in_een_run()) == 1
    assert _waarde("edudata_runs_running", pool="chat") == 0
    assert _waarde("edudata_sandbox_running") == 0
    assert _waarde("edudata_websockets_open") == 3
    assert _waarde("edudata_websockets_per_user_max") == 2
    assert _waarde("edudata_concurrency_limit", counter="websockets_per_user") == 3
    assert _waarde("edudata_concurrency_limit", counter="websockets_total") == 10
    assert _waarde("edudata_concurrency_limit", counter="chat") == 2


def test_de_app_volgt_haar_eigen_tellers(client):
    from routes import chat

    tekst = client.get("/metrics", headers=_bearer()).text
    assert "edudata_websockets_open " in tekst
    assert 'edudata_runs_running{pool="chat"}' in tekst
    assert 'edudata_runs_running{pool="dashboard"}' in tekst
    assert "edudata_sandbox_running " in tekst
    assert metrics._verbindingen == [chat._verbindingen]


# ── Modelaanroepen ───────────────────────────────────────────────────────────


def test_een_modelaanroep_telt_met_uitkomst_duur_en_eerste_chunk(monkeypatch):
    model = "mock/default"
    voor = {
        "ok": _waarde("edudata_model_calls_total", model=model, outcome="ok"),
        "fout": _waarde("edudata_model_calls_total", model=model, outcome="fout"),
        "fouten": _waarde("edudata_model_call_errors_total", model=model),
        "duur": _waarde("edudata_model_call_duration_seconds_count", model=model),
        "chunk": _waarde("edudata_model_first_chunk_seconds_count", model=model),
    }
    monkeypatch.setattr(loop.time, "monotonic", lambda: 105.0)
    loop._log_aanroep(model, loop._Aanroepmeting(start=100.0, open=101.0, eerste_chunk=102.0, uitvoer=10))
    loop._log_aanroep(model, loop._Aanroepmeting(start=100.0, uitkomst="APIConnectionError"))

    assert _waarde("edudata_model_calls_total", model=model, outcome="ok") == voor["ok"] + 1
    assert _waarde("edudata_model_calls_total", model=model, outcome="fout") == voor["fout"] + 1
    assert _waarde("edudata_model_call_errors_total", model=model) == voor["fouten"] + 1
    assert _waarde("edudata_model_call_duration_seconds_count", model=model) == voor["duur"] + 2
    assert _waarde("edudata_model_first_chunk_seconds_count", model=model) == voor["chunk"] + 1
    # Het fouttype zelf is geen label: dat is een open verzameling.
    assert _waarde("edudata_model_calls_total", model=model, outcome="APIConnectionError") == 0


def test_de_tokens_van_een_run_tellen_per_richting():
    model = "mock/tokens"
    voor_in = _waarde("edudata_model_tokens_total", model=model, direction="input")
    voor_uit = _waarde("edudata_model_tokens_total", model=model, direction="output")
    resultaat = loop.LoopResult()
    resultaat.tokens = Tokens(invoer=1200, uitvoer=34)
    loop._log_tokens(model, resultaat)
    assert _waarde("edudata_model_tokens_total", model=model, direction="input") == voor_in + 1200
    assert _waarde("edudata_model_tokens_total", model=model, direction="output") == voor_uit + 34


# ── Sandbox ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("uitkomst", "soort"),
    [
        (sandbox.Uitkomst(result=1), "ok"),
        (sandbox.Uitkomst(fout=sandbox.TIJDSLIMIET.format(s=sandbox.TIMEOUT_SECONDS)), "timeout"),
        (sandbox.Uitkomst(fout=sandbox.GESTOPT), "gestopt"),
        (sandbox.Uitkomst(fout="NameError: x"), "fout"),
    ],
)
def test_een_sandboxrun_telt_per_uitkomst(monkeypatch, uitkomst, soort):
    monkeypatch.setattr(sandbox, "_voer_uit", lambda *_: uitkomst)
    voor = _waarde("edudata_sandbox_runs_total", outcome=soort)
    voor_timeouts = _waarde("edudata_sandbox_timeouts_total")
    assert sandbox.voer_uit("1", None, {}) is uitkomst
    assert _waarde("edudata_sandbox_runs_total", outcome=soort) == voor + 1
    assert _waarde("edudata_sandbox_timeouts_total") == voor_timeouts + (soort == "timeout")


def test_een_volle_sandbox_telt_als_bezet_en_als_weigering(monkeypatch):
    vol = Procesplaatsen(max_tegelijk=1, wacht_s=0.01)
    monkeypatch.setattr(sandbox, "_PROCESSEN", vol)
    voor = _waarde("edudata_sandbox_runs_total", outcome="bezet")
    voor_weigering = _waarde("edudata_limiter_refusals_total", limiter="sandbox")
    with vol.plaats():
        assert sandbox.voer_uit("1", None, {}).fout == sandbox.BEZET
    assert _waarde("edudata_sandbox_runs_total", outcome="bezet") == voor + 1
    assert _waarde("edudata_limiter_refusals_total", limiter="sandbox") == voor_weigering + 1


# ── Limieten ─────────────────────────────────────────────────────────────────


def test_een_rate_limit_weigering_telt_onder_de_naam_van_de_limiet(monkeypatch):
    from persistence import db

    monkeypatch.setattr(db, "deelt_staat", lambda: False)
    limiet = RateLimiter(max_attempts=1, window_seconds=60, naam="login")
    voor = _waarde("edudata_limiter_refusals_total", limiter="login")
    assert limiet.probeer(GEBRUIKER) is None
    assert limiet.probeer(GEBRUIKER) is not None
    assert limiet.retry_after(GEBRUIKER) is not None  # alleen kijken telt niet
    assert _waarde("edudata_limiter_refusals_total", limiter="login") == voor + 1


def test_de_terugval_naar_het_geheugen_telt(monkeypatch):
    from persistence import db

    def weg(*_args, **_kwargs):
        raise RuntimeError("database weg")

    monkeypatch.setattr(db, "deelt_staat", lambda: True)
    monkeypatch.setattr(db, "rate_limit_poging", weg)
    limiet = RateLimiter(max_attempts=5, window_seconds=60, naam="bericht")
    voor = _waarde("edudata_limiter_db_fallback_total", limiter="bericht")
    assert limiet.probeer(GEBRUIKER) is None  # fail-open: het geheugen telt
    assert _waarde("edudata_limiter_db_fallback_total", limiter="bericht") == voor + 1


def test_een_volle_runplaats_in_de_chat_telt_als_weigering(monkeypatch):
    from routes import chat

    monkeypatch.setattr(chat, "_runplaatsen", Runplaatsen(max_tegelijk=1, wacht_s=0.01))
    voor = _waarde("edudata_limiter_refusals_total", limiter="runplaatsen_chat")
    meldingen: list[dict] = []

    async def emit(event):
        meldingen.append(event)

    async def start():
        raise AssertionError("geen run zonder plaats")

    async def vol():
        async with chat._runplaatsen.plaats():
            await chat._in_een_runplaats(start, emit)

    asyncio.run(vol())
    assert meldingen and meldingen[0]["type"] == "error"
    assert _waarde("edudata_limiter_refusals_total", limiter="runplaatsen_chat") == voor + 1


# ── Labels: begrensd, zonder persoon of tekst ────────────────────────────────


def test_geen_label_draagt_een_gebruiker_pseudoniem_of_vraagtekst(client, monkeypatch):
    from core.logging_util import gebruiker_kenmerk
    from core.pseudoniem import pseudoniem
    from persistence import db

    auth = _ingelogd()
    client.get(f"/api/conversations/{urllib.parse.quote(VRAAG, safe='')}", headers=auth)
    client.get("/api/conversations", params={"q": VRAAG}, headers=auth)
    client.get(f"/api/onbekend/{GEBRUIKER}", headers=auth)
    monkeypatch.setattr(db, "deelt_staat", lambda: False)
    limiet = RateLimiter(max_attempts=1, window_seconds=60, naam="feedback")
    limiet.probeer(GEBRUIKER)
    limiet.probeer(GEBRUIKER)

    tekst = client.get("/metrics", headers=_bearer()).text
    verboden = [GEBRUIKER, "anna", "geheimvak", VRAAG, pseudoniem("ratelimit", GEBRUIKER), gebruiker_kenmerk(GEBRUIKER)]
    for woord in verboden:
        if woord and woord != "-":
            assert woord not in tekst, woord

    for familie in text_string_to_metric_families(tekst):
        if not familie.name.startswith("edudata_"):
            continue
        for sample in familie.samples:
            assert set(sample.labels) <= _LABELS, (sample.name, sample.labels)
            if "route" in sample.labels:
                assert sample.labels["route"].startswith("/") or sample.labels["route"] == metrics.GEEN_ROUTE
            # De kwaliteitstellers (#1250): alleen namen en woorden uit vaste lijsten.
            vast = {
                "controle": metrics.controlenamen() | {metrics.OVERIG},
                "uitkomst": set(metrics.CONTROLE_UITKOMSTEN) | {metrics.OVERIG},
                "tool": metrics.toolnamen() | {metrics.OVERIG},
                "reden": set(metrics.TOOL_WEIGERREDENEN) | {metrics.OVERIG},
            }
            for label, toegestaan in vast.items():
                if label in sample.labels:
                    assert sample.labels[label] in toegestaan, (sample.name, sample.labels)


def metrics_route():
    from routes import metrics as route

    return route


# ── Kwaliteitstellers voor de wekelijkse audit (#1250) ──────────────────────


def _antwoordrun(monkeypatch, stappen: list, tool_result: str) -> str:
    """Een vraag door agent.run met een nagebootst model, zoals in test_chat_grounding.py."""
    import importlib

    run_module = importlib.import_module("agent.run")  # `agent.run` is ook een functie in agent/__init__.py

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    async def fake_execute_tool(call, emit, recept_van=None):
        return tool_result, None

    monkeypatch.setattr(loop, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop, "_execute_tool", fake_execute_tool)

    async def emit(event):
        pass

    return asyncio.run(
        run_module.run([{"role": "user", "content": VRAAG}], {}, emit, asyncio.Event(), model="openai/gpt-4o")
    )


def _controle(naam: str, uitkomst: str) -> float:
    return _waarde("edudata_controle_uitkomsten_total", controle=naam, uitkomst=uitkomst)


@pytest.mark.usefixtures("zonder_scopekaart")
def test_controles_herkansing_en_ingehouden_antwoord_tellen_mee(monkeypatch):
    from agent.probleem import INGEHOUDEN
    from agent.stream import StreamResult

    rijen = '{"data_key": "duo:p02:a", "rijen": [{"AANTAL": 5943}]}'
    query = {"id": "q", "name": "query_data", "arguments": '{"data_key": "duo:p02"}'}
    voor = {
        "hard": _controle("ongedekte_getallen", "hard"),
        "ok": _controle("metatekst", "ok"),
        "herkansingen": _waarde("edudata_herkansingen_total"),
        "ingehouden": _waarde("edudata_ingehouden_antwoorden_total"),
    }

    tekst = _antwoordrun(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[query]),
            StreamResult(text="In totaal 6.340 eerstejaars.", tool_calls=[]),
            StreamResult(text="Toch 6.340 eerstejaars.", tool_calls=[]),
        ],
        rijen,
    )

    assert tekst == INGEHOUDEN
    # Vóór en na de herkansing: twee keer hard, en elke andere controle twee keer per uitkomst.
    assert _controle("ongedekte_getallen", "hard") == voor["hard"] + 2
    assert _controle("metatekst", "ok") == voor["ok"] + 2
    assert _waarde("edudata_herkansingen_total") == voor["herkansingen"] + 1
    assert _waarde("edudata_ingehouden_antwoorden_total") == voor["ingehouden"] + 1


def test_elke_controle_van_het_antwoord_staat_in_de_vaste_lijst(caplog):
    """De labels komen uit CONTROLENAMEN; een nieuwe controle zonder plaats daar zou als `overig` tellen."""
    import logging

    from agent.controles import CONTROLENAMEN, antwoordcontrole

    with caplog.at_level(logging.INFO, logger="agent.run"):
        antwoordcontrole(VRAAG, [], [], [], [])("Een antwoord zonder getallen.", [])
    [regel] = [r.getMessage() for r in caplog.records if r.getMessage().startswith("CONTROLES")]
    gelogd = [deel.split("=", 1)[0] for deel in regel.removeprefix("CONTROLES").split("  ") if "=" in deel]
    assert gelogd == list(CONTROLENAMEN)
    assert metrics.controlenamen() == frozenset(CONTROLENAMEN)


def test_een_onbekende_controle_of_uitkomst_telt_als_overig():
    voor_naam = _controle(metrics.OVERIG, "hard")
    voor_uitkomst = _controle("ongedekte_getallen", metrics.OVERIG)
    voor_spatie = _controle("ongedekte_getallen", "niet_gecontroleerd")
    metrics.meet_controles({VRAAG: "hard", "ongedekte_getallen": "iets anders"})
    metrics.meet_controles({"ongedekte_getallen": "niet gecontroleerd"})
    assert _controle(metrics.OVERIG, "hard") == voor_naam + 1
    assert _controle("ongedekte_getallen", metrics.OVERIG) == voor_uitkomst + 1
    assert _controle("ongedekte_getallen", "niet_gecontroleerd") == voor_spatie + 1
    assert _controle(VRAAG, "hard") == 0


def test_de_toolnamen_zijn_alle_tools_van_de_app():
    from tools import LABELS
    from tools.schemas import TOOL_SCHEMAS

    assert {s["function"]["name"] for s in TOOL_SCHEMAS} <= metrics.toolnamen()
    assert metrics.toolnamen() == frozenset(LABELS)
    assert metrics.tool_label("get_maat") == "get_maat"
    assert metrics.tool_label(GEBRUIKER) == metrics.OVERIG
    assert metrics.reden_label("op_slot") == "op_slot"
    assert metrics.reden_label("vrije tekst") == metrics.OVERIG


def _toolweigering(tool: str, reden: str) -> float:
    return _waarde("edudata_tool_weigeringen_total", tool=tool, reden=reden)


def _lus(**kwargs) -> loop._Loop:
    standaard: dict[str, Any] = {
        "messages": [],
        "model": "openai/gpt-4o",
        "tools": [],
        "emit": None,
        "stop_event": None,
        "max_iterations": 3,
        "max_result_chars": 1000,
        "system": [],
        "stream_text": False,
        "on_llm_start": None,
        "on_tool_result": None,
        "tool_limits": {},
        "halt_on": frozenset(),
        "wrap_up": None,
    }
    return loop._Loop(**{**standaard, **kwargs})


def test_een_afgekapt_toolresultaat_telt_als_toolweigering():
    voor = _toolweigering("query_data", "afgekapt")
    assert loop._truncate("x" * 20, 30, tool="query_data") == "x" * 20  # binnen de grens telt niet
    loop._truncate("x" * 20, 10, tool="query_data")
    assert _toolweigering("query_data", "afgekapt") == voor + 1


def test_een_tool_op_slot_telt_eenmaal_als_toolweigering():
    lus = _lus()
    voor = _toolweigering("get_cbs_data", "op_slot")
    for _ in range(3):
        lus._note_error("get_cbs_data", "Fout (bron_fout): de bron faalde")
    assert lus.locked == {"get_cbs_data": "bron_fout"}
    assert _toolweigering("get_cbs_data", "op_slot") == voor + 1


def test_een_tool_over_zijn_limiet_telt_als_toolweigering(monkeypatch):
    async def fake_execute_tool(call, emit, recept_van=None):
        return "resultaat", None

    async def emit(event):
        pass

    monkeypatch.setattr(loop, "_execute_tool", fake_execute_tool)
    lus = _lus(tool_limits={"search_catalog": 1}, emit=emit)
    aanroepen = [
        loop.ToolCall(id=str(i), name="search_catalog", arguments=f'{{"query": "q{i}"}}', args={"query": f"q{i}"})
        for i in range(3)
    ]
    voor = _toolweigering("search_catalog", "limiet")
    asyncio.run(lus._run_tools(aanroepen))
    assert _toolweigering("search_catalog", "limiet") == voor + 2


def test_een_stappenbudget_dat_op_is_telt(monkeypatch):
    from agent.stream import StreamResult
    from tests.test_herkansing_budget import _beurt, _tool

    voor = _waarde("edudata_stappenbudget_op_total")
    stappen = [_tool("a"), _tool("b"), StreamResult(text="Deelantwoord.", tool_calls=[])]
    result, _, _ = _beurt(monkeypatch, stappen, max_iterations=2, wrap_up="Rond af.")
    assert result.wrapped_up
    assert _waarde("edudata_stappenbudget_op_total") == voor + 1
