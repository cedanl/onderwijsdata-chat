"""Wat de gebruiker van een fout ziet (#404).

Een fout van het model of de API (limiet, timeout, verbinding) hangt aan dat
model: een ander model kan wél lukken. Een interne fout (een bug in de code,
#392) faalt bij elk model gelijk. De gebruiker ziet dan een vaste melding met
een fout-ID; de uitzondering zelf staat onder dat ID in de log.
"""

import logging
import uuid

import litellm
import openai

logger = logging.getLogger(__name__)

_FRIENDLY_ERRORS: list[tuple[type, str | None]] = [
    (litellm.AuthenticationError, "API key ontbreekt of is ongeldig. Controleer je `.env` bestand."),
    (litellm.NotFoundError, "Model niet gevonden. Controleer de `MODEL` instelling in `.env`."),
    (litellm.RateLimitError, "Te veel verzoeken naar de API. Wacht even en probeer opnieuw."),
    (litellm.APIConnectionError, "Kan de API niet bereiken. Controleer je internetverbinding."),
    (litellm.BadRequestError, None),
]

# Alle litellm-API-fouten erven van openai.OpenAIError; een budget of timeout hoort ook bij het model.
_MODELFOUTEN = (openai.OpenAIError, litellm.BudgetExceededError, TimeoutError)


def modelafhankelijk(exc: Exception) -> bool:
    """Kan een ander model hier wel slagen? Nee bij een fout in onze eigen code."""
    return isinstance(exc, _MODELFOUTEN)


def log_interne_fout(exc: Exception, waar: str) -> str:
    """Log de uitzondering onder een kort fout-ID en geef dat ID terug."""
    fout_id = uuid.uuid4().hex[:8]
    logger.error("Interne fout %s in %s", fout_id, waar, exc_info=exc)
    return fout_id


def friendly_error(exc: Exception) -> str:
    for exc_type, msg in _FRIENDLY_ERRORS:
        if isinstance(exc, exc_type):
            if msg is None:
                break
            return f"❌ {msg}"
    if modelafhankelijk(exc):
        return f"❌ {exc}"
    fout_id = log_interne_fout(exc, "verwerking")
    return f"❌ Er ging intern iets mis (fout-ID {fout_id}). Probeer het opnieuw; blijft het misgaan, geef dit ID dan door."


def error_event(exc: Exception) -> dict:
    """Het websocket-event voor een fout; de frontend toont alleen bij een modelfout een ander model."""
    return {"type": "error", "message": friendly_error(exc), "modelafhankelijk": modelafhankelijk(exc)}
