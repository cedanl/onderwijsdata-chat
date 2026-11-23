"""Het OpenAPI-schema zoals de API zich gedraagt (#1188), waar FastAPI's standaard afwijkt.

FastAPI beschrijft elke 422 als `HTTPValidationError`, een lijst met `{loc, msg, type}`. De API antwoordt sinds #637 met
`{"detail": "<tekst>"}` (`core.foutmeldingen`), dus een uit het schema gegenereerde client las elke 422 verkeerd.
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


def registreer(app: FastAPI) -> None:
    """Laat `app.openapi()` het schema één keer opbouwen en daarna aanpassen; het resultaat blijft in de cache."""
    standaard = app.openapi

    def openapi() -> dict:
        if app.openapi_schema is None:
            _foutvorm(standaard())  # bouwt app.openapi_schema; hier op dezelfde dict aangepast
        return app.openapi_schema or {}

    app.openapi = openapi  # type: ignore[method-assign]
