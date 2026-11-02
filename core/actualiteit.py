"""Hoe lang een opgehaalde bron als actueel geldt (#864, #873).

De datastore, de CBS-metadata en het instellingsregister bewaarden wat ze ophaalden tot de pod herstartte: een
revisie of een nieuwe periode bij de bron bleef onzichtbaar. Na `TTL` halen ze opnieuw op. De klok staat hier op één
plek, zodat een test hem kan verzetten in plaats van te wachten (`monkeypatch.setattr(actualiteit, "nu", ...)`).
"""

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

TTL = timedelta(hours=24)


def nu() -> datetime:
    """Het moment van nu, met tijdzone; de enige klok voor ophaalmomenten."""
    return datetime.now(UTC)


def verlopen(opgehaald_op: datetime) -> bool:
    """Is wat op `opgehaald_op` is opgehaald ouder dan de TTL?"""
    return nu() - opgehaald_op >= TTL


class Verversing:
    """Leegt caches zonder verloop (`lru_cache`) zodra hun inhoud ouder dan de TTL kan zijn.

    Eén moment voor alle caches samen: wat er ook in staat, het is na `actueel()` nooit ouder dan de TTL. De eerste
    aanroep leegt ze ook, want wat er vóór die aanroep in kwam, heeft geen bekend ophaalmoment.
    """

    def __init__(self, *legen: Callable[[], None]) -> None:
        self._legen = legen
        self._sinds: datetime | None = None
        self._slot = threading.Lock()

    def actueel(self) -> None:
        with self._slot:
            if self._sinds is not None and not verlopen(self._sinds):
                return
            for leeg in self._legen:
                leeg()
            self._sinds = nu()
