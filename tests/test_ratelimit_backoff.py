"""Backoff bij een rate limit: Retry-After volgen en vastleggen wat de provider meldde (#431)."""

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
