"""Metrics voor de productiemonitoring (#678): `GET /metrics` in het tekstformaat van Prometheus (routes/metrics.py).

De standaardregistry van `prometheus_client`, zonder multiprocess-modus: een pod draait één uvicorn-proces (Dockerfile),
dus elke waarde hier is die van één pod. De procesmetrics van de bibliotheek (`process_*`, `python_gc_*`) komen mee.

Labels zijn begrensd: een routesjabloon (`/api/conversations/{conv_id}`, nooit het pad zelf), een vaste methode, de
statuscode, een modelnaam uit het aanbod (`core.config.toegestaan_model`) en vaste woorden. Nooit een gebruikersnaam,
pseudoniem, vraagtekst of sleutel-ID: dan groeit het aantal reeksen per gebruiker en staat er een persoon in de metrics.

Elke meetfunctie is goedkoop en gooit nooit: een fout in het meten mag geen verzoek, run of limiet breken.

De tellers van wat er tegelijk loopt (core/gelijktijdig.py) staan er als gauges per pod: ze worden pas bij een scrape
gelezen (`_Bezetting`), dus het tellen zelf verandert niet.
"""

import contextlib
import logging
import time
from collections.abc import Iterable
from typing import Any, Protocol

from prometheus_client import REGISTRY, Counter, Histogram, disable_created_metrics
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

PREFIX = "edudata"

# Geen `_created`-reeks naast elke teller: die verdubbelt de uitvoer en de tijdreeksen, en `rate()` heeft haar niet nodig.
disable_created_metrics()

# Methoden die een label krijgen; een andere (een client kan elke naam sturen) telt als ANDERS.
_METHODEN = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})
# Een verzoek dat op geen route paste (een 404 van de router zelf, of een fout ervoor): één label, niet het pad.
GEEN_ROUTE = "<geen route>"

# Seconden: een API-aanroep in honderdsten, een koude dashboardlading tot 90 s (DASHBOARD_TIMEOUT_S).
_HTTP_GRENZEN = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120)
# Een modelaanroep: de eerste chunk in seconden, het geheel tot minuten (RUN_TIMEOUT_S, GENEREER_TIMEOUT_S).
_EERSTE_CHUNK_GRENZEN = (0.25, 0.5, 1, 2, 3, 5, 10, 20, 30, 60, 120)
_MODEL_GRENZEN = (0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300, 600)

HTTP_VERZOEKEN = Counter(
    f"{PREFIX}_http_requests",
    "HTTP-verzoeken per methode, routesjabloon en statuscode.",
    ("method", "route", "status"),
)
HTTP_DUUR = Histogram(
    f"{PREFIX}_http_request_duration_seconds",
    "Duur van een HTTP-verzoek tot het antwoord klaar is, per methode en routesjabloon.",
    ("method", "route"),
    buckets=_HTTP_GRENZEN,
)
HTTP_5XX = Counter(
    f"{PREFIX}_http_server_errors",
    "HTTP-verzoeken met een 5xx-antwoord, per methode en routesjabloon.",
    ("method", "route"),
)

MODEL_AANROEPEN = Counter(
    f"{PREFIX}_model_calls",
    "Modelaanroepen per model en uitkomst (ok, gestopt, geannuleerd, afgebroken_runlimiet, fout), zoals MODELAANROEP.",
    ("model", "outcome"),
)
MODEL_FOUTEN = Counter(
    f"{PREFIX}_model_call_errors",
    "Mislukte modelaanroepen per model: een fout van de provider of de harde grens van de run (afgebroken_runlimiet).",
    ("model",),
)
MODEL_DUUR = Histogram(
    f"{PREFIX}_model_call_duration_seconds",
    "Duur van een modelaanroep tot het einde van de stroom, de stop of de fout.",
    ("model",),
    buckets=_MODEL_GRENZEN,
)
MODEL_EERSTE_CHUNK = Histogram(
    f"{PREFIX}_model_first_chunk_seconds",
    "Seconden tot de eerste chunk van het model (time to first token), per aanroep die er een kreeg.",
    ("model",),
    buckets=_EERSTE_CHUNK_GRENZEN,
)
MODEL_TOKENS = Counter(
    f"{PREFIX}_model_tokens",
    "Tokens per model en richting (input, output), zoals de TOKENS-regel per run.",
    ("model", "direction"),
)

