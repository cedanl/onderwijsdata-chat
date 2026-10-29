"""Wat de gebruiker van een fout ziet (#404).

Een fout van het model of de API (limiet, timeout, verbinding) hangt aan dat
model: een ander model kan wél lukken. Een interne fout (een bug in de code,
#392) faalt bij elk model gelijk. De gebruiker ziet dan een vaste melding met
een fout-ID; het type en een kenmerk van de uitzondering staan onder dat ID in de
log, de traceback op DEBUG (#502).
"""

import logging
import uuid

import litellm
import openai

from core.logging_util import foutkenmerk

logger = logging.getLogger(__name__)


class Gebruikersfout(Exception):
    """Een fout waarvan de tekst voor de gebruiker is geschreven (#503).

    Alleen deze tekst mag letterlijk naar de browser; elke andere uitzondering
    krijgt een vaste melding met fout-ID en de details gaan naar het log.
    """


# Alleen een limiet is iets wat de gebruiker zelf kan oplossen (even wachten): die houdt een vaste tekst zonder ID.
_FRIENDLY_ERRORS: list[tuple[type, str | None]] = [
    (litellm.RateLimitError, "Te veel verzoeken naar de API. Wacht even en probeer opnieuw."),
    (litellm.BadRequestError, None),
]

# Een ontbrekende of ongeldige sleutel, een onbekend model en een verbinding die de server met de provider niet krijgt
# zijn beheerderszaken (#712): een gebruiker heeft geen `.env` en zijn eigen internet is het niet. Hij krijgt een melding
# met fout-ID; wat er speelt (en waar de beheerder kijkt) staat onder dat ID in het log.
_MODEL_NIET_BESCHIKBAAR = (
    (litellm.AuthenticationError, "sleutel ontbreekt of is ongeldig: controleer de sleutel in het secret of `.env`"),
    (litellm.NotFoundError, "model niet gevonden: controleer `MODEL` en `AVAILABLE_MODELS`"),
    (litellm.APIConnectionError, "de server bereikt de provider niet: controleer de verbinding en `*_API_BASE`"),
)

# Zonder sleutel antwoordt geen enkel model (#790): dezelfde soort melding als hierboven, zonder `.env` of omgevingsvariabele.
# Welke sleutel ontbreekt, staat in het log.
MODEL_ZONDER_SLEUTEL = (
    "Het model is nu niet beschikbaar. Probeer het later opnieuw; blijft het misgaan, meld het dan aan de beheerder."
)

# Alle litellm-API-fouten erven van openai.OpenAIError; een budget of timeout hoort ook bij het model.
_MODELFOUTEN = (openai.OpenAIError, litellm.BudgetExceededError, TimeoutError)


def modelafhankelijk(exc: Exception) -> bool:
    """Kan een ander model hier wel slagen? Nee bij een fout in onze eigen code."""
    return isinstance(exc, _MODELFOUTEN)


def log_interne_fout(exc: Exception, waar: str) -> str:
    """Log de uitzondering onder een kort fout-ID en geef dat ID terug."""
    fout_id = uuid.uuid4().hex[:8]
    # Fouttekst en traceback kunnen vraag, antwoord of toolargumenten citeren (#502): op ERROR het type en
    # een kenmerk, de traceback onder hetzelfde ID op DEBUG. Eerst DEBUG, zodat de ERROR-regel de laatste is.
    logger.debug("Interne fout %s in %s", fout_id, waar, exc_info=exc)
    logger.error("Interne fout %s in %s: %s", fout_id, waar, foutkenmerk(exc))
    return fout_id


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, Gebruikersfout):
        return f"❌ {exc}"
    for exc_type, msg in _FRIENDLY_ERRORS:
        if isinstance(exc, exc_type):
            if msg is None:
                break
            return f"❌ {msg}"
    for exc_type, waar in _MODEL_NIET_BESCHIKBAAR:
        if isinstance(exc, exc_type):
            fout_id = log_interne_fout(exc, f"model/API ({waar})")
            return (
                f"❌ Het model is nu niet beschikbaar (fout-ID {fout_id}). Probeer het later opnieuw of kies een ander "
                "model; blijft het misgaan, geef dit ID dan door aan de beheerder."
            )
    if modelafhankelijk(exc):
        # Ook een API-fout kan interne details bevatten (#503): vaste tekst, details in het log.
        fout_id = log_interne_fout(exc, "model/API")
        return f"❌ Fout bij het model of de API (fout-ID {fout_id}). Probeer het opnieuw of kies een ander model."
    fout_id = log_interne_fout(exc, "verwerking")
    return f"❌ Er ging intern iets mis (fout-ID {fout_id}). Probeer het opnieuw; blijft het misgaan, geef dit ID dan door."


def error_event(exc: Exception) -> dict:
    """Het websocket-event voor een fout; de frontend toont alleen bij een modelfout een ander model."""
    return {"type": "error", "message": friendly_error(exc), "modelafhankelijk": modelafhankelijk(exc)}
