"""/mcp: de catalogustools van mcp_server.py over streamable HTTP, in de app zelf (#706).

SURF AI Chat (EduGenAI) koppelt een extensie via een URL; een stdio-server kan het niet aanroepen. Daarom draait de
MCP-server ook hier, in hetzelfde proces als de chat: één pod, dezelfde ingress, /health en /version blijven werken.
Definities, instructies en uitvoering zijn die van stdio (`mcp_server.maak_server`, `voer_uit`).

Stateless met JSON-antwoorden: elk verzoek krijgt een eigen transport, zonder sessie per client en zonder SSE-stroom.
Dat past bij de catalogustools (geen datastore) en bij één pod. De sessiemanager van de SDK heeft wel een taakgroep
nodig die zo lang leeft als de app; `draai()` hoort daarom in de lifespan van de app (server.create_app).

Alleen POST: een GET-stroom of een DELETE van een sessie heeft stateless geen betekenis (405). Zonder sleutels in
MCP_API_KEYS bestaat /mcp niet: 404, ook voor GET (anders gaf de SPA index.html).

Elk verzoek draagt `Authorization: Bearer <sleutel>` met een sleutel uit MCP_API_KEYS (#939), anders 401. Meerdere
sleutels tegelijk: roteren zonder onderbreking, en een eigen sleutel per consument. Het log noemt nooit de sleutel,
alleen een sleutel-ID (`tekst_kenmerk`, met LOG_HASH_SECRET een HMAC), zodat te zien is wie een aanroep deed.

Limieten (#940), los van die van de chat, zodat één consument de chat op de pod niet traag maakt: een rate limit per
sleutel en per IP (429 met Retry-After), een bovengrens op gelijktijdige verzoeken (snel een 503, geen lange wachtrij),
een tijdslimiet per toolaanroep en een begrensd resultaat.
"""

import contextlib
import contextvars
import hashlib
import hmac
import json
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import anyio
from fastapi.responses import JSONResponse
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.datastructures import Headers
from starlette.types import Receive, Scope, Send

import mcp_server
from core.config import (
    MCP_API_KEYS,
    MCP_MAX_GELIJKTIJDIG,
    MCP_RATE_LIMIT,
    MCP_RATE_LIMIT_IP,
    MCP_RATE_WINDOW_S,
    MCP_TOOL_TIMEOUT_S,
    MCP_WACHT_S,
    TOOL_RESULT_MAX_CHARS,
)
from core.foutmeldingen import NIET_GEVONDEN
from core.gelijktijdig import DRUK, Druk, Runplaatsen
from core.logging_util import tekst_kenmerk
from core.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

PAD = "/mcp"
ALLEEN_POST = "Alleen POST: /mcp is stateless, zonder stroom of sessie."
GEEN_SLEUTEL = "Geen geldige API-sleutel. Stuur Authorization: Bearer <sleutel>."
TE_VEEL = "Te veel verzoeken op /mcp. Probeer het over {wacht} seconden opnieuw."
# Na een 503: een plaats komt meestal binnen een toolaanroep vrij.
RETRY_DRUK_S = 5
# Resultaatgrootte zoals in de chat (#395); hier als geldige envelope (mcp_server.begrens).
MCP_MAX_TEKENS = TOOL_RESULT_MAX_CHARS

# Het sleutel-ID van het lopende verzoek, voor de logregel van de toolaanroep: de SDK draait die in een eigen taak,
# die de context van het verzoek erft.
_sleutel_id: contextvars.ContextVar[str] = contextvars.ContextVar("mcp_sleutel_id", default="-")


