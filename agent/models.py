from config import WILLMA_API_KEY, WILLMA_BASE_URL
from prompt import SYSTEM_PROMPT_SNEL, SYSTEM_PROMPT_VERDIEP, _SPARREN_SNEL_ADDENDUM, build_persona_block

_WILLMA_KWARGS: dict = (
    {
        "api_base": WILLMA_BASE_URL,
        "api_key": WILLMA_API_KEY,
        "extra_headers": {"X-API-KEY": WILLMA_API_KEY},
    }
    if WILLMA_API_KEY
    else {}
)


def litellm_kwargs(model: str) -> dict:
    if WILLMA_API_KEY and not model.startswith("anthropic/") and not model.startswith("ollama"):
        return _WILLMA_KWARGS
    return {}


def build_system(modus: str, settings: dict | None = None) -> list[dict]:
    settings = settings or {}
    text = SYSTEM_PROMPT_VERDIEP if modus == "verdiep" else SYSTEM_PROMPT_SNEL
    if settings.get("sparren") and modus == "snel":
        text += _SPARREN_SNEL_ADDENDUM
    text += build_persona_block(settings)
    return [{"role": "system", "content": [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]}]
