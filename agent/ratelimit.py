import asyncio
import logging
import os

import litellm

from .stream import Emit

logger = logging.getLogger(__name__)

_MAX_RETRIES = 4
_BASE_DELAY = 2.0
# Een Retry-After van de provider volgen, maar niet langer dan dit: de run heeft een tijdsgrens (#90).
_MAX_DELAY = 30.0
# LiteLLM request timeout (seconden). Azure AI kan traag zijn; standaard 600s → 1200s (#431).
_REQUEST_TIMEOUT = float(os.getenv("LITELLM_REQUEST_TIMEOUT", "1200"))


def _retry_after(exc: litellm.RateLimitError) -> float | None:
    """Het aantal seconden uit de Retry-After-header van de provider, als die er is."""
    headers = {str(k).lower(): v for k, v in (getattr(exc, "headers", None) or {}).items()}
    try:
        return float(headers["retry-after"])
    except (KeyError, TypeError, ValueError):
        return None


def _wachttijd(exc: litellm.RateLimitError, attempt: int) -> float:
    retry_after = _retry_after(exc)
    delay = retry_after if retry_after is not None else _BASE_DELAY * (2**attempt)
    return min(max(delay, 0.0), _MAX_DELAY)


def _log(exc: litellm.RateLimitError, attempt: int, delay: float | None) -> None:
    """Wat de provider meldde, zodat de capaciteit achteraf vast te stellen is (#431)."""
    logger.warning(
        "Rate limit (poging %d/%d): provider=%s model=%s status=%s request_id=%s retry_after=%s type=%s %s",
        attempt + 1,
        _MAX_RETRIES,
        getattr(exc, "llm_provider", None),
        getattr(exc, "model", None),
        getattr(exc, "status_code", None),
        getattr(exc, "request_id", None),
        _retry_after(exc),
        getattr(exc, "rate_limit_type", None),
        f"wacht {delay:.0f}s" if delay is not None else "geen nieuwe poging",
    )


async def acompletion_with_backoff(emit: Emit, **kwargs):
    """litellm.acompletion met backoff bij rate limit en timeout retry (#431).

    Timeout configuratie: stel LITELLM_REQUEST_TIMEOUT in (seconden, default 1200 voor Azure AI).
    """
    # Voeg request_timeout toe tenzij al meegegeven
    if "request_timeout" not in kwargs:
        kwargs["request_timeout"] = _REQUEST_TIMEOUT

    for attempt in range(_MAX_RETRIES):
        try:
            return await litellm.acompletion(**kwargs)
        except litellm.RateLimitError as exc:
            if attempt == _MAX_RETRIES - 1:
                _log(exc, attempt, None)
                raise
            delay = _wachttijd(exc, attempt)
            _log(exc, attempt, delay)
            await emit(
                {
                    "type": "toast",
                    "message": f"API rate limit bereikt, nieuwe poging over {delay:.0f}s…",
                    "level": "warning",
                }
            )
            await asyncio.sleep(delay)
        except (TimeoutError, asyncio.TimeoutError, litellm.APIConnectionError) as exc:
            # Timeout of verbinding verloren: herprobeert met backoff
            if attempt == _MAX_RETRIES - 1:
                logger.error("Model timeout na %d pogingen (%s)", _MAX_RETRIES, exc)
                raise
            delay = min(_BASE_DELAY * (2 ** attempt), _MAX_DELAY)
            logger.warning(
                "Model timeout (poging %d/%d): wacht %d seconden",
                attempt + 1,
                _MAX_RETRIES,
                delay,
            )
            await emit(
                {
                    "type": "toast",
                    "message": f"Model antwoordt traag, nieuwe poging over {delay:.0f}s…",
                    "level": "warning",
                }
            )
            await asyncio.sleep(delay)
