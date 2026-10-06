from core.config import SEED, TEMPERATURE, WILLMA_API_KEY, WILLMA_BASE_URL
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


# Voor herhaalbare analyses (#46). drop_params: een model dat temperature of seed niet
# ondersteunt (bijv. met extended thinking) krijgt ze niet, in plaats van een fout.
_SAMPLING_KWARGS: dict = {"temperature": TEMPERATURE, "seed": SEED, "drop_params": True}


def litellm_kwargs(model: str) -> dict:
    if WILLMA_API_KEY and model.startswith("openai/"):
        return {**_SAMPLING_KWARGS, **_WILLMA_KWARGS, "extra_body": {"model": model}}
    return dict(_SAMPLING_KWARGS)


def build_system(settings: dict | None = None, beurt: str = "") -> list[dict]:
    """Eén systeembericht; `beurt` (context van deze vraag) komt na het gecachete deel."""
    settings = settings or {}
    persona = build_persona_block(settings)
    text = persona + "\n\n" + SYSTEM_PROMPT if persona else SYSTEM_PROMPT
    content = [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
    if beurt:
        content.append({"type": "text", "text": beurt})
    return [{"role": "system", "content": content}]
