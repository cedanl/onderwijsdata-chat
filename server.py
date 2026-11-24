import asyncio
import contextlib
import logging
import sys
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.routing import Route

load_dotenv()

# JSON-logs op SDP, tekst lokaal (Config.json_logs, #676)
from config import Config, ConfigError
from core import bronstatus, config, dashboard_opwarmen, foutmeldingen, openapi_schema
from core.appversie import app_versie
from core.catalogusversie import arbeidsmarktversie, catalogusdigest, catalogusversie
from core.config import MAX_REQUEST_BYTES
from core.logging_util import foutkenmerk
from core.pakketherkomst import korte_commit
from core.verzoeklimiet import Verzoeklimiet
from frontend_static import mount_frontend
from logging_config import setup_logging

setup_logging(level=Config.log_level(), json_format=Config.json_logs())
logger = logging.getLogger(__name__)

# Validate configuration early
try:
    Config.validate()
except ConfigError as e:
    # Bewust leesbaar: een ConfigError bevat alleen tekst uit config.py (de foutregels van Config.validate, met de
    # configwaarde erbij), geen gebruikerstekst; zonder die tekst is een verkeerde configuratie niet te vinden.
    logger.error("Configuration validation failed: %s", e)
    sys.exit(1)

import health
from auth.oidc import is_oidc_configured
from persistence import db as persistence_db
from routes import (
    auth_router,
    bronstatus_router,
    chat_router,
    config_router,
    data_export_router,
    feedback_router,
    instellingen_router,
    mijn_gegevens_router,
    persistence_router,
    rapport_docx_router,
)
from routes.mcp_http import PAD as MCP_PAD
from routes.mcp_http import McpEindpunt, mcp_aan

# Initialize database
try:
    persistence_db.init_db()
    logger.info("Database initialized successfully")
except Exception as e:
    # Een driverfout kan host en databasenaam citeren: op ERROR alleen een veilige oorzaak (als er een is) met type en
    # kenmerk, de tekst op DEBUG (#817, #1155).
    oorzaak = persistence_db.startfout_oorzaak(e)
    logger.error("Failed to initialize database: %s", f"{oorzaak} [{foutkenmerk(e)}]" if oorzaak else foutkenmerk(e))
    logger.debug("Failed to initialize database", exc_info=True)
    sys.exit(1)


def connect_src(server_url: str | None) -> str:
    """Verbindingen alleen naar de eigen server (#506): de chat-WebSocket gaat naar location.host.

    'self' dekt ws(s) van dezelfde origin in CSP 3, maar oudere Safari-versies laten het niet op
    wss: slaan; daarom staat de origin uit SERVER_URL er expliciet bij. Zonder SERVER_URL (lokaal) 'self'.
    """
    delen = urlsplit(server_url or "")
    if delen.scheme not in ("http", "https") or not delen.netloc:
        return "'self'"
    return f"'self' {'wss' if delen.scheme == 'https' else 'ws'}://{delen.netloc}"


_CONNECT_SRC = connect_src(Config.SERVER_URL)

# Browserfuncties die de app niet gebruikt, ook niet voor een ingesloten frame of een geïnjecteerd script (#636).
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


def resource_policy(pad: str) -> str:
    """Cross-Origin-Resource-Policy (#690): andere origins mogen geen antwoord van de app insluiten.

    Behalve /assets: een rapport draait in een frame met alleen allow-scripts, dus met een eigen, opake origin, en
    laadt Plotly van /assets (plotlyBron.js). Met same-origin daar bleef elk rapport leeg. Die bestanden zijn de
    openbare, gehashte build; ze bevatten niets van een gebruiker.
    """
    return "cross-origin" if pad.startswith("/assets/") else "same-origin"


