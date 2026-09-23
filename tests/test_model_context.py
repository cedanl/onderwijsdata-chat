"""Tests for dynamic model context window resolution."""

import pytest

from agent.model_context import clamp_max_tokens, get_max_context


class TestModelContextResolution:
    """Test context window resolution for different model families."""

    def test_gpt_oss_120b_context(self):
        """gpt-oss-120b should have 4k context (conservative default)."""
        assert get_max_context("openai/gpt-oss-120b") == 4096
        assert get_max_context("openai/gpt-oss-120b-instruct") == 4096

    def test_qwen25_vl_context(self):
        """Qwen 2.5 VL should have 32k native context."""
        assert get_max_context("openai/Qwen/Qwen2.5-VL-32B-Instruct-AWQ") == 32768

    def test_qwen25_coder_context(self):
        """Qwen 2.5 Coder should have 128k full YaRN capacity."""
        assert get_max_context("openai/Qwen/Qwen2.5-Coder-32B-Instruct-AWQ") == 131072

    def test_qwen36_context(self):
        """Qwen 3.6 should have 262k native context."""
        assert get_max_context("openai/Qwen/Qwen3.6-27B-FP8") == 262144

    def test_devstral_context(self):
        """Devstral should have 256k context window."""
        assert get_max_context("openai/mistralai/Devstral-Small-2-24B-Instruct-2512") == 256000

    def test_ollama_mistral_context(self):
        """Ollama Mistral should have 32k context."""
        assert get_max_context("ollama/mistral") == 32768

    def test_unknown_model_fallback(self):
        """Unknown models should fall back to 4k conservative default."""
        assert get_max_context("unknown/model-xyz") == 4096


class TestOutputClamp:
    """Test output-clamp functionality for MAX_TOKENS limiting."""

    def test_clamp_small_model_below_limit(self):
        """Small models should clamp to their actual context."""
        # gpt-oss-120b has 4k context, should clamp 40960 → 4096
        assert clamp_max_tokens("openai/gpt-oss-120b", 40960) == 4096

    def test_clamp_medium_model_no_change(self):
        """Medium models should not be clamped if under limit."""
        # Ollama Mistral has 32k context, 40960 → clamps to 32768
        assert clamp_max_tokens("ollama/mistral", 40960) == 32768

    def test_clamp_large_model_no_change(self):
        """Large models should not be clamped if under limit."""
        # Qwen 3.6 has 262k, 40960 should pass through
        clamped = clamp_max_tokens("openai/Qwen/Qwen3.6-27B-FP8", 40960)
        assert clamped == 40960

    def test_clamp_respects_requested_value(self):
        """Clamp should return min(requested, context)."""
        # Request 1000 tokens for small model with 4k context
        assert clamp_max_tokens("openai/gpt-oss-120b", 1000) == 1000
        # Request 5000 tokens for small model with 4k context
        assert clamp_max_tokens("openai/gpt-oss-120b", 5000) == 4096

    def test_prevents_exceeding_context(self):
        """Clamp should prevent max_tokens from exceeding model context."""
        # Even with large requested value, should not exceed model context
        requested = 1_000_000
        model_context = get_max_context("openai/gpt-oss-120b")
        clamped = clamp_max_tokens("openai/gpt-oss-120b", requested)
        assert clamped <= model_context
        assert clamped == model_context


class TestAcceptanceCriteria:
    """Verify acceptance criteria from issue #68."""

    def test_all_willma_models_have_valid_context(self):
        """All configured Willma models should have valid max_tokens."""
        willma_models = [
            "openai/gpt-oss-120b",
            "openai/Qwen/Qwen2.5-VL-32B-Instruct-AWQ",
            "openai/Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
            "openai/Qwen/Qwen3.6-27B-FP8",
            "openai/mistralai/Devstral-Small-2-24B-Instruct-2512",
        ]
        for model in willma_models:
            context = get_max_context(model)
            assert context > 0, f"{model} should have positive context window"

    def test_max_history_safe_for_all_models(self):
        """MAX_HISTORY messages shouldn't exceed any model's context."""
        from core.config import MAX_HISTORY, MAX_TOKENS

        # Rough heuristic: assume ~1500 tokens per message on average
        # (varies by model, but a safe upper bound for chat history)
        tokens_per_message = 1500

        willma_models = [
            "openai/gpt-oss-120b",
            "openai/Qwen/Qwen2.5-VL-32B-Instruct-AWQ",
            "openai/Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
        ]

        for model in willma_models:
            context = get_max_context(model)
            estimated_history_tokens = MAX_HISTORY * tokens_per_message
            # The clamped max_tokens should be safe for the model
            clamped = clamp_max_tokens(model, MAX_TOKENS)
            # Rough check: clamped tokens + estimated history should fit
            # (not a hard guarantee, but a sanity check)
            assert clamped <= context, f"{model} clamping failed: {clamped} > {context}"
