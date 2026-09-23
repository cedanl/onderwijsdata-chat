"""Dynamic context window resolution per model.

Uses litellm.get_max_tokens() as the source of truth, with manual overrides
for models not mapped in LiteLLM (e.g., SURF Willma models).

Addresses issue #68: makes max_tokens dynamic per model instead of hardcoded 40960.
"""

import logging

import litellm

logger = logging.getLogger(__name__)

# Models not in LiteLLM's mapping — add context window manually.
# Format: "provider/model-name" → max_tokens for that model.
# Sources & native context lengths:
#   - gpt-oss-120b: https://huggingface.co/openai/gpt-oss-120b
#     (OpenAI OSS 120B; model card doesn't specify context, using conservative 4k default)
#   - Qwen2.5-VL-32B: https://huggingface.co/Qwen/Qwen2.5-VL-32B-Instruct-AWQ
#     (Vision-language model; 32k native context)
#   - Qwen2.5-Coder-32B: https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
#     (Code specialist; 128k with YaRN, using full capacity)
#   - Qwen3.6-27B: https://huggingface.co/Qwen/Qwen3.6-27B-FP8
#     (262k native, extensible to 1M; using native default)
#   - Devstral-Small-2-24B: https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512
#     (Development model; 256k context window)
_MODEL_CONTEXT_OVERRIDES: dict[str, int] = {
    "openai/gpt-oss-120b": 4096,
    "openai/gpt-oss-120b-instruct": 4096,
    "openai/Qwen/Qwen2.5-VL-32B-Instruct-AWQ": 32768,
    "openai/Qwen/Qwen2.5-Coder-32B-Instruct-AWQ": 131072,  # 128k full capacity via YaRN
    "openai/Qwen/Qwen2.5-Coder-7B-Instruct": 32768,
    "openai/Qwen/Qwen3.6-27B-FP8": 262144,  # 262k native
    "openai/mistralai/Devstral-Small-2-24B-Instruct-2512": 256000,
    "ollama/mistral": 32768,
}


def get_max_context(model: str) -> int:
    """Get maximum context window (in tokens) for a model.

    Args:
        model: Model ID in format "provider/model-name" (e.g., "openai/gpt-4o")

    Returns:
        Maximum tokens the model can accept in a single request.
        Falls back to 4096 if model is completely unknown.
    """
    # Check overrides first (models not in LiteLLM)
    if model in _MODEL_CONTEXT_OVERRIDES:
        ctx = _MODEL_CONTEXT_OVERRIDES[model]
        logger.debug("Model context (override): %s → %d tokens", model, ctx)
        return ctx

    # Try LiteLLM's built-in mappings
    try:
        ctx = litellm.get_max_tokens(model)
        if ctx and ctx > 0:
            logger.debug("Model context (litellm): %s → %d tokens", model, ctx)
            return ctx
    except Exception as e:
        logger.warning("litellm.get_max_tokens(%s) failed: %s", model, e)

    # Fallback: conservative default
    logger.warning("Model context unknown for %s, using 4096", model)
    return 4096


def clamp_max_tokens(model: str, requested: int) -> int:
    """Clamp max_tokens to the model's actual context window.

    Prevents "max_tokens exceeds context" errors by ensuring the requested
    max_tokens never exceeds what the model can handle.

    Args:
        model: Model ID
        requested: Requested max_tokens (typically from config)

    Returns:
        min(requested, model's actual context window)
    """
    context = get_max_context(model)
    clamped = min(requested, context)
    if clamped < requested:
        logger.info(
            "Clamped max_tokens: %s requested %d, model context %d → using %d",
            model,
            requested,
            context,
            clamped,
        )
    return clamped