async def security_headers(request, call_next):
    try:
        response = await call_next(request)
    except Exception as exc:
        # Hier en niet in een exception handler: die draait buiten deze middleware, zonder de headers hieronder (#1154).
        response = foutmeldingen.onverwachte_fout(request, exc)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = PERMISSIONS_POLICY
    # Geen window-referentie van of naar een andere origin; een bron opent via noopener (rapportSandbox.js, #690).
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = resource_policy(request.url.path)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        # Geen derde partij: Plotly voor rapporten en dashboards komt van de eigen server (#486).
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        # Maplibre (de kaart) start zijn worker vanaf een blob:-URL; zonder worker-src valt dat terug op
        # script-src en blijft de kaart leeg (#632). Alleen hier blob:, niet in script-src.
        "worker-src 'self' blob:; "
        f"connect-src {_CONNECT_SRC}; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        # Een geïnjecteerde <base> of <form> stuurt geen relatieve URL of formulier naar een andere host (#682).
        "base-uri 'self'; "
        "form-action 'self';"
    )
    # Geen API-antwoord in de browsercache of een tussenliggende proxy: ze bevatten gesprekken en werkboeken (#682).
    # Een route die zelf een Cache-Control zet, houdt die.
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


# ─── Health checks ───────────────────────────────────────────────────────────

# De eigen routes van de server; create_app hangt ze aan elke app.
_routes = APIRouter()


@_routes.get("/health", tags=["health"])
async def health_endpoint() -> dict:
    """Liveness probe: application is running."""
    return await health.health_check()


@_routes.get("/ready", tags=["health"])
async def ready_endpoint() -> JSONResponse:
    """Readiness probe: application is ready to serve traffic (503 if a check fails, #482)."""
    result, status_code = await health.readiness_check()
    return JSONResponse(content=result, status_code=status_code)


@_routes.get("/version", tags=["info"])
@_routes.get("/api/version", tags=["info"])  # zonder deze route gaf de SPA-fallback HTML terug (#405)
async def version() -> dict:
    """Release uit het chart (APP_VERSION), anders het ontwikkellabel `<pyproject>+dev[.<commit>]` (#1105); de commit waaruit het image is gebouwd (#231), de catalogus (#361)
    met de digest uit het manifest (#1029) en de dataversie van UWV en ROA (CH-46)."""

    return {
        "version": await asyncio.to_thread(app_versie, Config.APP_VERSION),
        # GIT_COMMIT is volledig (de installatieregel van een snippet heeft dat nodig, #888); hier de korte vorm.
        "commit": korte_commit(Config.GIT_COMMIT) or "onbekend",
        # Meegebouwde catalogusrevisies, niet de actuele GitHub-HEAD (#361); per pakket de commit waaruit het komt (#888).
        "catalogus": catalogusversie(Config.GIT_COMMIT),
        # De geladen catalogus met bronvlaggen, gelijk aan `catalogus` in het manifest van een antwoord (#1029).
        # De eerste aanroep laadt de catalogus, dus buiten de event loop.
        "catalogus_digest": await asyncio.to_thread(catalogusdigest),
        # Periode uit de statische riodata-records, zonder download (CH-46).
        "arbeidsmarkt": arbeidsmarktversie(),
        # Of /mcp aan staat (MCP_API_KEYS gezet), zodat een deploy dat zonder sleutel te controleren is (#941, L-07).
        "mcp": mcp_aan(),
    }


@_routes.get("/info", tags=["info"])
async def info() -> dict:
    """Naam en of OIDC aan staat. Databasetype en omgevingslabel stonden hier ook,
    maar het eindpunt is zonder token bereikbaar en die details helpen vooral een
    aanvaller (#518)."""
    return {
        "name": "Onderwijsdata Chat",
        "oidc_enabled": is_oidc_configured(),
    }


# ─── Startup and Shutdown ────────────────────────────────────────────────────


