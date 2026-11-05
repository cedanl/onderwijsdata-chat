"""Een idempotente GET naar CBS, DUO of RIO opnieuw proberen na een tijdelijke fout (#867).

Het bronpakket `onderwijsbronnen` roept `httpx.get` per functie aan, zonder sessie of transport om
een retry in te hangen. Daarom zit de herhaling hier, om de aanroep van de chat heen: `haal_op_met_retry("CBS",
lambda: data(...))`. Zo blijven de pakketten ongewijzigd, en kiest elk aanroeppunt zelf of zijn aanroep een
herhaling waard is.

Opnieuw proberen gebeurt alleen bij een fout die een seconde later anders kan uitvallen: HTTP 5xx, HTTP 429 en een
verbindingsfout (`httpx.TransportError`: weigering, reset, timeout). Een andere 4xx zegt dat de aanvraag zelf niet
klopt en komt meteen terug. Alleen een GET wordt herhaald; de methode staat in de fout zelf, dus een aanroeppunt
kan dat niet per vergissing omzeilen.

Hooguit twee herhalingen, met exponentiële wachttijd en jitter, en geen nieuwe poging meer als de wachttijd de tijd
sinds de eerste poging boven het budget zou brengen. Het budget (30 s) is de kortste timeout van de pakketten zelf:
een snelle 503 wordt herhaald, een aanroep die al tegen zijn timeout aanliep niet, zodat de tool niet langer
blijft hangen dan één trage aanroep al deed. Een fout die blijft, komt als dezelfde exception terug: de foutmelding
aan het model (`fouten.bronfout`) verandert niet.

Een structurele 500 blijft een 500. CBS antwoordt op een `$filter` met een haakjesgroep `(A or B) and (X and Y)`
met HTTP 500 (#561): die aanvraag gaat twee keer opnieuw, staat twee keer als `BRON_RETRY` in het log, en geeft
daarna dezelfde serverfout als zonder herhaling (tests/test_bronretry.py).
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class Beleid:
    """Hoe vaak en hoe lang; klok, slaap en toeval zijn injecteerbaar voor de tests."""

    herhalingen: int = 2
    basis_s: float = 0.5  # eerste wachttijd 0,5-1 s, tweede 1-2 s
    budget_s: float = 30.0
    slaap: Callable[[float], None] = field(default=time.sleep, repr=False)
    klok: Callable[[], float] = field(default=time.monotonic, repr=False)
    toeval: Callable[[], float] = field(default=random.random, repr=False)

    def wachttijd(self, poging: int, e: Exception) -> float:
        """De wachttijd vóór herhaling `poging` (0-based): Retry-After van een 429, anders backoff met jitter."""
        if (na := _retry_after(e)) is not None:
            return na
        return self.basis_s * 2**poging * (1 + self.toeval())


STANDAARD = Beleid()


def _retry_after(e: Exception) -> float | None:
    if not isinstance(e, httpx.HTTPStatusError) or e.response.status_code != 429:
        return None
    try:
        return max(0.0, float(e.response.headers.get("Retry-After", "")))
    except ValueError:
        return None


def _methode(e: httpx.HTTPError) -> str | None:
    try:
        return e.request.method
    except RuntimeError:  # httpx zet geen request bij een fout buiten een aanvraag
        return None


def herhaalbaar(e: Exception) -> str | None:
    """De reden om opnieuw te proberen (`HTTP 503`, `ConnectError`); None als de fout blijvend is."""
    if not isinstance(e, httpx.HTTPError) or _methode(e) != "GET":
        return None
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        return f"HTTP {status}" if status >= 500 or status == 429 else None
    if isinstance(e, httpx.TransportError):
        return type(e).__name__
    return None


def haal_op_met_retry(bron: str, haal: Callable[[], T], beleid: Beleid | None = None) -> T:
    """`haal()`, en bij een tijdelijke fout nog hooguit `beleid.herhalingen` keer binnen het budget.

    `haal` moet een idempotente GET zijn (of een reeks GETs, zoals een gepagineerde CBS-aanroep). Een fout die
    blijft of buiten het budget valt, gaat ongewijzigd naar de aanroeper. Het log noemt bron, poging en reden,
    geen URL: die citeert de codes die het model koos (#502).
    """
    beleid = beleid or STANDAARD
    start = beleid.klok()
    poging = 0
    while True:
        try:
            return haal()
        except Exception as e:
            reden = herhaalbaar(e)
            if reden is None or poging >= beleid.herhalingen:
                raise
            wacht = beleid.wachttijd(poging, e)
            if beleid.klok() - start + wacht > beleid.budget_s:
                raise
            poging += 1
            logger.warning(
                "BRON_RETRY bron=%s poging=%d/%d reden=%s wacht_s=%.1f",
                bron,
                poging,
                beleid.herhalingen,
                reden,
                wacht,
            )
            beleid.slaap(wacht)
