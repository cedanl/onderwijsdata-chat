"""Een dag- en maandbudget aan tokens per gebruiker (#678, audit S24/F-08).

Het tokengebruik per run stond al in het log (`TOKENS`, agent/loop.py); dezelfde run telt nu ook mee in de database
(`tokengebruik`), per gebruiker en per dag. Vóór een modelrun (vraag, verduidelijking, rapport) toetst
`routes/chat.py` het budget; erboven komt er een melding en geen modelaanroep.

Het budget is in invoertoken-equivalenten, gewogen naar de verhouding van de tarieven en niet naar een prijs: nieuwe
invoer x1, uit de cache gelezen x0,1, cache geschreven x1,25, uitvoer x5. `invoer` is het totaal, de cache inbegrepen
(agent/stream.py). Zo telt een vraag die vooral de gecachete systeemprompt leest (#1027) niet als een dure vraag.

De gebruiker van een run komt uit een ContextVar die de WebSocket bij het openen zet (zoals `ho_markers.beurtvraag`):
taken en `asyncio.to_thread` erven hem. Gast (zonder login) heeft geen budget; daar gelden de berichtlimiet en de
verbindingsgrens. Faalt de database, dan gaat het chatten door met een WARNING: liever even geen budget dan geen chat
(zoals core/rate_limit.py). De dag is UTC.
"""

import datetime as dt
import hashlib
import logging
import time
from contextvars import ContextVar

from agent.stream import Tokens
from core.config import TOKENBUDGET_DAG, TOKENBUDGET_MAAND

logger = logging.getLogger(__name__)

GEWICHT_CACHE_GELEZEN = 0.1
GEWICHT_CACHE_GESCHREVEN = 1.25
GEWICHT_UITVOER = 5
GAST = "gast"
_FOUTMELDING_PAUZE_S = 60

_gebruiker: ContextVar[str | None] = ContextVar("tokenbudget_gebruiker", default=None)
_laatste_foutmelding = float("-inf")

MELDING_DAG = (
    "Je hebt het budget voor vandaag bereikt. Morgen kun je weer vragen stellen; je gesprekken en rapporten blijven "
    "gewoon staan."
)
MELDING_MAAND = (
    "Je hebt het budget voor deze maand bereikt. Vanaf {volgende} kun je weer vragen stellen; je gesprekken en "
    "rapporten blijven gewoon staan."
)
_MAANDEN = (
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
)


def eenheden(t: Tokens) -> int:
    """De kosten van een run in invoertoken-equivalenten."""
    nieuw = max(0, t.invoer - t.cache_gelezen - t.cache_geschreven)
    return round(
        nieuw
        + t.cache_gelezen * GEWICHT_CACHE_GELEZEN
        + t.cache_geschreven * GEWICHT_CACHE_GESCHREVEN
        + t.uitvoer * GEWICHT_UITVOER
    )


def zet_gebruiker(gebruiker: str | None) -> None:
    """De gebruiker van deze verbinding; elke run die hierna in deze context start, telt voor hem."""
    _gebruiker.set(gebruiker if gebruiker and gebruiker != GAST else None)


def _vandaag() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def _sleutel(gebruiker: str) -> str:
    """Alleen de hash gaat de database in, zoals bij de limieten."""
    return hashlib.sha256(gebruiker.encode()).hexdigest()


def _aan() -> bool:
    return TOKENBUDGET_DAG > 0 or TOKENBUDGET_MAAND > 0


def _databasefout(exc: Exception) -> None:
    global _laatste_foutmelding
    nu = time.monotonic()
    if nu - _laatste_foutmelding >= _FOUTMELDING_PAUZE_S:
        _laatste_foutmelding = nu
        logger.warning("TOKENBUDGET niet beschikbaar: database niet bereikbaar (%s)", type(exc).__name__)


def boek(t: Tokens) -> None:
    """Tel een run mee voor de gebruiker van deze context. Synchroon (één databaseronde): vanuit async code via
    `asyncio.to_thread`."""
    from persistence import db

    gebruiker = _gebruiker.get()
    if not gebruiker or not _aan() or not (n := eenheden(t)):
        return
    try:
        db.tokengebruik_boek(_sleutel(gebruiker), _vandaag().isoformat(), n)
    except Exception as exc:
        _databasefout(exc)


def gebruik(gebruiker: str) -> tuple[int, int]:
    """(vandaag, deze maand) in invoertoken-equivalenten."""
    from persistence import db

    dag = _vandaag()
    return db.tokengebruik_stand(_sleutel(gebruiker), dag.isoformat(), dag.replace(day=1).isoformat())


def _volgende_maand(dag: dt.date) -> str:
    eerste = (dag.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return f"1 {_MAANDEN[eerste.month - 1]}"


def over_budget(gebruiker: str | None) -> str | None:
    """De melding voor de gebruiker als zijn budget op is; None als er nog ruimte is (of geen budget geldt)."""
    if not gebruiker or gebruiker == GAST or not _aan():
        return None
    try:
        vandaag, maand = gebruik(gebruiker)
    except Exception as exc:
        _databasefout(exc)
        return None
    if TOKENBUDGET_MAAND > 0 and maand >= TOKENBUDGET_MAAND:
        return MELDING_MAAND.format(volgende=_volgende_maand(_vandaag()))
    if TOKENBUDGET_DAG > 0 and vandaag >= TOKENBUDGET_DAG:
        return MELDING_DAG
    return None
