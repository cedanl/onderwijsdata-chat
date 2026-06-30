import litellm

_FRIENDLY_ERRORS: list[tuple[type, str]] = [
    (litellm.AuthenticationError, "API key ontbreekt of is ongeldig. Controleer je `.env` bestand."),
    (litellm.NotFoundError, "Model niet gevonden. Controleer de `MODEL` instelling in `.env`."),
    (litellm.RateLimitError, "Te veel verzoeken naar de API. Wacht even en probeer opnieuw."),
    (litellm.APIConnectionError, "Kan de API niet bereiken. Controleer je internetverbinding."),
    (litellm.BadRequestError, "Het verzoek werd afgewezen door de API. Mogelijk een ongeldig model of parameter."),
]


def friendly_error(exc: Exception) -> str:
    for exc_type, msg in _FRIENDLY_ERRORS:
        if isinstance(exc, exc_type):
            return f"❌ {msg}"
    return f"❌ Er is een fout opgetreden: {exc}"
