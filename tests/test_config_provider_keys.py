"""Test provider→API-key mapping for drift prevention (#53)."""

from core.config import get_all_api_key_env_vars, get_required_api_key_env_var


class TestProviderApiKeyMapping:
    """De mapping provider → sleutel in core/config.py (`_PROVIDER_API_KEYS`) is de ene bron (ADR-003).

    Deze tests leggen de mapping zelf vast: welke sleutel bij een prefix hoort, en welke namen
    `get_all_api_key_env_vars()` geeft (de lijst die /ready en de chat lezen). Dat de afnemers hem gebruiken,
    toetsen ze niet.
    """

    def test_known_providers_map_to_keys(self):
        """Each known provider maps to its correct API key environment variable."""
        assert get_required_api_key_env_var("anthropic/claude-opus") == "ANTHROPIC_API_KEY"
        assert get_required_api_key_env_var("openai/gpt-4") == "OPENAI_API_KEY"
        assert get_required_api_key_env_var("azure_ai/claude") == "AZURE_AI_API_KEY"
        assert get_required_api_key_env_var("azure/gpt") == "AZURE_API_KEY"
        assert get_required_api_key_env_var("gemini/model") == "GEMINI_API_KEY"

    def test_ollama_does_not_require_key(self):
        """Ollama models don't require API keys."""
        assert get_required_api_key_env_var("ollama/mistral") is None
        assert get_required_api_key_env_var("ollama_chat/neural-chat") is None

    def test_unknown_provider_returns_none(self):
        """Unknown providers handled gracefully (no error, just None)."""
        assert get_required_api_key_env_var("unknown-provider/model") is None
        assert get_required_api_key_env_var("future-ai/model") is None

    def test_empty_model_id_returns_none(self):
        """Empty model IDs don't crash."""
        assert get_required_api_key_env_var("") is None
        assert get_required_api_key_env_var(None) is None

    def test_api_key_vars_are_reasonable(self):
        """All returned API key vars look like environment variable names."""
        all_keys = get_all_api_key_env_vars()
        expected = {
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "AZURE_API_KEY",
            "AZURE_AI_API_KEY",
            "GEMINI_API_KEY",
            "WILLMA_API_KEY",
        }
        # Gesorteerd vergeleken: ook een dubbele naam of een None valt op.
        assert sorted(all_keys) == sorted(expected), (
            f"API key vars changed. Got: {all_keys}, Expected: {expected}. Update test if intentional."
        )

    def test_provider_extraction_from_model_id(self):
        """Provider prefix correctly extracted from model ID (part before '/')."""
        # Standard format: provider/model-name
        assert get_required_api_key_env_var("anthropic/claude-sonnet-4-6") == "ANTHROPIC_API_KEY"
        assert get_required_api_key_env_var("openai/gpt-4o-mini") == "OPENAI_API_KEY"

        # Multi-slash format (nested paths)
        assert get_required_api_key_env_var("openai/openai/gpt-oss-120b") == "OPENAI_API_KEY"
        assert get_required_api_key_env_var("openai/Qwen/Qwen2.5-Coder-32B") == "OPENAI_API_KEY"

    def test_case_insensitive_provider_matching(self):
        """Provider names are lowercased for matching."""
        # The function lowercases the provider prefix before lookup
        assert get_required_api_key_env_var("ANTHROPIC/model") == "ANTHROPIC_API_KEY"
        assert get_required_api_key_env_var("OpenAI/model") == "OPENAI_API_KEY"


def test_llm_calls_are_deterministic_by_default():
    # #46: temperature stond op de provider-default 1.0, de grootste bron van runvariatie.
    from agent.models import litellm_kwargs

    kwargs = litellm_kwargs("anthropic/claude-sonnet-4-6")
    assert kwargs["temperature"] == 0
    assert kwargs["seed"] == 42
    assert kwargs["drop_params"] is True  # a provider without seed support must not fail the call
