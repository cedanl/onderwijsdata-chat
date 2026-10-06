"""Foundry 5-5 modellen in de picker: display-namen + provider-key."""

from core.config import _models_from_ids, get_required_api_key_env_var

SONNET_55 = "azure_ai/claude-sonnet-5-5"
OPUS_55 = "azure_ai/claude-opus-5-5"


def test_foundry_55_models_require_azure_ai_key():
    """Beide 5-5-modellen vallen onder AZURE_AI_API_KEY (prefix-mapping)."""
    assert get_required_api_key_env_var(SONNET_55) == "AZURE_AI_API_KEY"
    assert get_required_api_key_env_var(OPUS_55) == "AZURE_AI_API_KEY"


def test_foundry_55_models_have_display_names():
    """Picker toont een display-naam + omschrijving, niet het kale model-ID."""
    rendered = {mid: (name, desc, icon) for mid, name, desc, icon in _models_from_ids([SONNET_55, OPUS_55])}
    for mid in (SONNET_55, OPUS_55):
        name, desc, _icon = rendered[mid]
        assert name != mid.split("/")[-1], f"{mid} heeft geen display-naam"
        assert desc, f"{mid} heeft geen omschrijving"
