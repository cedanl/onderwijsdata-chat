"""Hoe lang een opgehaalde bron als actueel geldt (#864, #873).

De datastore, de CBS-metadata en het instellingsregister bewaarden wat ze ophaalden tot de pod herstartte: een
revisie of een nieuwe periode bij de bron bleef onzichtbaar. Na `TTL` halen ze opnieuw op. De klok staat hier op één
plek, zodat een test hem kan verzetten in plaats van te wachten (`monkeypatch.setattr(actualiteit, "nu", ...)`).

`Voorwaardelijk` vraagt een bestand na de TTL opnieuw met If-Modified-Since (#935): een jaarlijkse editie komt dan als
304 terug in plaats van opnieuw megabytes.
"""

import functools
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

import httpx

from core import brongebruik

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
    - laadt de eerste aanroep na de TTL opnieuw;
    - meldt elke aanroep, ook een cachetreffer, de bestanden die de lading meldde (`brongebruik`, #904).

    `cache_clear` heet zoals bij `lru_cache`, zodat de tests de caches van een module op dezelfde manier legen.
    """

    def __init__(self, laad: Callable[..., T]) -> None:
        functools.update_wrapper(self, laad)
        self._laad = laad
        self._bewaard: dict[tuple, tuple[T, datetime, tuple[Mapping, ...]]] = {}
        self._slot = threading.Lock()

    def __call__(self, *args) -> T:
        with self._slot:
            bewaard = self._bewaard.get(args)
            if bewaard is None or verlopen(bewaard[1]):
                with brongebruik.verzamel() as gemeld:
                    waarde = self._laad(*args)
                bewaard = (waarde, nu(), tuple(gemeld))
                self._bewaard[args] = bewaard
        brongebruik.meld(*bewaard[2])
        return bewaard[0]

    def cache_clear(self) -> None:
        self._bewaard.clear()


class Voorwaardelijk:
    """Een haler die een bestand opnieuw vraagt met If-Modified-Since (#935).

    Een bron die één keer per jaar een editie publiceert (DUO's verantwoording uit XBRL, 5 MB) hoeft na de TTL niet
    alles opnieuw te sturen: met de Last-Modified van de vorige download antwoordt de server 304, en dan blijft de
    bewaarde inhoud geldig. Zonder Last-Modified (een pagina die de server elke keer opbouwt) is het een gewone GET.
    Een fout gaat naar de aanroeper; de bewaarde inhoud blijft dan staan voor de volgende poging.
    """

    def __init__(self, headers: Mapping[str, str] | None = None, timeout_s: float = 60) -> None:
        self._headers = dict(headers or {})
        self._timeout_s = timeout_s
        self._bewaard: dict[str, tuple[bytes, str, str]] = {}  # url → (inhoud, content-type, Last-Modified)
        self._slot = threading.Lock()

    def __call__(self, url: str) -> tuple[bytes, str]:
        """(inhoud, content-type) van `url`: de bewaarde inhoud bij 304, anders de nieuwe."""
        with self._slot:
            bewaard = self._bewaard.get(url)
        headers = {**self._headers, **({"If-Modified-Since": bewaard[2]} if bewaard else {})}
        antwoord = httpx.get(url, headers=headers, timeout=self._timeout_s, follow_redirects=True)
        if antwoord.status_code == 304 and bewaard:
            return bewaard[0], bewaard[1]
        antwoord.raise_for_status()
        soort = antwoord.headers.get("content-type", "")
        if gewijzigd := antwoord.headers.get("last-modified"):
            with self._slot:
                self._bewaard[url] = (antwoord.content, soort, gewijzigd)
        return antwoord.content, soort

    def cache_clear(self) -> None:
        with self._slot:
            self._bewaard.clear()
