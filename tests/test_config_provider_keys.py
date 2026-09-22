"""Test provider→API-key mapping for drift prevention (#53)."""

import pytest
from core.config import get_required_api_key_env_var, get_all_api_key_env_vars


class TestProviderApiKeyMapping:
    """Validate that provider→key mapping is consistent and drift-free.

    The mapping in config._PROVIDER_API_KEYS is the single source of truth.
    This test ensures that routes/chat.py and tests/test_eval_aggregation.py
    both rely on it, preventing drift.
    """

    def test_known_providers_map_to_keys(self):
        """Each known provider maps to its correct API key environment variable."""
        assert get_required_api_key_env_var("anthropic/claude-opus") == "ANTHROPIC_API_KEY"
        assert get_required_api_key_env_var("openai/gpt-4") == "OPENAI_API_KEY"
        assert get_required_api_key_env_var("azure_ai/claude") == "AZURE_AI_API_KEY"
        assert get_required_api_key_env_var("azure/gpt") == "AZURE_API_KEY"
        assert get_required_api_key_env_var("gemini/model") == "GEMINI_API_KEY"
        assert get_required_api_key_env_var("willma/llama") == "WILLMA_API_KEY"

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

    def test_get_all_api_key_env_vars_excludes_none(self):
        """get_all_api_key_env_vars only returns actual env var names (no None)."""
        all_keys = get_all_api_key_env_vars()
        assert all_keys is not None
        assert isinstance(all_keys, list)
        assert len(all_keys) > 0
        # All items should be strings (actual env var names), no None
        assert all(isinstance(k, str) for k in all_keys)
        # No duplicates
        assert len(all_keys) == len(set(all_keys))

    def test_api_key_vars_are_reasonable(self):
        """All returned API key vars look like environment variable names."""
        all_keys = get_all_api_key_env_vars()
        expected = {
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_API_KEY",
            "AZURE_AI_API_KEY", "GEMINI_API_KEY", "WILLMA_API_KEY"
        }
        assert set(all_keys) == expected, (
            f"API key vars changed. Got: {set(all_keys)}, "
            f"Expected: {expected}. Update test if intentional."
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
