"""Alles wat de server onder één gebruikersnaam bewaart, als één JSON-bestand (AVG art. 15, #645).

Per soort een generator van rijen, en `export_json_chunks` die de JSON stuk voor stuk opbouwt: de
kop, daarna per soort `[`, de rijen en `]`. Zo staat de export nooit in zijn geheel in het geheugen,
ook niet met tachtig rapporten van een paar MB HTML (#633). Gesprekken en werkboeken komen daarom als
lijst van ids en daarna één voor één; een verbinding blijft alleen open voor één query, niet over een
`yield` heen, zodat een trage download geen plek in de Postgres-pool vasthoudt (#508).

Elke query filtert op `username = ?`, behalve die van `tokengebruik`, `oidc_gebruiker` en `geavanceerd`: die staan onder
een pseudoniem van de naam (#1112, #984, #1269), dus filteren die op `sleutel = ?` met dat pseudoniem en geven de sleutel
niet mee: `tokengebruik` alleen `dag` en `eenheden` (#1074), `oidc_gebruiker` het bewaarde SRAM-profiel (`gegevens`,
ontleed) en `expires_at` (#1209), `geavanceerd` de keuze (`aan`) en `gewijzigd`. Niet in de export: andermans rijen, ingetrokken tokens en de `localStorage` van de browser.
Kolomnamen zijn die van de database (`html_content`, zoals `GET /api/workbooks/{id}`). Een nieuwe soort komt achteraan
en verhoogt `SCHEMA_VERSION` niet: hij voegt alleen een sleutel toe. Zo ook `reden_leeg` in een lege `beurtbewijs`-rij
(#1217), `oidc_gebruiker` (#1209) en `geavanceerd` (#1269).
"""

import json
import logging
import time
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


def data_recipes(username: str) -> Iterator[dict]:
    """Hoe de tabellen van de gesprekken zijn opgehaald (#472)."""
    for row in _rijen(
        "SELECT conv_id, data_key, recipe, created_at FROM data_recipes "
        "WHERE username = ? ORDER BY created_at, conv_id, data_key",
        (username,),
    ):
        row["recipe"] = _json_of_tekst(row["recipe"])
        yield row


_BEURTBEWIJS_KOLOMMEN = ("lineage", "rekenbewijs", "bronnen", "figuren")
REDEN_LEEG = "geen toolstap in deze beurt"


def beurtbewijs(username: str) -> Iterator[dict]:
    """Wat de server per antwoord vastlegde: herkomst, rekenbewijs en figuurstappen (#993) voor het rapport
    (ADR-009, #875) en de bronregels voor een vervolgantwoord (#987).

    Een antwoord zonder toolstap heeft vier lege verzamelingen (`None`, `""`, `[]` of `{}`). Die rij blijft in de
    export, want die is compleet (AVG), maar krijgt `reden_leeg`, zodat ze niet als ontbrekende data leest (#1217);
    een rij met inhoud krijgt die sleutel niet.
    """
    for row in _rijen(
        "SELECT conv_id, tekst_hash, lineage, rekenbewijs, bronnen, figuren, created_at FROM beurtbewijs "
        "WHERE username = ? ORDER BY created_at, conv_id, tekst_hash",
        (username,),
    ):
        for kolom in _BEURTBEWIJS_KOLOMMEN:
            row[kolom] = _json_of_tekst(row[kolom])
        if not any(row[kolom] for kolom in _BEURTBEWIJS_KOLOMMEN):
            row["reden_leeg"] = REDEN_LEEG
        yield row


def tokengebruik(username: str) -> Iterator[dict]:
    """Hoeveel de vragen van het account het model kostten, één getal per dag (#678, #1074); zonder de sleutel."""
    yield from _rijen(
        "SELECT dag, eenheden FROM tokengebruik WHERE sleutel = ? ORDER BY dag",
        (db.tokengebruik_sleutel(username),),
    )


def oidc_gebruiker(username: str) -> Iterator[dict]:
    """Het SRAM-profiel van het account (naam, e-mail, organisatie, instelling; #984, #1209): hoogstens één rij, met
    `gegevens` ontleed en `expires_at` (seconden sinds epoch), zonder de sleutel. Een verlopen rij leest de app niet meer
    (`db.oidc_gebruiker_lees`), dus de export toont haar ook niet; lezen houdt de rij hier niet jong."""
    for row in _rijen(
        "SELECT gegevens, expires_at FROM oidc_gebruikers WHERE sleutel = ? AND expires_at > ?",
        (db.oidc_sleutel(username), int(time.time())),
    ):
        row["gegevens"] = _json_of_tekst(row["gegevens"])
        yield row


def geavanceerd(username: str) -> Iterator[dict]:
    """De instelling "Geavanceerd" van het account (#1269): hoogstens één rij, `aan` (ja/nee) en `gewijzigd` (ms sinds
    epoch), zonder de sleutel. Geen rij: de gebruiker koos nog niets, dan staat ze uit."""
    for row in _rijen(
        "SELECT aan, gewijzigd FROM geavanceerd WHERE sleutel = ?",
        (db.geavanceerd_sleutel(username),),
    ):
        yield {"aan": bool(row["aan"]), "gewijzigd": row["gewijzigd"]}


SOORTEN: dict[str, Callable[[str], Iterator[dict]]] = {
    "conversations": conversations,
    "workbooks": workbooks,
    "feedback": feedback,
    "algemene_feedback": algemene_feedback,
    "data_recipes": data_recipes,
    "beurtbewijs": beurtbewijs,
    "tokengebruik": tokengebruik,
    "oidc_gebruiker": oidc_gebruiker,
    "geavanceerd": geavanceerd,
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
