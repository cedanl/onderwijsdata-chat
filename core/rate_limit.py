import time


class RateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self._max = max_attempts
        self._window = window_seconds
        self._attempts: dict[str, list[float]] = {}
        self._laatste_opruiming = time.monotonic()

    def _prune(self, key: str) -> list[float]:
        """Geeft de pogingen binnen het venster; een leeg bucket verdwijnt uit het geheugen."""
        cutoff = time.monotonic() - self._window
        recent = [t for t in self._attempts.get(key, ()) if t > cutoff]
        if recent:
            self._attempts[key] = recent
        else:
            self._attempts.pop(key, None)
        return recent

    def _ruim_verlopen_keys_op(self) -> None:
        """Eens per venster alle verlopen buckets weg: een key die nooit meer terugkomt
        (bijv. een eenmalige gebruikersnaam) wordt anders nooit opgeschoond."""
        nu = time.monotonic()
        if nu - self._laatste_opruiming < self._window:
            return
        self._laatste_opruiming = nu
        for key in list(self._attempts):
            self._prune(key)

    def is_allowed(self, key: str) -> bool:
        self._ruim_verlopen_keys_op()
        recent = self._prune(key)
        if len(recent) >= self._max:
            return False
        recent.append(time.monotonic())
        self._attempts[key] = recent
        return True

    def retry_after(self, key: str) -> int | None:
        recent = self._prune(key)
        if len(recent) < self._max:
            return None
        oldest = recent[0]
        return max(1, int(self._window - (time.monotonic() - oldest)) + 1)
