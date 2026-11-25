"""Alles wat de server onder één gebruikersnaam bewaart, in één keer weg (AVG art. 17, #646).

Eén `DELETE ... WHERE username = ?` per soort, in één transactie; `tokengebruik` en het SRAM-profiel (`oidc_gebruikers`)
staan onder een pseudoniem van de naam (#1112, #984) en gaan weg met `WHERE sleutel = ?` en dat pseudoniem (#1074,
#1209). Alles in één transactie: lukt één ervan niet, dan blijft alles staan
(rollback bij SQLite, en de Postgres-pool rolt een niet-gecommitte verbinding terug). Opnieuw proberen is veilig:
een tweede keer verwijdert nul rijen.

Ingetrokken tokens (`revoked_tokens`, `revoked_users`) hebben
geen gebruikersnaam, alleen een hash, en vervallen vanzelf; de route zet er hierna een rij voor alle tokens van het
account bij (#786).
"""

from persistence import db

# Per soort zijn ene DELETE; de sleutels en hun volgorde zijn die van export.SOORTEN, en het zijn precies de
# tabellen met een kolom `username`, plus `tokengebruik` en `oidc_gebruikers` (tests/test_mijn_gegevens_verwijderen.py
# bewaakt beide).
DELETES: dict[str, str] = {
    "conversations": "DELETE FROM conversations WHERE username = ?",
    "workbooks": "DELETE FROM workbooks WHERE username = ?",
    "feedback": "DELETE FROM feedback WHERE username = ?",
    "algemene_feedback": "DELETE FROM algemene_feedback WHERE username = ?",
    "data_recipes": "DELETE FROM data_recipes WHERE username = ?",
    "beurtbewijs": "DELETE FROM beurtbewijs WHERE username = ?",
    "tokengebruik": "DELETE FROM tokengebruik WHERE sleutel = ?",
    "oidc_gebruiker": "DELETE FROM oidc_gebruikers WHERE sleutel = ?",
}


def verwijder_alles(username: str) -> dict[str, int]:
    """Verwijder alle rijen van deze gebruiker; per soort het aantal verwijderde rijen."""
    parameters = dict.fromkeys(DELETES, username) | {
        "tokengebruik": db.tokengebruik_sleutel(username),
        "oidc_gebruiker": db.oidc_sleutel(username),
    }
    with db._connection() as conn:
        aantallen = {soort: db._execute(conn, sql, (parameters[soort],)).rowcount for soort, sql in DELETES.items()}
        conn.commit()
    return aantallen