class Sleutels:
    """De geldige API-sleutels (#939). Elke vergelijking constant-time, op een SHA-256 van gelijke lengte, en tegen
    alle sleutels zonder vroeg te stoppen: de duur verraadt niet welke sleutel bijna klopte, noch hoe lang hij is."""

    def __init__(self, sleutels: tuple[str, ...]) -> None:
        self._sleutels = [(_digest(s), tekst_kenmerk(s, "sleutel_")) for s in sleutels]

    def __bool__(self) -> bool:
        return bool(self._sleutels)

    def herken(self, autorisatie: str | None) -> str | None:
        """Het sleutel-ID bij `Bearer <geldige sleutel>`, anders None."""
        schema, _, aangeboden = (autorisatie or "").partition(" ")
        aangeboden = aangeboden.strip()
        if schema.lower() != "bearer" or not aangeboden:
            return None
        digest = _digest(aangeboden)
        gevonden = None
        for kandidaat, sleutel_id in self._sleutels:
            if hmac.compare_digest(digest, kandidaat):
                gevonden = sleutel_id
        return gevonden


def _digest(sleutel: str) -> bytes:
    return hashlib.sha256(sleutel.encode()).digest()


@dataclass(frozen=True)
class Grenzen:
    """De limieten van /mcp (#940), los van die van de chat; core/config.py zegt waarom deze standaarden."""

    rate_limit: int
    rate_limit_ip: int
    venster_s: int
    max_gelijktijdig: int
    wacht_s: float
    tijdslimiet_s: float
    max_tekens: int


async def _weiger(
    scope: Scope, receive: Receive, send: Send, status: int, detail: str, koppen: dict[str, str] | None = None
) -> None:
    await JSONResponse({"detail": detail}, status_code=status, headers=koppen)(scope, receive, send)


