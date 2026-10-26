"""Wat de gebruiker van een fout ziet (#404)."""

import logging

import litellm

from core.errors import Gebruikersfout, error_event


def _tekst_boven_debug(caplog, tekst: str) -> list[str]:
    """Regels op WARNING en hoger die de fouttekst noemen; de tekst hoort alleen op DEBUG (#502)."""
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.WARNING and (r.exc_info or tekst in r.getMessage())
    ]


def test_interne_fout_toont_geen_exceptietekst(caplog):
    with caplog.at_level("DEBUG"):
        event = error_event(ValueError("zip() argument 3 is shorter than arguments 1-2"))
    assert "zip()" not in event["message"]
    assert "fout-ID" in event["message"]
    assert event["modelafhankelijk"] is False
    fout_id = event["message"].split("fout-ID ")[1][:8]
    assert fout_id in caplog.text and "zip()" in caplog.text
    assert not _tekst_boven_debug(caplog, "zip()")


def test_modelfout_biedt_een_ander_model_aan():
    exc = litellm.RateLimitError("te veel", llm_provider="azure_ai", model="claude-sonnet-5-5")
    event = error_event(exc)
    assert event["modelafhankelijk"] is True
    assert "Te veel verzoeken" in event["message"]


def test_timeout_is_modelafhankelijk():
    assert error_event(TimeoutError())["modelafhankelijk"] is True


def test_modelfout_zonder_vaste_tekst_lekt_geen_exceptietekst(caplog):
    """#503: ook een API-fout (BadRequestError) kan interne details bevatten."""
    exc = litellm.BadRequestError(
        "geheim intern detail /app/data/cache/x.parquet", llm_provider="azure_ai", model="claude-sonnet-5-5"
    )
    with caplog.at_level("DEBUG"):
        event = error_event(exc)
    assert "parquet" not in event["message"] and "geheim" not in event["message"]
    assert "fout-ID" in event["message"]
    assert event["modelafhankelijk"] is True
    assert "parquet" in caplog.text
    assert not _tekst_boven_debug(caplog, "parquet")


def test_gebruikersfout_bereikt_de_gebruiker_letterlijk():
    melding = "Geen datasets geladen. Stel eerst een vraag waarvoor data wordt opgehaald."
    event = error_event(Gebruikersfout(melding))
    assert melding in event["message"]


def _beschikbaar(exc, caplog):
    with caplog.at_level("ERROR"):
        return error_event(exc)


def test_sleutel_model_en_verbinding_geven_een_fout_id_en_geen_verwijzing_naar_env(caplog):
    """#712: een gebruiker heeft geen `.env`, en zijn eigen internet is het niet."""
    for exc in (
        litellm.AuthenticationError("geheim", llm_provider="azure_ai", model="m"),
        litellm.NotFoundError("geheim", llm_provider="azure_ai", model="m"),
        litellm.APIConnectionError("geheim", llm_provider="azure_ai", model="m"),
    ):
        event = _beschikbaar(exc, caplog)

        assert "fout-ID" in event["message"] and ".env" not in event["message"]
        assert "internetverbinding" not in event["message"] and "geheim" not in event["message"]
        assert event["modelafhankelijk"] is True


def test_de_beheerder_vindt_de_oorzaak_onder_het_fout_id(caplog):
    event = _beschikbaar(litellm.AuthenticationError("geheim", llm_provider="azure_ai", model="m"), caplog)

    fout_id = event["message"].split("fout-ID ")[1][:8]
    regel = next(r.getMessage() for r in caplog.records if fout_id in r.getMessage())
    assert "sleutel ontbreekt of is ongeldig" in regel and "AuthenticationError" in regel
    assert "geheim" not in regel


def test_een_limiet_blijft_een_vaste_tekst_zonder_fout_id():
    event = error_event(litellm.RateLimitError("te veel", llm_provider="azure_ai", model="m"))

    assert "fout-ID" not in event["message"]
