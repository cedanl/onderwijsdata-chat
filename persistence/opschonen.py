"""Bewaartermijn en opschoning (#485, privacy M5): wat over zijn termijn is, gaat weg; wat actief is, blijft.

Termijnen (besluit 21-10-2026), in te stellen in core/config.py:

- Gesprekken (`conversations`): 90 dagen na de laatste activiteit, de tijd van het laatst opgeslagen bericht
  (`timestamp`). Met het gesprek gaat wat erbij hoort, zoals bij verwijderen door de gebruiker
  (`db.ruim_gesprek_op`): zijn datarecepten weg, zijn feedback per antwoord losgekoppeld (#476).
- Feedback (`answer_feedback` met de `trace`, `feedback` met `report_title` en vrije tekst, `algemene_feedback`):
  90 dagen nadat hij is gegeven (`created_at`). Feedback per antwoord blijft zolang zijn gesprek actief is.
- Datarecepten zonder gesprek (`data_recipes`): 90 dagen na `created_at`; een jonger recept kan bij een gesprek
  horen dat nog wordt opgeslagen.
- Rapporten en dashboards (`workbooks`): 365 dagen nadat ze voor het laatst zijn opgeslagen of geopend
  (`laatst_gebruikt`). Langer dan een gesprek: een rapport is het resultaat dat je bewaart en terugkijkt.

Veiligheid: de grens is één expliciet tijdstip (`grenzen`, uit een opgegeven `nu`); een rij precies op de grens
blijft. Een termijn die geen geheel getal is of korter dan 7 dagen, verwijdert niets. Alles gebeurt in één
transactie: bij een fout blijft alles staan (rollback; de verbinding gaat zonder commit dicht). `--droog` telt met
dezelfde voorwaarden en verwijdert niets. De datastore en de wachtende recepten in het geheugen van de app-pod
(tools/store.py, agent/recepten.py) zijn vanuit een aparte taak niet te bereiken; die zijn begrensd en verdwijnen
bij een herstart.

Aanroep: `python -m persistence.opschonen [--droog]`, ook als CronJob in de Helm-chart (`opschonen` in
charts/onderwijsdata-chat/values.yaml). Uitvoer: alleen de grenzen en aantallen per tabel, nooit een account.
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from core import config
from persistence import db

logger = logging.getLogger(__name__)

MINIMUM_DAGEN = 7

# De tabellen die de opschoning raakt, in de volgorde van de uitvoer.
SOORTEN = ("conversations", "data_recipes", "answer_feedback", "feedback", "algemene_feedback", "workbooks")


class OngeldigeTermijn(ValueError):
    """Een bewaartermijn die geen geheel aantal dagen van minstens MINIMUM_DAGEN is: er wordt niets verwijderd."""


@dataclass(frozen=True)
class Termijnen:
    gesprekken: int
    rapporten: int


@dataclass(frozen=True)
class Grenzen:
    """Wat vóór deze tijdstippen voor het laatst actief was, is verlopen; een rij precies op de grens blijft."""

    gesprekken: datetime
    rapporten: datetime


def _dagen(naam: str, waarde: object) -> int:
    tekst = str(waarde).strip() if waarde is not None else ""
    if not (tekst.isascii() and tekst.isdigit()) or int(tekst) < MINIMUM_DAGEN:
        raise OngeldigeTermijn(f"{naam} moet een geheel aantal dagen zijn, minstens {MINIMUM_DAGEN}; niet {waarde!r}")
    return int(tekst)


_UIT_CONFIG = object()


def termijnen(gesprekken: object = _UIT_CONFIG, rapporten: object = _UIT_CONFIG) -> Termijnen:
    """De getoetste termijnen; zonder argument uit de config (BEWAARTERMIJN_GESPREKKEN_DAGEN, _RAPPORTEN_DAGEN)."""
    if gesprekken is _UIT_CONFIG:
        gesprekken = config.BEWAARTERMIJN_GESPREKKEN_DAGEN
    if rapporten is _UIT_CONFIG:
        rapporten = config.BEWAARTERMIJN_RAPPORTEN_DAGEN
    return Termijnen(
        gesprekken=_dagen("BEWAARTERMIJN_GESPREKKEN_DAGEN", gesprekken),
        rapporten=_dagen("BEWAARTERMIJN_RAPPORTEN_DAGEN", rapporten),
    )


def grenzen(t: Termijnen, nu: datetime) -> Grenzen:
    if nu.tzinfo is None:
        raise ValueError("nu heeft een tijdzone nodig")
    return Grenzen(gesprekken=nu - timedelta(days=t.gesprekken), rapporten=nu - timedelta(days=t.rapporten))


def _iso(tijd: datetime) -> str:
    """Zoals de app `created_at` schrijft (UTC, op de seconde): dan sorteert de tekst als de tijd."""
    return tijd.astimezone(UTC).isoformat(timespec="seconds")


def _bij_gesprek(tabel: str, kolom: str, actief: bool) -> str:
    """Of de rij een (actief) gesprek heeft; actief betekent: laatste activiteit op of na de grens."""
    voorwaarde = " AND c.timestamp >= ?" if actief else ""
    return (
        f"EXISTS (SELECT 1 FROM conversations c WHERE c.id = {tabel}.{kolom} "
        f"AND c.username = {tabel}.username{voorwaarde})"
    )


def _voorwaarden(g: Grenzen) -> dict[str, tuple[str, tuple]]:
    """Per tabel wat verlopen is, als WHERE met parameters. `tel` gebruikt ze letterlijk; `schoon_op` komt op
    hetzelfde uit (tests/test_opschonen.py vergelijkt beide)."""
    gesprek_s, gesprek_iso = int(g.gesprekken.timestamp()), _iso(g.gesprekken)
    return {
        "conversations": ("timestamp < ?", (gesprek_s,)),
        # Van een verlopen gesprek, of zonder gesprek en ouder dan de termijn.
        "data_recipes": (
            f"NOT {_bij_gesprek('data_recipes', 'conv_id', actief=True)} "
            f"AND (created_at < ? OR {_bij_gesprek('data_recipes', 'conv_id', actief=False)})",
            (gesprek_s, gesprek_iso),
        ),
        "answer_feedback": (
            f"created_at < ? AND NOT {_bij_gesprek('answer_feedback', 'conversation_id', actief=True)}",
            (gesprek_iso, gesprek_s),
        ),
        "feedback": ("created_at < ?", (gesprek_iso,)),
        "algemene_feedback": ("created_at < ?", (gesprek_iso,)),
        "workbooks": ("laatst_gebruikt < ?", (int(g.rapporten.timestamp()),)),
    }


def tel(g: Grenzen) -> dict[str, int]:
    """Hoeveel rijen per tabel verlopen zijn; leest alleen."""
    with db._connection() as conn:
        return {
            tabel: int(db._execute(conn, f"SELECT COUNT(*) AS n FROM {tabel} WHERE {waar}", params).fetchone()["n"])
            for tabel, (waar, params) in _voorwaarden(g).items()
        }


def schoon_op(g: Grenzen) -> dict[str, int]:
    """Verwijder wat verlopen is, in één transactie; per tabel het aantal verwijderde rijen."""
    with db._connection() as conn:
        try:
            aantallen = _verwijder(conn, g)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return aantallen


def _verwijder(conn: Any, g: Grenzen) -> dict[str, int]:
    voorwaarden = _voorwaarden(g)
    waar, params = voorwaarden["conversations"]
    gesprekken = db._execute(conn, f"DELETE FROM conversations WHERE {waar} RETURNING id, username", params).fetchall()
    # Per verwijderd gesprek hetzelfde als bij verwijderen door de gebruiker: recepten weg, feedback losgekoppeld.
    recepten = sum(db.ruim_gesprek_op(conn, rij["username"], rij["id"]) for rij in gesprekken)
    # Daarna heeft geen recept en geen feedback nog een verlopen gesprek: wat overblijft van de voorwaarde zijn de
    # recepten zonder gesprek (wezen), de losgekoppelde feedback en die van eerder verwijderde gesprekken.
    wezen = f"DELETE FROM data_recipes WHERE created_at < ? AND NOT {_bij_gesprek('data_recipes', 'conv_id', False)}"
    recepten += db._execute(conn, wezen, (_iso(g.gesprekken),)).rowcount
    aantallen = {"conversations": len(gesprekken), "data_recipes": recepten}
    for tabel in ("answer_feedback", "feedback", "algemene_feedback", "workbooks"):
        waar, params = voorwaarden[tabel]
        aantallen[tabel] = db._execute(conn, f"DELETE FROM {tabel} WHERE {waar}", params).rowcount
    return {tabel: aantallen[tabel] for tabel in SOORTEN}


def _samenvatting(droog: bool, t: Termijnen, g: Grenzen, aantallen: dict[str, int]) -> str:
    soort = "droog, niets verwijderd" if droog else "verwijderd"
    database = "postgres" if db._USE_POSTGRES else "sqlite"
    telling = " ".join(f"{tabel}={aantallen[tabel]}" for tabel in SOORTEN)
    return (
        f"opschonen ({soort}, {database}): gesprekken en feedback vóór {_iso(g.gesprekken)} ({t.gesprekken} dagen), "
        f"rapporten vóór {_iso(g.rapporten)} ({t.rapporten} dagen): {telling}"
    )


def main(argv: list[str] | None = None, nu: datetime | None = None) -> int:
    """0: gelukt; 1: databasefout, niets verwijderd; 2: ongeldige termijn, niets verwijderd."""
    parser = argparse.ArgumentParser(
        prog="python -m persistence.opschonen",
        description="Verwijder gesprekken, feedback en rapporten die over hun bewaartermijn zijn (#485).",
    )
    parser.add_argument("--droog", action="store_true", help="alleen tellen wat zou verdwijnen, niets verwijderen")
    args = parser.parse_args(argv)
    try:
        t = termijnen()
    except OngeldigeTermijn as fout:
        print(f"opschonen geweigerd, niets verwijderd: {fout}", file=sys.stderr)
        return 2
    g = grenzen(t, nu or datetime.now(UTC))
    try:
        aantallen = tel(g) if args.droog else schoon_op(g)
    except Exception as fout:
        # Alleen het type: fouttekst hoort niet in het log (#502); op DEBUG wel de traceback.
        logger.debug("opschonen mislukt", exc_info=True)
        print(f"opschonen mislukt ({type(fout).__name__}), niets verwijderd", file=sys.stderr)
        return 1
    print(_samenvatting(args.droog, t, g, aantallen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
