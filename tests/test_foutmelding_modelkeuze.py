"""De foutmelding in de chat noemt een ander model alleen als de gebruiker er een kan kiezen (#1167).

Op test en playground staat één model in `AVAILABLE_MODELS`: dan is er geen picker en geen ander model.
"""

import asyncio

import litellm
import pytest

from core import config
from routes import chat

USERNAME = "foutmelding-test"


async def _modelfout(messages, session, emit, stop_event, model=None):
    raise litellm.AuthenticationError("geheim", llm_provider="azure_ai", model="m")


def _melding(monkeypatch, aanbod: str | None) -> str:
    monkeypatch.setattr(config, "_AVAILABLE_MODELS_RAW", aanbod)
    monkeypatch.setattr(config, "_USER_MODELS", {})
    monkeypatch.setattr(chat, "agent_run", _modelfout)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(chat._process_message("vraag", chat._new_session(username=USERNAME), emit, None))
    [fout] = [e for e in events if e["type"] == "error"]
    return fout["message"]


@pytest.mark.parametrize("aanbod", [None, "azure_ai/een"])
def test_zonder_keuze_staat_er_geen_ander_model_in_de_melding(monkeypatch, aanbod):
    assert "ander model" not in _melding(monkeypatch, aanbod)


def test_met_twee_modellen_blijft_de_suggestie_staan(monkeypatch):
    assert "ander model" in _melding(monkeypatch, "azure_ai/een,azure_ai/twee")