async def on_startup() -> None:
    """Meld de start in het log, met een waarschuwing bij LOG_LEVEL=DEBUG."""
    if Config.LOG_LEVEL == "DEBUG":
        # Op DEBUG staat vraag- en antwoordtekst in het log (#475), en dus eventuele
        # persoonsgegevens in de logaggregatie. Niet stil laten gebeuren (#516).
        logger.warning("LOG_LEVEL=DEBUG: vraag- en antwoordtekst komt in het log; niet gebruiken met echte gebruikers")
    # In de berichttekst: de JSONFormatter neemt geen extra-velden over (#816).
    logger.info(
        "Application startup completed: oidc_enabled=%s database=%s",
        is_oidc_configured(),
        "PostgreSQL" if Config.POSTGRES_URI else "SQLite",
    )


async def on_shutdown() -> None:
    """Graceful shutdown: close connections and cleanup."""
    logger.info("Application shutdown initiated")
    try:
        persistence_db.close()
    except Exception as e:
        logger.warning("Error during shutdown cleanup: %s", foutkenmerk(e))
        logger.debug("Error during shutdown cleanup", exc_info=True)
    logger.info("Application shutdown completed")


def levensloop(mcp: McpEindpunt) -> Callable[[FastAPI], contextlib.AbstractAsyncContextManager[None]]:
    """Start en stop van de app, met daartussen de sessiemanager van /mcp (#706): die heeft een taakgroep nodig die zo
    lang leeft als de app. Een gemounte app krijgt geen eigen lifespan, dus de app start hem zelf. Na de start warmen
    de dashboards op de achtergrond op (#1166); de start wacht daar niet op."""

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        await on_startup()
        try:
            async with (
                bronstatus.bewaking(config.BRONSTATUS_INTERVAL_S),
                dashboard_opwarmen.opwarming(config.DASHBOARDS_ENABLED and config.DASHBOARD_WARMUP),
                mcp.draai(),
            ):
                yield
        finally:
            await on_shutdown()

    return lifespan


# ─── App ─────────────────────────────────────────────────────────────────────

_ROUTERS = (
    config_router,
    bronstatus_router,
    feedback_router,
    auth_router,
    persistence_router,
    rapport_docx_router,
    instellingen_router,
    data_export_router,
    mijn_gegevens_router,
    chat_router,
)


def create_app(*, api_docs: bool | None = None, frontend_dist: Path | None = None) -> FastAPI:
    """De app met middleware, routes en event handlers; zonder frontend_dist geen SPA.

    api_docs=None volgt Config.api_docs(). Tests bouwen zo een app zonder documentatie zonder de module te herladen.
    """
    # API-documentatie niet op playground en productie (#636, #676): het schema somt elke route op voor wie niet is
    # ingelogd, en Swagger UI en ReDoc laden hun scripts van cdn.jsdelivr.net.
    docs = Config.api_docs() if api_docs is None else api_docs
    mcp = McpEindpunt.uit_config()
    app = FastAPI(
        title="Onderwijsdata Chat",
        version=app_versie(Config.APP_VERSION),
        docs_url="/api/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/api/openapi.json" if docs else None,
        lifespan=levensloop(mcp),
    )
    # Validatiefouten en onbekende routes in het Nederlands, zonder de invoer te herhalen (#637).
    foutmeldingen.registreer(app)
    openapi_schema.registreer(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=Config.get_parsed_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(Verzoeklimiet, max_bytes=MAX_REQUEST_BYTES)
    # Bundel, catalogus en API-antwoorden gecomprimeerd: de ingress doet het niet (#110).
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.middleware("http")(security_headers)
    app.include_router(_routes)
    for router in _ROUTERS:
        app.include_router(router)
    # Vóór de SPA: zonder sleutels geeft ook GET /mcp een JSON-404, geen index.html. Een ASGI-app als eindpunt: elke
    # methode gaat naar de transport van de SDK, die zelf POST, GET en DELETE afhandelt.
    app.router.routes.append(Route(MCP_PAD, endpoint=mcp, include_in_schema=False))
    if frontend_dist is not None:
        mount_frontend(app, frontend_dist)
    return app


# ─── Serve React frontend ───────────────────────────────────────────────────

_FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

app = create_app(frontend_dist=_FRONTEND_DIST if _FRONTEND_DIST.exists() else None)
