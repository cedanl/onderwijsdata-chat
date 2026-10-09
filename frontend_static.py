"""De gebouwde React-app serveren, met caching die past bij Vite-uitvoer (#110).

Bestanden onder /assets dragen een inhoudshash in hun naam: een nieuwe build geeft
nieuwe namen, dus de browser mag ze een jaar bewaren zonder opnieuw te vragen.
index.html verwijst naar die namen en moet daarom bij elke load vers zijn, anders
draait een browser na een deploy nog de oude app.

Onbekende paden onder /api krijgen een JSON-404 in plaats van index.html (#482):
een client die een API-pad verkeerd spelt, hoort een fout te zien en geen HTML met 200.
"""

from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

_EEN_JAAR = "public, max-age=31536000, immutable"


class _GehashteAssets(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = _EEN_JAAR
        return response


def mount_frontend(app: FastAPI, dist: Path) -> None:
    app.mount("/assets", _GehashteAssets(directory=dist / "assets"), name="assets")

    @app.get("/api", include_in_schema=False)
    @app.get("/api/{rest:path}", include_in_schema=False)
    async def onbekende_api_route() -> JSONResponse:
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> Response:
        return Response(
            content=(dist / "index.html").read_text(),
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )
