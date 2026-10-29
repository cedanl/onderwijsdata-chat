"""Backoff bij een rate limit: Retry-After volgen en vastleggen wat de provider meldde (#431).

Een time-out van de provider (`litellm.Timeout`) krijgt dezelfde backoff als een verbroken verbinding (#799).
"""

import asyncio
import logging

import litellm
import pytest

from agent import ratelimit


def _fout(headers=None):
    return litellm.RateLimitError("te veel", llm_provider="openai", model="m", headers=headers)


@pytest.fixture
def geen_slaap(monkeypatch):
    wachttijden: list[float] = []

    async def slaap(sec):
        wachttijden.append(sec)

    monkeypatch.setattr(ratelimit.asyncio, "sleep", slaap)
    return wachttijden


async def _niets(_event):
    return None


def _draai():
    return asyncio.run(ratelimit.acompletion_with_backoff(_niets))


def _provider(monkeypatch, fouten):
    pogingen = iter(fouten)

    async def acompletion(**_):
        fout = next(pogingen)
        if fout:
            raise fout
        return "ok"

    monkeypatch.setattr(ratelimit.litellm, "acompletion", acompletion)


def test_retry_after_van_de_provider_gaat_voor(monkeypatch, geen_slaap):
    _provider(monkeypatch, [_fout({"Retry-After": "7"}), None])
    assert _draai() == "ok"
    assert geen_slaap == [7.0]


def test_zonder_retry_after_exponentieel_en_begrensd(monkeypatch, geen_slaap):
    _provider(monkeypatch, [_fout(), _fout({"retry-after": "600"}), None])
    _draai()
    assert geen_slaap == [2.0, ratelimit._MAX_DELAY]


def test_elke_rate_limit_wordt_gelogd_met_providergegevens(monkeypatch, geen_slaap, caplog):
    _provider(monkeypatch, [_fout({"retry-after": "3"})] * ratelimit._MAX_RETRIES)
    with caplog.at_level(logging.WARNING, logger=ratelimit.__name__), pytest.raises(litellm.RateLimitError):
        _draai()

    regels = [r.getMessage() for r in caplog.records]
    assert len(regels) == ratelimit._MAX_RETRIES
    assert all("provider=openai" in r and "retry_after=3.0" in r for r in regels)
    assert "geen nieuwe poging" in regels[-1]


def _timeout():
    return litellm.Timeout("traag", model="m", llm_provider="azure_ai")


def test_een_time_out_van_de_provider_wordt_herhaald_met_een_toast(monkeypatch, geen_slaap):
    """#799: litellm.Timeout erft niet van TimeoutError of litellm.APIConnectionError, en ging zo meteen door."""
    _provider(monkeypatch, [_timeout(), None])
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    assert asyncio.run(ratelimit.acompletion_with_backoff(emit)) == "ok"
    assert geen_slaap == [2.0]
    assert [e["message"] for e in events if e["type"] == "toast"] == ["Model antwoordt traag, nieuwe poging over 2s…"]


def test_na_de_laatste_time_out_een_errorregel_en_de_fout_naar_de_aanroeper(monkeypatch, geen_slaap, caplog):
    _provider(monkeypatch, [_timeout()] * ratelimit._MAX_RETRIES)
    with caplog.at_level(logging.WARNING, logger=ratelimit.__name__), pytest.raises(litellm.Timeout):
        _draai()

    assert len(geen_slaap) == ratelimit._MAX_RETRIES - 1
    fouten = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(fouten) == 1 and f"Model timeout na {ratelimit._MAX_RETRIES} pogingen" in fouten[0].getMessage()


def test_een_andere_fout_wordt_niet_herhaald(monkeypatch, geen_slaap):
    _provider(monkeypatch, [litellm.BadRequestError("fout", model="m", llm_provider="openai"), None])
    with pytest.raises(litellm.BadRequestError):
        _draai()
    assert geen_slaap == []
