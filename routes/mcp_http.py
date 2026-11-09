"""/mcp: de catalogustools van mcp_server.py over streamable HTTP, in de app zelf (#706).

SURF AI Chat (EduGenAI) koppelt een extensie via een URL; een stdio-server kan het niet aanroepen. Daarom draait de
MCP-server ook hier, in hetzelfde proces als de chat: één pod, dezelfde ingress, /health en /version blijven werken.
Definities, instructies en uitvoering zijn die van stdio (`mcp_server.maak_server`, `voer_uit`).

Stateless met JSON-antwoorden: elk verzoek krijgt een eigen transport, zonder sessie per client en zonder SSE-stroom.
Dat past bij de catalogustools (geen datastore) en bij één pod. De sessiemanager van de SDK heeft wel een taakgroep
nodig die zo lang leeft als de app; `draai()` hoort daarom in de lifespan van de app (server.create_app).

Alleen POST: een GET-stroom of een DELETE van een sessie heeft stateless geen betekenis (405). Zonder sleutels in
MCP_API_KEYS bestaat /mcp niet: 404, ook voor GET (anders gaf de SPA index.html).
"""

import contextlib
import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

import anyio
from fastapi.responses import JSONResponse
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.types import Receive, Scope, Send

import mcp_server
from core.config import MCP_API_KEYS
from core.foutmeldingen import NIET_GEVONDEN
from core.logging_util import tekst_kenmerk

logger = logging.getLogger(__name__)

PAD = "/mcp"
ALLEEN_POST = "Alleen POST: /mcp is stateless, zonder stroom of sessie."


async def _in_thread(naam: str, argumenten: dict[str, Any] | None) -> tuple[str, bool]:
    """Een toolaanroep in een thread: voer_uit is synchroon (de eerste zoekactie laadt het DUO-register, seconden) en
    de event loop draait ook de chat. Het log noemt tool en uitkomst, de argumenten alleen als kenmerk (#475)."""
    begin = time.monotonic()
    tekst, fout = await anyio.to_thread.run_sync(mcp_server.voer_uit, naam, argumenten)
    logger.info(
        "MCP TOOL %s %s fout=%s duur=%.2fs",
        naam,
        tekst_kenmerk(json.dumps(argumenten or {}, ensure_ascii=False, sort_keys=True), "args_"),
        fout,
        time.monotonic() - begin,
    )
    return tekst, fout


class McpEindpunt:
    """De ASGI-app achter /mcp. Eén per app: server.create_app maakt hem en zet `draai()` in de lifespan."""

    def __init__(self, *, sleutels: tuple[str, ...]) -> None:
        self._sleutels = sleutels
        self._server = mcp_server.maak_server(_in_thread)
        self._manager: StreamableHTTPSessionManager | None = None

    @classmethod
    def uit_config(cls) -> "McpEindpunt":
        return cls(sleutels=MCP_API_KEYS)

    @contextlib.asynccontextmanager
    async def draai(self) -> AsyncGenerator[None]:
        """De sessiemanager voor de duur van de app; zonder sleutels geen manager en één logregel waarom."""
        if not self._sleutels:
            logger.info("MCP uit: MCP_API_KEYS is leeg, /mcp geeft 404")
            yield
            return
        # Elke start een nieuwe manager: die van de SDK draait maar één keer, en een app kan vaker starten (tests).
        self._manager = StreamableHTTPSessionManager(app=self._server, stateless=True, json_response=True)
        try:
            async with self._manager.run():
                logger.info("MCP aan op %s: streamable HTTP, stateless", PAD)
                yield
        finally:
            self._manager = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._manager is None:
            await JSONResponse({"detail": NIET_GEVONDEN}, status_code=404)(scope, receive, send)
            return
        if scope["method"] != "POST":
            # Stateless is er geen GET-stroom (de SDK hield hem open zonder ooit iets te sturen) en geen sessie om met
            # DELETE te sluiten. 405 zegt de client dat de server geen stroom aanbiedt (MCP-spec, streamable HTTP).
            await JSONResponse({"detail": ALLEEN_POST}, status_code=405, headers={"Allow": "POST"})(
                scope, receive, send
            )
            return
        await self._manager.handle_request(scope, receive, send)
