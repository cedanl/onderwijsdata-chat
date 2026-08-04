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

# Display names voor bekende modellen — voor onbekende modellen wordt het deel na '/' gebruikt.
_KNOWN_NAMES: dict[str, tuple[str, str, str]] = {
    "anthropic/claude-haiku-4-5-20251001": ("Haiku", "Snel en goedkoop", "zap"),
    "anthropic/claude-sonnet-4-6":         ("Sonnet", "Gebalanceerd", "sparkles"),
    "anthropic/claude-opus-4-6":           ("Opus 4.6", "Hoog kwaliteit", "brain"),
    "anthropic/claude-opus-4-7":           ("Opus 4.7", "Hoog kwaliteit", "brain"),
    "anthropic/claude-opus-4-8":           ("Opus 4.8", "Meest capabel", "brain"),
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
