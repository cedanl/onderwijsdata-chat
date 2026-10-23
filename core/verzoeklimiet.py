"""Een bovengrens op de grootte van een HTTP-verzoek (#682).

`PUT /api/conversations/{id}` en `PUT /api/workbooks/{id}` nemen een vrij JSON-lichaam aan; zonder grens kon één
gebruiker het geheugen van de pod en de database vullen. Een verzoek met een te grote Content-Length krijgt meteen
413; zonder lengte (chunked) telt de middleware wat er binnenkomt en stopt bij de grens.
"""

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

TE_GROOT = "Het verzoek is te groot."


class Verzoeklimiet:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        lengte = dict(scope["headers"]).get(b"content-length", b"")
        if lengte.isdigit() and int(lengte) > self.max_bytes:
            await JSONResponse({"detail": TE_GROOT}, status_code=413)(scope, receive, send)
            return
        ontvangen = 0

        async def tellend() -> Message:
            nonlocal ontvangen
            bericht = await receive()
            if bericht["type"] == "http.request":
                ontvangen += len(bericht.get("body", b""))
                if ontvangen > self.max_bytes:
                    # FastAPI laat een HTTPException uit het lezen van het lichaam door (routing.py), zodat de
                    # gewone foutafhandeling er 413 van maakt in plaats van "error parsing the body".
                    raise HTTPException(status_code=413, detail=TE_GROOT)
            return bericht

        await self.app(scope, tellend, send)
