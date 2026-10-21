"""Alles wat de server onder één gebruikersnaam bewaart, in één keer weg (AVG art. 17, #646).

Eén `DELETE ... WHERE username = ?` per soort, in één transactie: lukt één ervan niet, dan blijft alles staan
(rollback bij SQLite, en de Postgres-pool rolt een niet-gecommitte verbinding terug). Opnieuw proberen is veilig:
een tweede keer verwijdert nul rijen.

Ook de feedback per antwoord gaat weg, met zijn `trace`: die kan persoonsgegevens bevatten. Niet hier: feedback
die al bij het verwijderen van een gesprek is losgekoppeld (`verwijderd`, #476) hangt aan niemand meer en blijft;
een account dat toevallig zo heet, wist die dus niet. Ingetrokken tokens (`revoked_tokens`) hebben geen
gebruikersnaam en vervallen vanzelf.
"""

from typing import Any

from persistence import db

# Per soort zijn ene DELETE; de sleutels en hun volgorde zijn die van export.SOORTEN, en het zijn precies de
# tabellen met een kolom `username` (tests/test_mijn_gegevens_verwijderen.py bewaakt beide).
DELETES: dict[str, str] = {
    "conversations": "DELETE FROM conversations WHERE username = ?",
    "workbooks": "DELETE FROM workbooks WHERE username = ?",
    "feedback": "DELETE FROM feedback WHERE username = ?",
    "algemene_feedback": "DELETE FROM algemene_feedback WHERE username = ?",
    "answer_feedback": "DELETE FROM answer_feedback WHERE username = ?",
    "data_recipes": "DELETE FROM data_recipes WHERE username = ?",
}


def verwijder_alles(username: str) -> dict[str, int]:
    """Verwijder alle rijen van deze gebruiker; per soort het aantal verwijderde rijen."""
    with db._connection() as conn:
        aantallen = {soort: _verwijder(conn, soort, username) for soort in DELETES}
        conn.commit()
    return aantallen


def _verwijder(conn: Any, soort: str, username: str) -> int:
    if soort == "answer_feedback" and username == db.VERWIJDERDE_GEBRUIKER:
        return 0
    return db._execute(conn, DELETES[soort], (username,)).rowcount
