from core.config import WILLMA_API_KEY, WILLMA_BASE_URL
from prompts import SYSTEM_PROMPT, build_persona_block

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
    if WILLMA_API_KEY and model.startswith("openai/"):
        return _WILLMA_KWARGS
    return {}


def build_system(settings: dict | None = None) -> list[dict]:
    settings = settings or {}
    persona = build_persona_block(settings)
    text = persona + "\n\n" + SYSTEM_PROMPT if persona else SYSTEM_PROMPT
    return [{"role": "system", "content": [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]}]
