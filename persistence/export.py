"""Alles wat de server onder één gebruikersnaam bewaart, als één JSON-bestand (AVG art. 15, #645).

Per soort een generator van rijen, en `export_json_chunks` die de JSON stuk voor stuk opbouwt: de
kop, daarna per soort `[`, de rijen en `]`. Zo staat de export nooit in zijn geheel in het geheugen,
ook niet met tachtig rapporten van een paar MB HTML (#633). Gesprekken en werkboeken komen daarom als
lijst van ids en daarna één voor één; een verbinding blijft alleen open voor één query, niet over een
`yield` heen, zodat een trage download geen plek in de Postgres-pool vasthoudt (#508).

Elke query filtert op `username = ?`. Niet in de export: andermans rijen, feedback die bij het
verwijderen van een gesprek is losgekoppeld (`verwijderd`, #476), ingetrokken tokens en de
`localStorage` van de browser. Kolomnamen zijn die van de database (`html_content`, zoals
`GET /api/workbooks/{id}`).
"""

import json
import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

from persistence import db

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def _json_of_tekst(waarde: str | None) -> object:
    """Een JSON-kolom ontleed; None blijft None, en een onleesbare waarde gaat als tekst mee in plaats van te falen."""
    if waarde is None:
        return None
    try:
        return json.loads(waarde)
    except ValueError:
        return waarde


def _rijen(sql: str, params: tuple) -> list[dict]:
    with db._connection() as conn:
        return [dict(r) for r in db._execute(conn, sql, params).fetchall()]


def _rij(sql: str, params: tuple) -> dict | None:
    with db._connection() as conn:
        row = db._execute(conn, sql, params).fetchone()
    return dict(row) if row else None


def _ids(sql: str, username: str) -> list[str]:
    return [r["id"] for r in _rijen(sql, (username,))]


def conversations(username: str) -> Iterator[dict]:
    """Elk gesprek met zijn berichten, nieuwste eerst; één gesprek tegelijk uit de database."""
    sql_ids = "SELECT id FROM conversations WHERE username = ? ORDER BY timestamp DESC, id DESC"
    for conv_id in _ids(sql_ids, username):
        row = _rij(
            "SELECT id, title, timestamp, messages FROM conversations WHERE id = ? AND username = ?",
            (conv_id, username),
        )
        if row is not None:
            row["messages"] = _json_of_tekst(row["messages"])
            yield row


def workbooks(username: str) -> Iterator[dict]:
    """Elk rapport en dashboard met HTML, berichten, figuren en spec; één werkboek tegelijk uit de database."""
    sql_ids = "SELECT id FROM workbooks WHERE username = ? ORDER BY created_at DESC, id DESC"
    for wb_id in _ids(sql_ids, username):
        row = _rij(
            "SELECT id, title, description, instelling, created_at, messages, figures, html_content, dashboard_spec "
            "FROM workbooks WHERE id = ? AND username = ?",
            (wb_id, username),
        )
        if row is not None:
            for kolom in ("messages", "figures", "dashboard_spec"):
                row[kolom] = _json_of_tekst(row[kolom])
            yield row


def feedback(username: str) -> Iterator[dict]:
    """De antwoorden op de vragen bij een rapport of dashboard."""
    for row in _rijen(
        "SELECT id, workbook_id, report_type, report_title, instelling, answers, created_at FROM feedback "
        "WHERE username = ? ORDER BY created_at, id",
        (username,),
    ):
        row["answers"] = _json_of_tekst(row["answers"])
        yield row


def algemene_feedback(username: str) -> Iterator[dict]:
    """Wat de gebruiker via de link Feedback stuurde (#600)."""
    yield from _rijen(
        "SELECT id, soort, tekst, pagina, created_at FROM algemene_feedback WHERE username = ? ORDER BY created_at, id",
        (username,),
    )


def answer_feedback(username: str) -> Iterator[dict]:
    """Het oordeel per antwoord met toelichting en trace; losgekoppelde feedback (#476) hoort bij niemand."""
    if username == db.VERWIJDERDE_GEBRUIKER:
        return
    for row in _rijen(
        "SELECT conversation_id, message_index, oordeel, toelichting, trace, created_at FROM answer_feedback "
        "WHERE username = ? ORDER BY created_at, conversation_id, message_index",
        (username,),
    ):
        row["trace"] = _json_of_tekst(row["trace"])
        yield row


def data_recipes(username: str) -> Iterator[dict]:
    """Hoe de tabellen van de gesprekken zijn opgehaald (#472)."""
    for row in _rijen(
        "SELECT conv_id, data_key, recipe, created_at FROM data_recipes "
        "WHERE username = ? ORDER BY created_at, conv_id, data_key",
        (username,),
    ):
        row["recipe"] = _json_of_tekst(row["recipe"])
        yield row


SOORTEN: dict[str, Callable[[str], Iterator[dict]]] = {
    "conversations": conversations,
    "workbooks": workbooks,
    "feedback": feedback,
    "algemene_feedback": algemene_feedback,
    "answer_feedback": answer_feedback,
    "data_recipes": data_recipes,
}


def _dump(waarde: object) -> str:
    return json.dumps(waarde, ensure_ascii=False)


def export_json_chunks(username: str, nu: datetime | None = None) -> Iterator[str]:
    """De export als JSON-tekst in stukken: de kop, dan per soort een lijst, rij voor rij.

    De regelovergang komt alleen als laatste teken: daaraan ziet de frontend dat het bestand compleet is
    (`downloadMijnGegevens`), want `json.dumps` schrijft er binnen een tekst nooit een. Op INFO alleen het
    aantal rijen per soort, nooit de inhoud of de gebruikersnaam (#475).
    """
    exported_at = (nu or datetime.now(UTC)).isoformat(timespec="seconds")
    yield f'{{"schema_version": {SCHEMA_VERSION}, "exported_at": {_dump(exported_at)}, "username": {_dump(username)}'
    aantallen: dict[str, int] = {}
    for soort, rijen in SOORTEN.items():
        yield f", {_dump(soort)}: ["
        aantal = 0
        for rij in rijen(username):
            yield (", " if aantal else "") + _dump(rij)
            aantal += 1
        yield "]"
        aantallen[soort] = aantal
    yield "}\n"
    logger.info("export mijn gegevens: %s", ", ".join(f"{soort}={n}" for soort, n in aantallen.items()))
