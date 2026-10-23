"""Hoeveel er tegelijk mag op één pod (#688): open chatverbindingen en lopende runs.

De berichtlimiet (core/rate_limit.py) telt verzoeken in de tijd, niet wat er tegelijk loopt. Een client kon
veel sockets openen en op elk een run starten; op één pod (#677) kost dat geheugen en CPU voor iedereen.
Alles hier leeft in het geheugen van het proces, net als de andere limieten.
"""

import asyncio
import contextlib
import threading
from collections import Counter
from collections.abc import AsyncGenerator, Generator

DRUK = "Het is nu erg druk. Probeer het over een minuut opnieuw."


class Druk(Exception):
    """Geen runplaats binnen de wachttijd. Eigen klasse, geen Gebruikersfout: core.errors laadt litellm, en de
    sandbox (en dus het retrievalscript) importeert deze module (tests/retrieval_baseline)."""

    def __init__(self) -> None:
        super().__init__(DRUK)


class Verbindingen:
    """Telt open verbindingen, per sleutel en in totaal. Een sleutel None telt alleen in het totaal."""

    def __init__(self, *, per_sleutel: int, totaal: int) -> None:
        self._per_sleutel = per_sleutel
        self._totaal = totaal
        self._open: Counter[str] = Counter()
        self._aantal = 0

    def open(self, sleutel: str | None) -> bool:
        """Neemt een plaats als er een vrij is; False betekent: weigeren, er is niets geteld."""
        if self._aantal >= self._totaal:
            return False
        if sleutel is not None and self._open[sleutel] >= self._per_sleutel:
            return False
        self._aantal += 1
        if sleutel is not None:
            self._open[sleutel] += 1
        return True

    def sluit(self, sleutel: str | None) -> None:
        self._aantal -= 1
        if sleutel is not None:
            self._open[sleutel] -= 1
            if self._open[sleutel] <= 0:
                del self._open[sleutel]

    @property
    def aantal(self) -> int:
        return self._aantal


class Runplaatsen:
    """Een wachtrij voor runs die het model aanroepen: hooguit `max_tegelijk`, de rest wacht `wacht_s` op een plaats."""

    def __init__(self, *, max_tegelijk: int, wacht_s: float) -> None:
        self._semafoor = asyncio.Semaphore(max_tegelijk)
        self._wacht_s = wacht_s

    @contextlib.asynccontextmanager
    async def plaats(self) -> AsyncGenerator[None]:
        """Druk als er binnen de wachttijd geen plaats vrijkomt; dan is er niets gestart."""
        try:
            await asyncio.wait_for(self._semafoor.acquire(), timeout=self._wacht_s)
        except TimeoutError:
            raise Druk from None
        try:
            yield
        finally:
            self._semafoor.release()


class Procesplaatsen:
    """Hetzelfde voor kindprocessen (de sandbox van run_analysis): die draaien in een thread, dus een threading-semafoor."""

    def __init__(self, *, max_tegelijk: int, wacht_s: float) -> None:
        self._semafoor = threading.BoundedSemaphore(max_tegelijk)
        self._wacht_s = wacht_s

    @contextlib.contextmanager
    def plaats(self) -> Generator[bool]:
        """Geeft True met een plaats, False als er binnen de wachttijd geen vrijkwam."""
        if not self._semafoor.acquire(timeout=self._wacht_s):
            yield False
            return
        try:
            yield True
        finally:
            self._semafoor.release()
