"""Een limiet op pogingen per sleutel in een glijdend venster.

Zonder `naam` telt de limiet in het geheugen van dit proces. Met een `naam` telt hij, waar de database de staat van
meerdere pods deelt (Postgres), in de tabel `rate_limit_hits`, zodat twee pods samen één limiet vormen en een herstart
niemand op nul zet (#984). Faalt de database, dan telt de limiet tijdelijk per pod: liever een ruimere limiet dan geen
inlog of chatbericht meer voor iedereen. Een vergrendelde SQLite-database is geen storing: die poging gaat kort
opnieuw (#1194).
"""

import logging
import sqlite3
import time

from core.pseudoniem import pseudoniem

logger = logging.getLogger(__name__)

_FOUTMELDING_PAUZE_S = 60  # de eerste databasefout per limiet staat in het log; daarna eens per minuut
# Na een vergrendelde database nog zo vaak opnieuw, na deze pauzes: samen hooguit 0,3 s extra op een inlog of bericht.
_HERKANSING_PAUZES_S = (0.05, 0.25)


def _vergrendeld(exc: Exception) -> bool:
    """Een voorbijgaande vergrendeling van SQLite ('database is locked' of 'busy'), geen database die weg is."""
    tekst = str(exc).lower()
    return isinstance(exc, sqlite3.OperationalError) and ("locked" in tekst or "busy" in tekst)


class RateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60, naam: str | None = None):
        self._max = max_attempts
        self._window = window_seconds
        self._naam = naam
        self._attempts: dict[str, list[float]] = {}
        self._laatste_opruiming = time.monotonic()
        self._laatste_db_opruiming = time.monotonic()
        self._laatste_foutmelding: dict[str, float] = {}  # per soort melding

    def _gedeelde_naam(self) -> str | None:
        """De naam van deze limiet als hij in de database telt; None als het geheugen telt."""
        if self._naam is None:
            return None
        from persistence import db

        return self._naam if db.deelt_staat() else None

    def _sleutel(self, key: str) -> str:
        """Alleen een HMAC met een servergeheim gaat de database in (#1117): gebruikersnaam of adres staan er niet
        leesbaar en ook niet terug te rekenen (een e-mailadres is te raden, een IPv4-adres telt hooguit 2^32 waarden)."""
        return pseudoniem("ratelimit", key)

    def _uit_database(self, naam: str, key: str, *, tel: bool) -> tuple[bool, int | None]:
        """(gelukt, wachttijd in s of None). Gelukt is False bij een databasefout: dan telt het geheugen."""
        from persistence import db

        try:
            wacht_ms = self._poging_in_database(naam, key, tel=tel)
        except Exception as exc:
            self._meld_fout("Limiet %s telt per pod: database niet bereikbaar (%s)", naam, exc)
            return False, None
        # Los van het tellen: faalt de opruiming, dan staat de poging al in de database en mag het geheugen haar niet
        # nog eens tellen (#1194).
        if tel and time.monotonic() - self._laatste_db_opruiming >= self._window:
            self._laatste_db_opruiming = time.monotonic()
            try:
                db.rate_limit_opruimen(naam)
            except Exception as exc:
                self._meld_fout("Limiet %s: opruimen van verlopen pogingen mislukt (%s)", naam, exc)
        return True, None if wacht_ms is None else max(1, -(-wacht_ms // 1000))

    def _poging_in_database(self, naam: str, key: str, *, tel: bool) -> int | None:
        """Eén poging in de database; na een vergrendelde SQLite-database een paar keer opnieuw (#1194). Dat is veilig:
        de mislukte transactie is teruggedraaid, de poging telde dus nog niet. Een andere fout gaat meteen door."""
        from persistence import db

        for pauze in _HERKANSING_PAUZES_S:
            try:
                return db.rate_limit_poging(naam, self._sleutel(key), self._max, self._window * 1000, tel=tel)
            except sqlite3.OperationalError as exc:
                if not _vergrendeld(exc):
                    raise
            time.sleep(pauze)
        return db.rate_limit_poging(naam, self._sleutel(key), self._max, self._window * 1000, tel=tel)

    def _meld_fout(self, bericht: str, naam: str, exc: Exception) -> None:
        """De eerste fout van elke soort staat in het log, daarna eens per minuut; alleen het soort fout, geen details."""
        nu = time.monotonic()
        if nu - self._laatste_foutmelding.get(bericht, float("-inf")) >= _FOUTMELDING_PAUZE_S:
            self._laatste_foutmelding[bericht] = nu
            logger.warning(bericht, naam, type(exc).__name__)

    def probeer(self, key: str) -> int | None:
        """Telt een poging mee en geeft None, of geeft na hoeveel seconden het weer mag. Eén ronde naar de database,
        dus vanuit async code via `asyncio.to_thread`."""
        if naam := self._gedeelde_naam():
            gelukt, wacht = self._uit_database(naam, key, tel=True)
            if gelukt:
                return wacht
        return None if self._geheugen_toestaan(key) else (self._geheugen_wacht(key) or 1)

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
        return self.probeer(key) is None

    def retry_after(self, key: str) -> int | None:
        if naam := self._gedeelde_naam():
            gelukt, wacht = self._uit_database(naam, key, tel=False)
            if gelukt:
                return wacht
        return self._geheugen_wacht(key)

    def _geheugen_toestaan(self, key: str) -> bool:
        self._ruim_verlopen_keys_op()
        recent = self._prune(key)
        if len(recent) >= self._max:
            return False
        recent.append(time.monotonic())
        self._attempts[key] = recent
        return True

    def _geheugen_wacht(self, key: str) -> int | None:
        recent = self._prune(key)
        if len(recent) < self._max:
            return None
        oldest = recent[0]
        return max(1, int(self._window - (time.monotonic() - oldest)) + 1)