SANDBOX_RUNS = Counter(
    f"{PREFIX}_sandbox_runs",
    "Scripts van run_analysis per uitkomst: ok, fout, timeout, gestopt, bezet (geen plaats vrij).",
    ("outcome",),
)
SANDBOX_TIMEOUTS = Counter(
    f"{PREFIX}_sandbox_timeouts",
    "Scripts van run_analysis die na de tijdslimiet zijn afgebroken.",
)

LIMIET_WEIGERINGEN = Counter(
    f"{PREFIX}_limiter_refusals",
    "Geweigerde verzoeken per limiet: een rate limit (429 of melding) of een volle plaats (Druk, MCP 503, verbindingen).",
    ("limiter",),
)
LIMIET_TERUGVAL = Counter(
    f"{PREFIX}_limiter_db_fallback",
    "Pogingen die een limiet in het geheugen van de pod telde omdat de database niet bereikbaar was (fail-open).",
    ("limiter",),
)

_SANDBOX_UITKOMSTEN = frozenset({"ok", "fout", "timeout", "gestopt", "bezet"})
_MODEL_UITKOMSTEN = frozenset({"ok", "gestopt", "geannuleerd", "afgebroken_runlimiet"})
# Een limiet zonder naam (alleen in tests) of een onverwachte naam krijgt geen eigen reeks.
_ONBENOEMD = "onbenoemd"


def _veilig(functie):
    """Meten mag nooit de aanroeper breken: een fout komt eenmaal per soort op DEBUG in het log."""

    def binnen(*args: Any, **kwargs: Any) -> None:
        try:
            functie(*args, **kwargs)
        except Exception:
            logger.debug("Meten mislukt in %s", functie.__name__, exc_info=True)

    binnen.__name__ = functie.__name__
    binnen.__doc__ = functie.__doc__
    return binnen


def methode_label(methode: str) -> str:
    return methode if methode in _METHODEN else "ANDERS"


def route_label(scope: Scope) -> str:
    """Het sjabloon van de route die het verzoek afhandelde (Starlette zet haar in de scope), nooit het pad zelf."""
    route = scope.get("route")
    pad = getattr(route, "path", None)
    return pad if isinstance(pad, str) and pad else GEEN_ROUTE


@_veilig
def meet_verzoek(methode: str, route: str, status: int, duur_s: float) -> None:
    methode = methode_label(methode)
    HTTP_VERZOEKEN.labels(methode, route, str(status)).inc()
    HTTP_DUUR.labels(methode, route).observe(duur_s)
    if 500 <= status <= 599:
        HTTP_5XX.labels(methode, route).inc()


