"""Hoe lang een opgehaalde bron als actueel geldt (#864, #873).

De datastore, de CBS-metadata en het instellingsregister bewaarden wat ze ophaalden tot de pod herstartte: een
revisie of een nieuwe periode bij de bron bleef onzichtbaar. Na `TTL` halen ze opnieuw op. De klok staat hier op één
plek, zodat een test hem kan verzetten in plaats van te wachten (`monkeypatch.setattr(actualiteit, "nu", ...)`).
"""

import functools
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

T = TypeVar("T")

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


class Lading(Generic[T]):
    """Wat een lader ophaalt, per argumenten bewaard tot de TTL; als decorator om een lader (#901).

    Voor de dashboards stond er een `lru_cache` om, en daarmee drie gaten: niets verliep tot de pod herstartte, een
    lader die zijn fout zelf afving en `{}` gaf, hield die `{}` voorgoed, en vijf eindpunten tegelijk laadden dezelfde
    DUO-bestanden vijf keer. Hier:

    - komt alleen een geslaagde lading erin: een fout gaat naar de aanroeper, de volgende aanroep probeert opnieuw;
    - laden gelijktijdige aanroepen één keer: de rest wacht op die lading en krijgt haar uitkomst;
    - laadt de eerste aanroep na de TTL opnieuw.

    `cache_clear` heet zoals bij `lru_cache`, zodat de tests de caches van een module op dezelfde manier legen.
    """

    def __init__(self, laad: Callable[..., T]) -> None:
        functools.update_wrapper(self, laad)
        self._laad = laad
        self._bewaard: dict[tuple, tuple[T, datetime]] = {}
        self._slot = threading.Lock()

    def __call__(self, *args) -> T:
        with self._slot:
            bewaard = self._bewaard.get(args)
            if bewaard is not None and not verlopen(bewaard[1]):
                return bewaard[0]
            waarde = self._laad(*args)
            self._bewaard[args] = (waarde, nu())
            return waarde

    def cache_clear(self) -> None:
        self._bewaard.clear()
