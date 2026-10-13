"""Modellen in de picker: platte labels, provider en provider-key (#496, F10)."""

import pytest

from core import config
from core.config import _KNOWN_NAMES, _models_from_ids, get_required_api_key_env_var, model_provider

SONNET_55 = "azure_ai/claude-sonnet-5-5"
OPUS_55 = "azure_ai/claude-opus-5-5"
WILLMA_IDS = {
    "openai/openai/gpt-oss-120b",
    "openai/Qwen/Qwen2.5-VL-32B-Instruct-AWQ",
    "openai/Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
}
PROVIDER_BY_PREFIX = {"anthropic": "Anthropic", "azure_ai": "Microsoft Azure AI Foundry", "openai": "OpenAI"}
# Woorden die in het bijschrift horen, niet in naam of omschrijving van het model.
JARGON = ("foundry", "azure", "willma", "surf", "tool calling")


@pytest.fixture
def zonder_willma(monkeypatch):
    monkeypatch.setattr(config, "WILLMA_API_KEY", None)


@pytest.fixture
def met_willma(monkeypatch):
    monkeypatch.setattr(config, "WILLMA_API_KEY", "test-sleutel")


def test_foundry_55_models_require_azure_ai_key():
    """Beide 5-5-modellen vallen onder AZURE_AI_API_KEY (prefix-mapping)."""
    assert get_required_api_key_env_var(SONNET_55) == "AZURE_AI_API_KEY"
    assert get_required_api_key_env_var(OPUS_55) == "AZURE_AI_API_KEY"


def test_foundry_55_models_have_display_names():
    """Picker toont een display-naam + omschrijving, niet het kale model-ID."""
    rendered = {mid: (name, desc) for mid, name, desc, _icon, _provider in _models_from_ids([SONNET_55, OPUS_55])}
    for mid in (SONNET_55, OPUS_55):
        name, desc = rendered[mid]
        assert name != mid.split("/")[-1], f"{mid} heeft geen display-naam"
        assert desc, f"{mid} heeft geen omschrijving"


def test_sonnet_55_reads_as_plain_language(zonder_willma):
    assert _models_from_ids([SONNET_55]) == [
        (SONNET_55, "Sonnet 5.5", "voor de meeste vragen", "sparkles", "Microsoft Azure AI Foundry")
    ]


def test_opus_55_names_its_provider_apart(zonder_willma):
    [(_mid, name, _desc, _icon, provider)] = _models_from_ids([OPUS_55])
    assert (name, provider) == ("Opus 5.5", "Microsoft Azure AI Foundry")


@pytest.mark.parametrize("mid", sorted(_KNOWN_NAMES))
def test_known_labels_carry_no_provider_jargon(mid):
    name, desc, _icon, _provider = _KNOWN_NAMES[mid]
    text = f"{name} {desc}".lower()
    assert [word for word in JARGON if word in text] == []


@pytest.mark.parametrize("mid", sorted(_KNOWN_NAMES))
def test_every_known_model_names_its_provider(mid, zonder_willma):
    expected = "SURF Willma" if mid in WILLMA_IDS else PROVIDER_BY_PREFIX[mid.split("/")[0]]
    assert _KNOWN_NAMES[mid][3] == expected
    assert model_provider(mid) == expected


@pytest.mark.parametrize(
    ("mid", "provider"),
    [
        ("anthropic/claude-nieuw", "Anthropic"),
        ("azure_ai/claude-nieuw", "Microsoft Azure AI Foundry"),
        ("openai/gpt-nieuw", "OpenAI"),
        ("mistral/large-latest", ""),
        ("zonder-prefix", ""),
    ],
)
def test_unknown_model_gets_provider_from_its_prefix_only(mid, provider, zonder_willma):
    """Geen verzonnen naam: het deel na de laatste '/' blijft de naam, zonder omschrijving."""
    assert _models_from_ids([mid]) == [(mid, mid.split("/")[-1], "", "cpu", provider)]


@pytest.mark.parametrize("mid", ["openai/nieuw-model", "openai/gpt-4o"])
def test_willma_key_sends_every_openai_model_to_willma(mid, met_willma):
    """Zoals agent/models.py:litellm_kwargs: met WILLMA_API_KEY gaat elk openai/-model naar Willma."""
    assert model_provider(mid) == "SURF Willma"


def test_willma_key_leaves_other_providers_alone(met_willma):
    assert model_provider(SONNET_55) == "Microsoft Azure AI Foundry"
    assert model_provider("anthropic/claude-nieuw") == "Anthropic"
