import time

from core.rate_limit import RateLimiter


def test_allows_under_limit():
    rl = RateLimiter(max_attempts=3, window_seconds=60)
    assert rl.is_allowed("192.168.1.1") is True
    assert rl.is_allowed("192.168.1.1") is True
    assert rl.is_allowed("192.168.1.1") is True


def test_blocks_over_limit():
    rl = RateLimiter(max_attempts=3, window_seconds=60)
    for _ in range(3):
        rl.is_allowed("192.168.1.1")
    assert rl.is_allowed("192.168.1.1") is False


def test_different_keys_independent():
    rl = RateLimiter(max_attempts=2, window_seconds=60)
    rl.is_allowed("10.0.0.1")
    rl.is_allowed("10.0.0.1")
    assert rl.is_allowed("10.0.0.1") is False
    assert rl.is_allowed("10.0.0.2") is True


def test_window_expires(monkeypatch):
    fake_time = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])

    rl = RateLimiter(max_attempts=2, window_seconds=10)
    rl.is_allowed("ip1")
    rl.is_allowed("ip1")
    assert rl.is_allowed("ip1") is False

    fake_time[0] = 1011.0
    assert rl.is_allowed("ip1") is True


def test_retry_after_returns_seconds():
    rl = RateLimiter(max_attempts=1, window_seconds=30)
    rl.is_allowed("ip1")
    assert rl.is_allowed("ip1") is False
    retry = rl.retry_after("ip1")
    assert retry is not None
    assert 0 < retry <= 30


def test_retry_after_none_when_allowed():
    rl = RateLimiter(max_attempts=5, window_seconds=60)
    assert rl.retry_after("ip1") is None


def test_retry_after_maakt_geen_bucket_voor_onbekende_key():
    rl = RateLimiter(max_attempts=5, window_seconds=60)
    assert rl.retry_after("onbekend") is None
    assert rl._attempts == {}


def test_leeg_geworden_bucket_wordt_verwijderd(monkeypatch):
    fake_time = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])
    rl = RateLimiter(max_attempts=2, window_seconds=10)
    rl.is_allowed("ip1")
    assert "ip1" in rl._attempts

    fake_time[0] = 1011.0
    assert rl.retry_after("ip1") is None
    assert "ip1" not in rl._attempts


def test_verlopen_keys_die_nooit_terugkomen_worden_opgeruimd(monkeypatch):
    """Eenmalige keys (zoals verzonnen gebruikersnamen) mogen het geheugen niet vullen."""
    fake_time = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])
    rl = RateLimiter(max_attempts=2, window_seconds=10)
    for i in range(100):
        rl.is_allowed(f"gast{i}")
    assert len(rl._attempts) == 100

    fake_time[0] = 1011.0
    rl.is_allowed("nieuw")
    assert list(rl._attempts) == ["nieuw"]


def test_limiet_blijft_gelden_na_opruiming(monkeypatch):
    fake_time = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])
    rl = RateLimiter(max_attempts=2, window_seconds=10)
    rl.is_allowed("ip1")
    fake_time[0] = 1011.0
    assert rl.is_allowed("ip1") is True
    assert rl.is_allowed("ip1") is True
    assert rl.is_allowed("ip1") is False
    assert rl.retry_after("ip1") is not None
