"""De gebouwde React-app serveren, met caching die past bij Vite-uitvoer (#110).

Bestanden onder /assets dragen een inhoudshash in hun naam: een nieuwe build geeft
nieuwe namen, dus de browser mag ze een jaar bewaren zonder opnieuw te vragen.
index.html verwijst naar die namen en moet daarom bij elke load vers zijn, anders
draait een browser na een deploy nog de oude app.

Onbekende paden onder /api krijgen een JSON-404 in plaats van index.html (#482):
een client die een API-pad verkeerd spelt, hoort een fout te zien en geen HTML met 200.

HEAD op een pad van de app-shell antwoordt als GET, zonder body (#654). Een pad dat een
andere route kent (/health, alles onder /api) houdt bij HEAD zijn 405, zoals voorheen.
"""

from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

from core.foutmeldingen import NIET_GEVONDEN

_EEN_JAAR = "public, max-age=31536000, immutable"


class _GehashteAssets(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = _EEN_JAAR
        return response


class _SpaRoute(APIRoute):
    """De catch-all van de app-shell, die een HEAD beantwoordt als GET.

    FastAPI zet HEAD niet bij een GET-route. De router geeft een HEAD alleen aan deze route als
    geen eerdere route het pad kent; kent een wel het pad (/health, /api/ping, de JSON-404 onder
    /api), dan antwoordt die zelf met 405. Methods blijft GET: het schema krijgt er niets bij.
    """

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["method"] == "HEAD":
            # Een kopie: de server houdt HEAD in zijn eigen scope en stuurt dan geen body mee.
            scope = {**scope, "method": "GET"}
        await super().handle(scope, receive, send)


def mount_frontend(app: FastAPI, dist: Path) -> None:
    app.mount("/assets", _GehashteAssets(directory=dist / "assets"), name="assets")

    @app.get("/api", include_in_schema=False)
    @app.get("/api/{rest:path}", include_in_schema=False)
    async def onbekende_api_route() -> JSONResponse:
        return JSONResponse({"detail": NIET_GEVONDEN}, status_code=404)

    async def serve_spa(full_path: str) -> Response:
        return Response(
            content=(dist / "index.html").read_text(),
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    app.router.add_api_route("/{full_path:path}", serve_spa, methods=["GET"], route_class_override=_SpaRoute)
