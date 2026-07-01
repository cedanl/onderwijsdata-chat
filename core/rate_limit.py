import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self._max = max_attempts
        self._window = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str) -> list[float]:
        cutoff = time.monotonic() - self._window
        recent = [t for t in self._attempts[key] if t > cutoff]
        self._attempts[key] = recent
        return recent

    def is_allowed(self, key: str) -> bool:
        recent = self._prune(key)
        if len(recent) >= self._max:
            return False
        self._attempts[key].append(time.monotonic())
        return True

    def retry_after(self, key: str) -> int | None:
        recent = self._prune(key)
        if len(recent) < self._max:
            return None
        oldest = recent[0]
        return max(1, int(self._window - (time.monotonic() - oldest)) + 1)
