"""Verwijderde gesprekstekst staat niet meer in het SQLite-bestand (#1116, AVG art. 17 en 32).

SQLite geeft vrijgekomen pagina's niet leeg: na een DELETE staat de tekst nog in het databasebestand, tot er een
andere rij overheen komt. SQLite is alleen de lokale terugval (SDP draait op PostgreSQL), maar wie de app op een laptop
draait en gegevens "definitief" verwijdert, houdt ze anders op schijf. De tests zoeken bytes in het bestand zelf en in
`-wal` en `-journal`, niet in de tabellen.
"""

import importlib
import sqlite3
from pathlib import Path

import pytest

TEKST = "Ik ben Jan Jansen, jan.jansen@example.nl, 0612345678"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    return db


def _bytes_op_schijf(pad: Path) -> bytes:
    """Het databasebestand en wat ernaast staat (`-wal`, `-shm`, `-journal`), als één reeks bytes."""
    return b"".join(p.read_bytes() for p in sorted(pad.parent.glob(f"{pad.name}*")) if p.is_file())


def _bewaar(db, conv_id: str, tekst: str = TEKST, user: str = "anna") -> None:
    # Genoeg tekst voor een overflowpagina: een lang gesprek staat niet in één bladpagina.
    berichten = [{"role": "user", "content": tekst}, {"role": "assistant", "content": "Antwoord. " * 2000}]
    db.upsert_conversation(user, conv_id, "titel", 1_795_180_000, berichten)


def test_na_verwijderen_van_een_gesprek_staat_de_tekst_niet_meer_op_schijf(db, tmp_path):
    _bewaar(db, "pii-1")
    assert TEKST.encode() in _bytes_op_schijf(tmp_path / "test.db"), "de test moet de tekst eerst kunnen vinden"

    db.delete_conversation("anna", "pii-1")

    assert TEKST.encode() not in _bytes_op_schijf(tmp_path / "test.db")


def test_ook_als_een_andere_verbinding_open_staat_blijft_er_geen_tekst_in_de_wal(db, tmp_path):
    """Zolang een lezer open staat, ruimt SQLite de WAL niet zelf op: de verwijdering moet haar dan zelf leegmaken."""
    _bewaar(db, "pii-1")
    lezer = sqlite3.connect(tmp_path / "test.db")
    try:
        lezer.execute("SELECT COUNT(*) FROM conversations").fetchone()

        db.delete_conversation("anna", "pii-1")

        assert TEKST.encode() not in _bytes_op_schijf(tmp_path / "test.db")
    finally:
        lezer.close()


def test_na_verwijder_alles_staat_de_tekst_niet_meer_op_schijf(db, tmp_path):
    from persistence import verwijderen

    _bewaar(db, "pii-1")
    _bewaar(db, "pii-2")
    db.add_algemene_feedback("anna", "", f"Feedback van {TEKST}", "/")

    verwijderen.verwijder_alles("anna")

    assert TEKST.encode() not in _bytes_op_schijf(tmp_path / "test.db")


def test_een_bijgewerkt_antwoord_laat_de_oude_tekst_niet_achter(db, tmp_path):
    """Een afgebroken antwoord dat later volledig wordt opgeslagen (#548): het oude stuk hoort niet op schijf te blijven."""
    db.upsert_conversation(
        "anna", "c", "t", 1_795_180_000, [{"role": "user", "content": "vraag"}, {"role": "assistant", "content": TEKST}]
    )
    assert TEKST.encode() in _bytes_op_schijf(tmp_path / "test.db")

    db.upsert_conversation(
        "anna",
        "c",
        "t",
        1_795_180_000,
        [{"role": "user", "content": "vraag"}, {"role": "assistant", "content": "Een gewoon antwoord"}],
    )

    assert TEKST.encode() not in _bytes_op_schijf(tmp_path / "test.db")


def test_de_opruiming_na_de_bewaartermijn_wist_ook_op_schijf(db, tmp_path):
    from datetime import UTC, datetime

    from persistence import opschonen

    _bewaar(db, "oud")
    nu = datetime.fromtimestamp(1_795_180_000, UTC).replace(year=2027)
    opschonen.schoon_op(opschonen.grenzen(opschonen.termijnen(), nu))

    assert TEKST.encode() not in _bytes_op_schijf(tmp_path / "test.db")
