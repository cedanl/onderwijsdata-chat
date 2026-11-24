"""Foutmeldingen van de API in het Nederlands, zonder de invoer te herhalen (#637).

FastAPI antwoordt bij ongeldige invoer met pydantic's lijst ("Field required", "Input should be ...",
met de verstuurde waarde erin) en bij een onbekend pad met Starlette's "Not Found". Deze handlers
vervangen alleen die standaardteksten. Wat een route zelf meldt ("Gesprek niet gevonden", een 429 met
Retry-After) gaat ongewijzigd door FastAPI's eigen handler, met de headers erbij. Een uitzondering die geen
route afving krijgt een JSON-500 met fout-ID (`onverwachte_fout`, #1154).
"""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.errors import log_interne_fout, melding_interne_fout

ONGELDIGE_INVOER = "Ongeldige invoer. Controleer de gegevens en probeer opnieuw."
NIET_GEVONDEN = "Niet gevonden"
# Wat de gebruiker onder Rapporten ziet, niet de naam van de tabel erachter (#1140).
RAPPORT_NIET_GEVONDEN = "Rapport niet gevonden"
METHODE_NIET_TOEGESTAAN = "Methode niet toegestaan"

# FastAPI's 400 voor een body die het niet kan lezen: ongeldige UTF-8 of JSON die te diep genest is (#1162).
# Gewone ongeldige JSON geeft al een RequestValidationError; deze twee kwamen als Engelse 400 door.
_BODY_NIET_TE_LEZEN = "There was an error parsing the body"

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
    if exc.status_code == 400 and exc.detail == _BODY_NIET_TE_LEZEN:
        return await _ongeldige_invoer(request, exc)
    return await http_exception_handler(request, _vertaald(exc))


def onverwachte_fout(request: Request, exc: Exception) -> JSONResponse:
    """Het antwoord op een uitzondering die een route niet afving (#1154): een 500 in JSON met een fout-ID.

    Geen exception handler voor `Exception`: Starlette draait die in ServerErrorMiddleware, buiten alle
    middleware, dus het antwoord kreeg geen security-headers en geen `Cache-Control: no-store`. De
    middleware `security_headers` roept deze functie zelf aan en zet die headers dan wel. Het log krijgt het
    type en een kenmerk van de uitzondering onder het fout-ID, de traceback op DEBUG (`log_interne_fout`).
    """
    route = request.scope.get("route")  # het pad met {parameters}, niet de waarden: die kunnen een id of naam zijn
    fout_id = log_interne_fout(exc, f"{request.method} {getattr(route, 'path', 'onbekende route')}")
    return JSONResponse({"detail": melding_interne_fout(fout_id)}, status_code=500)


def registreer(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _ongeldige_invoer)
    app.add_exception_handler(StarletteHTTPException, _http_fout)
