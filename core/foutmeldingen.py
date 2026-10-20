"""Foutmeldingen van de API in het Nederlands, zonder de invoer te herhalen (#637).

FastAPI antwoordt bij ongeldige invoer met pydantic's lijst ("Field required", "Input should be ...",
met de verstuurde waarde erin) en bij een onbekend pad met Starlette's "Not Found". Deze handlers
vervangen alleen die standaardteksten. Wat een route zelf meldt ("Gesprek niet gevonden", een 429 met
Retry-After) gaat ongewijzigd door FastAPI's eigen handler, met de headers erbij.
"""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

ONGELDIGE_INVOER = "Ongeldige invoer. Controleer de gegevens en probeer opnieuw."
NIET_GEVONDEN = "Niet gevonden"
METHODE_NIET_TOEGESTAAN = "Methode niet toegestaan"

# Per status de Nederlandse tekst voor Starlette's standaardzin (HTTPStatus(...).phrase).
_STANDAARDZINNEN = {404: NIET_GEVONDEN, 405: METHODE_NIET_TOEGESTAAN}


async def _ongeldige_invoer(request: Request, exc: Exception) -> JSONResponse:
    # Geen veldnamen of waarden: de melding herhaalt nooit wat er is verstuurd.
    return JSONResponse({"detail": ONGELDIGE_INVOER}, status_code=422)


def _vertaald(exc: StarletteHTTPException) -> StarletteHTTPException:
    """De uitzondering met een Nederlandse detail als die Starlette's standaardzin is; anders dezelfde."""
    tekst = _STANDAARDZINNEN.get(exc.status_code)
    if tekst is None or exc.detail != HTTPStatus(exc.status_code).phrase:
        return exc
    return StarletteHTTPException(exc.status_code, detail=tekst, headers=exc.headers)


async def _http_fout(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, StarletteHTTPException):  # alleen hiervoor geregistreerd; voor de typechecker
        raise exc
    return await http_exception_handler(request, _vertaald(exc))


def registreer(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _ongeldige_invoer)
    app.add_exception_handler(StarletteHTTPException, _http_fout)
