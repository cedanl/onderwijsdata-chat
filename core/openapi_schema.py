"""Het OpenAPI-schema zoals de API zich gedraagt (#1188), waar FastAPI's standaard afwijkt.

FastAPI beschrijft elke 422 als `HTTPValidationError`, een lijst met `{loc, msg, type}`. De API antwoordt sinds #637 met
`{"detail": "<tekst>"}` (`core.foutmeldingen`), dus een uit het schema gegenereerde client las elke 422 verkeerd.
Een route die een bestand geeft, noemt zijn eigen mediatype met `bijlage` in plaats van FastAPI's `application/json`.
"""

from fastapi import FastAPI

from core.foutmeldingen import ONGELDIGE_INVOER

FOUTMELDING = "Foutmelding"

_FASTAPI_VALIDATIE = ("HTTPValidationError", "ValidationError")

_FOUTMELDING_SCHEMA = {
    "title": FOUTMELDING,
    "type": "object",
    "properties": {"detail": {"type": "string", "title": "Detail", "examples": [ONGELDIGE_INVOER]}},
    "required": ["detail"],
}


def _foutvorm(schema: dict) -> None:
    """Elke 422 verwijst naar Foutmelding; FastAPI's validatieschema's gaan weg, want niets gebruikt ze nog."""
    schemas = schema.setdefault("components", {}).setdefault("schemas", {})
    for naam in _FASTAPI_VALIDATIE:
        schemas.pop(naam, None)
    schemas[FOUTMELDING] = _FOUTMELDING_SCHEMA
    antwoord = {
        "description": "Ongeldige invoer",
        "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{FOUTMELDING}"}}},
    }
    for operaties in schema["paths"].values():
        for operatie in operaties.values():
            if "422" in operatie["responses"]:
                operatie["responses"]["422"] = antwoord


def bijlage(media_type: str, beschrijving: str) -> dict[int | str, dict]:
    """De `responses=` van een route die een bestand als bijlage geeft, voor een 200 met dit mediatype.

    Samen met `response_class=Response` op de route: zonder dat voegt FastAPI zelf `application/json` aan het 200-antwoord
    toe, ook als de route een `Response` met een ander mediatype teruggeeft.
    """
    return {
        200: {
            "description": beschrijving,
            "content": {media_type: {"schema": {"type": "string", "format": "binary"}}},
            "headers": {
                "Content-Disposition": {
                    "description": '`attachment; filename="<naam>"`: de browser bewaart het antwoord als bestand.',
                    "schema": {"type": "string"},
                }
            },
        }
    }


def registreer(app: FastAPI) -> None:
    """Laat `app.openapi()` het schema één keer opbouwen en daarna aanpassen; het resultaat blijft in de cache."""
    standaard = app.openapi

    def openapi() -> dict:
        if app.openapi_schema is None:
            _foutvorm(standaard())  # bouwt app.openapi_schema; hier op dezelfde dict aangepast
        return app.openapi_schema or {}

    app.openapi = openapi  # type: ignore[method-assign]