class McpEindpunt:
    """De ASGI-app achter /mcp. Eén per app: server.create_app maakt hem en zet `draai()` in de lifespan.

    Volgorde per verzoek: aan (404), rate limit per IP (429, telt ook foute sleutels), sleutel (401), alleen POST
    (405), rate limit per sleutel (429), een vrije plaats (503); dan de transport van de SDK.
    """

    def __init__(self, *, sleutels: tuple[str, ...], grenzen: Grenzen) -> None:
        self._sleutels = Sleutels(sleutels)
        self._grenzen = grenzen
        self._server = mcp_server.maak_server(self._voer_uit)
        self._per_sleutel = RateLimiter(max_attempts=grenzen.rate_limit, window_seconds=grenzen.venster_s)
        self._per_ip = RateLimiter(max_attempts=grenzen.rate_limit_ip, window_seconds=grenzen.venster_s)
        self._manager: StreamableHTTPSessionManager | None = None
        # Plaatsen voor verzoeken, en threads voor toolaanroepen: een aanroep die over zijn tijd gaat, loopt in zijn
        # thread door (een thread is niet te stoppen) en houdt dan zijn thread vast, niet die van de rest van de app.
        self._plaatsen: Runplaatsen | None = None
        self._threads: anyio.CapacityLimiter | None = None

    @classmethod
    def uit_config(cls) -> "McpEindpunt":
        grenzen = Grenzen(
            rate_limit=MCP_RATE_LIMIT,
            rate_limit_ip=MCP_RATE_LIMIT_IP,
            venster_s=MCP_RATE_WINDOW_S,
            max_gelijktijdig=MCP_MAX_GELIJKTIJDIG,
            wacht_s=MCP_WACHT_S,
            tijdslimiet_s=MCP_TOOL_TIMEOUT_S,
            max_tekens=MCP_MAX_TEKENS,
        )
        return cls(sleutels=MCP_API_KEYS, grenzen=grenzen)

    @contextlib.asynccontextmanager
    async def draai(self) -> AsyncGenerator[None]:
        """De sessiemanager voor de duur van de app; zonder sleutels geen manager en één logregel waarom."""
        if not self._sleutels:
            logger.info("MCP uit: MCP_API_KEYS is leeg, /mcp geeft 404")
            yield
            return
        # Elke start een nieuwe manager: die van de SDK draait maar één keer, en een app kan vaker starten (tests).
        # Plaatsen en threads ook: een semafoor hoort bij de event loop waarin hij wacht.
        self._manager = StreamableHTTPSessionManager(app=self._server, stateless=True, json_response=True)
        self._plaatsen = Runplaatsen(max_tegelijk=self._grenzen.max_gelijktijdig, wacht_s=self._grenzen.wacht_s)
        self._threads = anyio.CapacityLimiter(self._grenzen.max_gelijktijdig)
        try:
            async with self._manager.run():
                logger.info("MCP aan op %s: streamable HTTP, stateless, %s", PAD, self._grenzen)
                yield
        finally:
            self._manager = self._plaatsen = self._threads = None

    async def _voer_uit(self, naam: str, argumenten: dict[str, Any] | None) -> tuple[str, bool]:
        """Een toolaanroep in een thread: voer_uit is synchroon (de eerste zoekactie laadt het DUO-register, seconden)
        en de event loop draait ook de chat. Met een tijdslimiet en een begrensd resultaat (#940). Het log noemt tool,
        uitkomst en sleutel-ID, de argumenten alleen als kenmerk (#475)."""
        begin = time.monotonic()
        tijdslimiet = self._grenzen.tijdslimiet_s
        try:
            with anyio.fail_after(tijdslimiet):
                tekst, fout = await anyio.to_thread.run_sync(
                    mcp_server.voer_uit, naam, argumenten, abandon_on_cancel=True, limiter=self._threads
                )
        except TimeoutError:
            tekst, fout = f"{naam} duurde langer dan {tijdslimiet:g} s en is gestopt. Probeer het zo opnieuw.", True
        if not fout:
            tekst = mcp_server.begrens(tekst, self._grenzen.max_tekens)
        logger.info(
            "MCP TOOL %s %s fout=%s duur=%.2fs tekens=%d %s",
            naam,
            tekst_kenmerk(json.dumps(argumenten or {}, ensure_ascii=False, sort_keys=True), "args_"),
            fout,
            time.monotonic() - begin,
            len(tekst),
            _sleutel_id.get(),
        )
        return tekst, fout

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        manager, plaatsen = self._manager, self._plaatsen
        if manager is None or plaatsen is None:
            await _weiger(scope, receive, send, 404, NIET_GEVONDEN)
            return
        ip = (scope.get("client") or ("onbekend",))[0]
        if not self._per_ip.is_allowed(ip):
            logger.warning("MCP 429: rate limit per IP")
            await self._te_veel(scope, receive, send, self._per_ip, ip)
            return
        sleutel_id = self._sleutels.herken(Headers(scope=scope).get("authorization"))
        if sleutel_id is None:
            # Zonder de aangeboden waarde: ook een foute sleutel kan een echte zijn met een tikfout.
            logger.warning("MCP 401: geen of ongeldige sleutel")
            await _weiger(scope, receive, send, 401, GEEN_SLEUTEL, {"WWW-Authenticate": "Bearer"})
            return
        if scope["method"] != "POST":
            # Stateless is er geen GET-stroom (de SDK hield hem open zonder ooit iets te sturen) en geen sessie om met
            # DELETE te sluiten. 405 zegt de client dat de server geen stroom aanbiedt (MCP-spec, streamable HTTP).
            await _weiger(scope, receive, send, 405, ALLEEN_POST, {"Allow": "POST"})
            return
        if not self._per_sleutel.is_allowed(sleutel_id):
            logger.warning("MCP 429: rate limit per sleutel %s", sleutel_id)
            await self._te_veel(scope, receive, send, self._per_sleutel, sleutel_id)
            return
        _sleutel_id.set(sleutel_id)
        try:
            async with plaatsen.plaats():
                await manager.handle_request(scope, receive, send)
        except Druk:
            logger.warning("MCP 503: %d verzoeken tegelijk", self._grenzen.max_gelijktijdig)
            await _weiger(scope, receive, send, 503, DRUK, {"Retry-After": str(RETRY_DRUK_S)})

    async def _te_veel(self, scope: Scope, receive: Receive, send: Send, limiter: RateLimiter, sleutel: str) -> None:
        wacht = limiter.retry_after(sleutel) or self._grenzen.venster_s
        await _weiger(scope, receive, send, 429, TE_VEEL.format(wacht=wacht), {"Retry-After": str(wacht)})