class HttpMeting:
    """ASGI-middleware die elk HTTP-verzoek telt en meet, met het routesjabloon als label.

    Een gewone ASGI-middleware, geen BaseHTTPMiddleware: een gestreamd antwoord (de export van mijn gegevens) loopt
    gewoon door. De statuscode komt uit `http.response.start`; een verzoek dat zonder antwoord met een fout eindigt,
    telt als 500 (de server stuurt dan zelf een 500).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        begin = time.perf_counter()
        status = 500

        async def send_met_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_met_status)
        finally:
            meet_verzoek(scope.get("method", ""), route_label(scope), status, time.perf_counter() - begin)


@_veilig
def meet_modelaanroep(model: str, uitkomst: str, duur_s: float, eerste_chunk_s: float | None) -> None:
    """Eén modelaanroep, met de uitkomst van MODELAANROEP (agent/loop.py); een fouttype telt als `fout`."""
    soort = uitkomst if uitkomst in _MODEL_UITKOMSTEN else "fout"
    MODEL_AANROEPEN.labels(model, soort).inc()
    if soort in ("fout", "afgebroken_runlimiet"):
        MODEL_FOUTEN.labels(model).inc()
    MODEL_DUUR.labels(model).observe(duur_s)
    if eerste_chunk_s is not None:
        MODEL_EERSTE_CHUNK.labels(model).observe(eerste_chunk_s)


@_veilig
def meet_tokens(model: str, invoer: int, uitvoer: int) -> None:
    """De tokens van een run, zoals de TOKENS-regel (agent/loop.py)."""
    if invoer > 0:
        MODEL_TOKENS.labels(model, "input").inc(invoer)
    if uitvoer > 0:
        MODEL_TOKENS.labels(model, "output").inc(uitvoer)


@_veilig
def meet_sandbox(uitkomst: str) -> None:
    soort = uitkomst if uitkomst in _SANDBOX_UITKOMSTEN else "fout"
    SANDBOX_RUNS.labels(soort).inc()
    if soort == "timeout":
        SANDBOX_TIMEOUTS.inc()


@_veilig
def meet_weigering(limiet: str | None) -> None:
    """Een geweigerd verzoek: de naam van een RateLimiter, of een vaste naam voor een volle plaats."""
    LIMIET_WEIGERINGEN.labels(limiet or _ONBENOEMD).inc()


@_veilig
def meet_terugval(limiet: str | None) -> None:
    """Een limiet telde in het geheugen omdat de database niet bereikbaar was (core/rate_limit.py)."""
    LIMIET_TERUGVAL.labels(limiet or _ONBENOEMD).inc()


# ── Wat er tegelijk loopt, per pod (core/gelijktijdig.py) ────────────────────


class _Bezet(Protocol):
    @property
    def bezet(self) -> int: ...

    @property
    def max_tegelijk(self) -> int: ...


class _Open(Protocol):
    @property
    def aantal(self) -> int: ...

    @property
    def meeste_per_sleutel(self) -> int: ...

    @property
    def max_per_sleutel(self) -> int: ...

    @property
    def max_totaal(self) -> int: ...


_plaatsen: dict[str, _Bezet] = {}
_verbindingen: list[_Open] = []


def volg_plaatsen(soort: str, plaatsen: _Bezet | None) -> None:
    """Toon de bezetting van deze plaatsen als `runs_running{pool=soort}` (of `sandbox_running`); None haalt ze weg."""
    if plaatsen is None:
        _plaatsen.pop(soort, None)
    else:
        _plaatsen[soort] = plaatsen


def volg_verbindingen(verbindingen: _Open) -> None:
    """Toon de open chatverbindingen van deze pod; een tweede aanroep (een herladen module) vervangt de eerste."""
    _verbindingen[:] = [verbindingen]


class _Bezetting(Collector):
    """Leest de tellers van core/gelijktijdig.py bij elke scrape; zonder labels per gebruiker."""

    def collect(self) -> Iterable[GaugeMetricFamily]:
        open_ = GaugeMetricFamily(f"{PREFIX}_websockets_open", "Open chatverbindingen (WebSockets) op deze pod.")
        per_gebruiker = GaugeMetricFamily(
            f"{PREFIX}_websockets_per_user_max",
            "Het grootste aantal open chatverbindingen van één gebruiker op deze pod (zonder te zeggen wie).",
        )
        runs = GaugeMetricFamily(
            f"{PREFIX}_runs_running",
            "Lopende runs per wachtrij op deze pod: chat (vraag, rapport), dashboard, mcp.",
            labels=("pool",),
        )
        sandbox = GaugeMetricFamily(f"{PREFIX}_sandbox_running", "Lopende sandboxprocessen van run_analysis.")
        grenzen = GaugeMetricFamily(
            f"{PREFIX}_concurrency_limit",
            "De grens per teller van wat er tegelijk mag op deze pod (core/gelijktijdig.py).",
            labels=("counter",),
        )
        if not _verbindingen:
            open_.add_metric((), 0)
            per_gebruiker.add_metric((), 0)
        if "sandbox" not in _plaatsen:
            sandbox.add_metric((), 0)
        for verbindingen in _verbindingen[:1]:
            with contextlib.suppress(Exception):
                open_.add_metric((), verbindingen.aantal)
                per_gebruiker.add_metric((), verbindingen.meeste_per_sleutel)
                grenzen.add_metric(("websockets_total",), verbindingen.max_totaal)
                grenzen.add_metric(("websockets_per_user",), verbindingen.max_per_sleutel)
        for soort, plaatsen in sorted(_plaatsen.items()):
            with contextlib.suppress(Exception):
                if soort == "sandbox":
                    sandbox.add_metric((), plaatsen.bezet)
                else:
                    runs.add_metric((soort,), plaatsen.bezet)
                grenzen.add_metric((soort,), plaatsen.max_tegelijk)
        yield from (open_, per_gebruiker, runs, sandbox, grenzen)


REGISTRY.register(_Bezetting())
