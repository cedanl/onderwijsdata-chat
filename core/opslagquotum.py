"""Een opslagquotum per gebruiker voor gesprekken en werkboeken (#682, S24).

Een verzoek heeft al een grens (MAX_REQUEST_BYTES, core/verzoeklimiet.py); per gebruiker was er geen, zodat één account
de database kon blijven vullen. Vóór het bewaren telt de route wat de gebruiker al heeft: het aantal gesprekken, het
aantal werkboeken (rapporten en dashboards) en hun samen bewaarde grootte. Een nieuw item boven een aantal, of een
grootte boven de ruimte, krijgt een melding; wat er al staat, blijft. Een bestaand item bijwerken telt alleen het
verschil in grootte, en mag dus ook als het aantal al vol is.

De grootte is die van de bewaarde tekst (JSON en HTML), zoals de database haar telt. Twee pods die tegelijk voor
dezelfde gebruiker bewaren, kunnen samen net over de grens gaan: dat is een zachte grens, geen boekhouding. Zonder login
(`gast`, alleen lokaal) geldt geen quotum.
"""

import json

from core.auth import FALLBACK_USER
from core.config import MAX_GESPREKKEN_PER_GEBRUIKER, MAX_OPSLAG_PER_GEBRUIKER_MB, MAX_WERKBOEKEN_PER_GEBRUIKER

MAX_GESPREKKEN = MAX_GESPREKKEN_PER_GEBRUIKER
MAX_WERKBOEKEN = MAX_WERKBOEKEN_PER_GEBRUIKER
MAX_OPSLAG_BYTES = MAX_OPSLAG_PER_GEBRUIKER_MB * 1024 * 1024

STATUS = 507  # Insufficient Storage: opnieuw proberen helpt pas na het opruimen
_OPRUIMEN = "Verwijder oude gesprekken of rapporten om weer te kunnen bewaren; wat er al staat, blijft bewaard."
MELDING_GESPREKKEN = "Je hebt het maximum van {n} bewaarde gesprekken bereikt. " + _OPRUIMEN
MELDING_WERKBOEKEN = "Je hebt het maximum van {n} bewaarde rapporten en dashboards bereikt. " + _OPRUIMEN
MELDING_RUIMTE = "Je bewaarde gesprekken en rapporten gebruiken samen al alle ruimte ({mb} MB). " + _OPRUIMEN


def grootte_gesprek(messages: list) -> int:
    return len(json.dumps(messages))


def grootte_werkboek(body: dict) -> int:
    """Zoals persistence/db.py het werkboek bewaart: messages, figures en dashboardSpec als JSON, de HTML als tekst."""
    delen = [json.dumps(body[veld]) for veld in ("messages", "figures", "dashboardSpec") if body.get(veld) is not None]
    return sum(map(len, delen)) + len(body.get("htmlContent") or "")


def toets(username: str, soort: str, item_id: str, nieuw: int) -> str | None:
    """De melding als het bewaren van `item_id` (`soort` "gesprek" of "werkboek", `nieuw` tekens) het quotum van
    `username` overschrijdt; None als het past."""
    from persistence import db

    if not username or username == FALLBACK_USER:
        return None
    stand = db.opslagstand(username, soort, item_id)
    bestaat = stand["item"] is not None
    if not bestaat and soort == "gesprek" and 0 < MAX_GESPREKKEN <= stand["gesprekken"]:
        return MELDING_GESPREKKEN.format(n=MAX_GESPREKKEN)
    if not bestaat and soort == "werkboek" and 0 < MAX_WERKBOEKEN <= stand["werkboeken"]:
        return MELDING_WERKBOEKEN.format(n=MAX_WERKBOEKEN)
    if MAX_OPSLAG_BYTES > 0 and stand["grootte"] - (stand["item"] or 0) + nieuw > MAX_OPSLAG_BYTES:
        return MELDING_RUIMTE.format(mb=MAX_OPSLAG_BYTES // (1024 * 1024) or 1)
    return None
