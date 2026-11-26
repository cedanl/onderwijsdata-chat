"""De instelling "Geavanceerd" per account (#1269): extra mogelijkheden voor wie de analyse zelf wil zien en bijsturen.

Geavanceerd voegt alleen iets toe (de code per stap, de technische key van een getal, de CSV-downloads en de modelkeuze);
het zet nooit een beschermende functie uit (docs/kwaliteit-en-veiligheid.md). De gebruiker kiest het zelf; de waarde
komt alleen uit de tabel `geavanceerd` (persistence/db.py), nooit uit een SRAM-attribuut, de instelling of de functie
in het profiel, en ook niet uit wat de client in `settings` meestuurt (core/profiel.py laat die sleutel weg).

Eén uitzondering op "de gebruiker kiest": de pilotlijst `GEAVANCEERD_PILOT` zet haar aan bij de eerste login van een
account dat nog geen keuze heeft. Daarna beslist de gebruiker; een rij met "uit" blijft staan, dus de lijst zet een
uitgezette instelling nooit terug. Zonder login (iedereen is de gedeelde `gast`) bewaart de server niets: de browser
houdt de keuze dan zelf, standaard uit.

Elke functie hier gaat naar de database: vanuit async code via asyncio.to_thread (#508).
"""

import time

from core import config
from persistence import db


def lees(gebruiker: str) -> bool:
    """Staat Geavanceerd aan voor dit account? Zonder bewaarde keuze: uit."""
    return db.geavanceerd_lees(db.geavanceerd_sleutel(gebruiker)) is True


def zet(gebruiker: str, aan: bool) -> bool:
    """Bewaar de keuze van de gebruiker zelf en geef haar terug."""
    db.geavanceerd_zet(db.geavanceerd_sleutel(gebruiker), aan, time.time())
    return aan


def bij_login(gebruiker: str) -> bool:
    """Na een geslaagde login: een pilotaccount zonder bewaarde keuze krijgt Geavanceerd aan. True als dat nu gebeurde.

    Alleen de accountnaam telt, precies zoals in `GEAVANCEERD_PILOT`; een account buiten de lijst krijgt geen rij.
    """
    if gebruiker not in config.GEAVANCEERD_PILOT:
        return False
    return db.geavanceerd_zet_als_nieuw(db.geavanceerd_sleutel(gebruiker), True, time.time())
