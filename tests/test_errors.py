"""Wat de gebruiker van een fout ziet (#404)."""

import litellm

from core.errors import error_event


def test_interne_fout_toont_geen_exceptietekst(caplog):
    with caplog.at_level("ERROR"):
        event = error_event(ValueError("zip() argument 3 is shorter than arguments 1-2"))
    assert "zip()" not in event["message"]
    assert "fout-ID" in event["message"]
    assert event["modelafhankelijk"] is False
    fout_id = event["message"].split("fout-ID ")[1][:8]
    assert fout_id in caplog.text and "zip()" in caplog.text


def test_modelfout_biedt_een_ander_model_aan():
    exc = litellm.RateLimitError("te veel", llm_provider="azure_ai", model="claude-sonnet-5-5")
    event = error_event(exc)
    assert event["modelafhankelijk"] is True
    assert "Te veel verzoeken" in event["message"]


def test_timeout_is_modelafhankelijk():
    assert error_event(TimeoutError())["modelafhankelijk"] is True
