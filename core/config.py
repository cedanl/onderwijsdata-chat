import os

MODEL = os.getenv("MODEL", "anthropic/claude-sonnet-4-6")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "40960"))
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "25"))
CBS_ROW_LIMIT = int(os.getenv("CBS_ROW_LIMIT", "5000"))
RIO_PAGE_SIZE = int(os.getenv("RIO_PAGE_SIZE", "50"))
DUO_ROW_LIMIT = int(os.getenv("DUO_ROW_LIMIT", "500"))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "40"))

# Willma AI-Hub (SURF) — optioneel. Zet WILLMA_API_KEY om via Willma te draaien.
# Zet MODEL naar bijv. "openai/Qwen2.5-Coder-7B-Instruct" om een specifiek Willma-model te kiezen.
WILLMA_API_KEY = os.getenv("WILLMA_API_KEY")
WILLMA_BASE_URL = os.getenv("WILLMA_BASE_URL", "")

# Kommagescheiden lijst van LiteLLM model-IDs voor de model-picker in de UI.
# Niet ingesteld → geen model-picker, de app gebruikt altijd MODEL.
_AVAILABLE_MODELS_RAW = os.getenv("AVAILABLE_MODELS")

# Per-gebruiker model-picker: "user1:model_a,model_b;user2:model_c"
# Gebruikers niet in deze lijst krijgen de globale AVAILABLE_MODELS.
_USER_MODELS_RAW = os.getenv("USER_MODELS", "")

# Provider prefix → API key environment variable mapping. Centraal punt voor drift-preventie.
# Zie #53: één plek waar alle provider→key mappings staan.
_PROVIDER_API_KEYS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "azure_ai": "AZURE_AI_API_KEY",
    "azure": "AZURE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "willma": "WILLMA_API_KEY",
    "ollama": None,  # Ollama doesn't require API key
    "ollama_chat": None,
}


def get_required_api_key_env_var(model_id: str) -> str | None:
    """Get the environment variable name for a model's required API key.

    Extracts the provider prefix (part before first '/') and looks up the
    corresponding environment variable. Returns None if provider is unknown
    or doesn't require a key (ollama).

    Examples:
        'anthropic/claude-opus' → 'ANTHROPIC_API_KEY'
        'openai/gpt-4o' → 'OPENAI_API_KEY'
        'ollama/mistral' → None
        'unknown-provider/model' → None (unknown provider handled gracefully)
    """
    if not model_id:
        return None
    provider = model_id.split("/")[0].lower()
    return _PROVIDER_API_KEYS.get(provider)


def get_all_api_key_env_vars() -> list[str]:
    """Get all environment variable names that might contain API keys.

    Used to check if ANY API key is configured (for startup checks).
    Filters out None values (providers that don't need keys).
    """
    return [k for k in _PROVIDER_API_KEYS.values() if k is not None]


# Display names voor bekende modellen — voor onbekende modellen wordt het deel na '/' gebruikt.
_KNOWN_NAMES: dict[str, tuple[str, str, str]] = {
    "anthropic/claude-haiku-4-5-20251001": ("Haiku", "Snel en goedkoop", "zap"),
    "anthropic/claude-sonnet-4-6":         ("Sonnet", "Gebalanceerd", "sparkles"),
    "anthropic/claude-opus-4-6":           ("Opus 4.6", "Hoog kwaliteit", "brain"),
    "anthropic/claude-opus-4-7":           ("Opus 4.7", "Hoog kwaliteit", "brain"),
    "anthropic/claude-opus-4-8":           ("Opus 4.8", "Meest capabel", "brain"),
    "azure_ai/claude-sonnet-4-6":         ("Sonnet (Foundry)", "Azure AI Foundry", "sparkles"),
    "azure_ai/claude-opus-4-6":           ("Opus 4.6 (Foundry)", "Azure AI Foundry — hoog kwaliteit", "brain"),
    "azure_ai/claude-haiku-4-5":          ("Haiku (Foundry)", "Azure AI Foundry — snel", "zap"),
    "openai/gpt-4o-mini":                  ("GPT-4o mini", "Snel", "zap"),
    "openai/gpt-4o":                       ("GPT-4o", "Capabel", "sparkles"),
    "openai/gpt-5":                        ("GPT-5", "Meest capabel", "brain"),
    "openai/openai/gpt-oss-120b":                      ("GPT-OSS 120B", "SURF Willma — sterk in tool calling", "cpu"),
    "openai/Qwen/Qwen2.5-VL-32B-Instruct-AWQ":        ("Qwen 2.5 VL 32B", "SURF Willma — vision+taal", "cpu"),
    "openai/Qwen/Qwen2.5-Coder-32B-Instruct-AWQ":     ("Qwen 2.5 Coder 32B", "SURF Willma — code", "cpu"),
}


def _parse_user_models() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if not _USER_MODELS_RAW.strip():
        return result
    for entry in _USER_MODELS_RAW.split(";"):
        entry = entry.strip()
        if ":" not in entry:
            continue
        username, _, models_str = entry.partition(":")
        models = [m.strip() for m in models_str.split(",") if m.strip()]
        if username.strip() and models:
            result[username.strip()] = models
    return result


_USER_MODELS: dict[str, list[str]] = _parse_user_models()


def _models_from_ids(model_ids: list[str]) -> list[tuple[str, str, str, str]]:
    return [
        (mid,) + _KNOWN_NAMES.get(mid, (mid.split("/")[-1], "", "cpu"))
        for mid in model_ids
    ]


def get_available_models() -> list[tuple[str, str, str, str]] | None:
    """Return list of (model_id, name, description, icon), or None if no picker."""
    if not _AVAILABLE_MODELS_RAW:
        return None
    result = _models_from_ids(
        [m.strip() for m in _AVAILABLE_MODELS_RAW.split(",") if m.strip()]
    )
    return result or None


def get_available_models_for_user(username: str | None) -> list[tuple[str, str, str, str]] | None:
    """Return per-user models if configured, else fall back to global AVAILABLE_MODELS."""
    if username and username in _USER_MODELS:
        return _models_from_ids(_USER_MODELS[username]) or None
    return get_available_models()
