"""De duimpjes zijn weg (#983, besluit 09-11): geen eindpunt meer voor feedback per antwoord, en geen opgeslagen
feedback per antwoord meer. Bij de start gaat de tabel `answer_feedback` weg, op SQLite en PostgreSQL, bij elke start
opnieuw en zonder fout als zij er niet (meer) is.
"""

import importlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

import server
from tests.test_persistence_beurtbewijs import postgres  # noqa: F401  (fixture)


@pytest.mark.parametrize("methode", ["GET", "POST"])
def test_er_is_geen_eindpunt_voor_feedback_per_antwoord(methode):
    client = TestClient(server.app)
    # Vroeger: GET gaf de oordelen (200), POST zonder geldige body een 422.
    assert client.request(methode, "/api/answer-feedback", params={"conversation_id": "c1"}, json={}).status_code == 404
    # De vragenlijst op rapporten en de link Feedback blijven: daar bestaat de route, dus geen 404.
    assert client.post("/api/feedback", json={}).status_code != 404
    assert client.post("/api/feedback/algemeen", json={}).status_code != 404


def _tabellen(pad) -> set[str]:
    with sqlite3.connect(pad) as conn:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_de_start_haalt_de_oude_tabel_met_haar_rijen_weg(tmp_path, monkeypatch):
    pad = tmp_path / "oud.db"
    with sqlite3.connect(pad) as oud:
        oud.executescript("""
            CREATE TABLE answer_feedback (
                username TEXT NOT NULL, conversation_id TEXT NOT NULL, message_index INTEGER NOT NULL,
                oordeel TEXT NOT NULL, toelichting TEXT NOT NULL DEFAULT '', trace TEXT NOT NULL,
                created_at TEXT NOT NULL, PRIMARY KEY (username, conversation_id, message_index)
            );
            INSERT INTO answer_feedback VALUES ('anna', 'c1', 1, 'down', 'klopt niet', '{}', '2026-11-01T10:00:00+00:00');
        """)
    monkeypatch.setenv("DATABASE_PATH", str(pad))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    assert "answer_feedback" not in _tabellen(pad)
    # Idempotent: een tweede start (of een tweede replica) vindt niets meer en faalt niet.
    db.init_db()
    assert "answer_feedback" not in _tabellen(pad)
    # De rest van het schema blijft, ook het bewijs per antwoord met zijn controle (#875/#876).
    assert {"conversations", "feedback", "algemene_feedback", "beurtbewijs"} <= _tabellen(pad)


def test_een_nieuwe_database_krijgt_de_tabel_niet(tmp_path, monkeypatch):
    pad = tmp_path / "nieuw.db"
    monkeypatch.setenv("DATABASE_PATH", str(pad))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    assert "answer_feedback" not in _tabellen(pad)
    assert not any("answer_feedback" in ddl for ddl in db._SCHEMA)


def test_postgres_haalt_de_tabel_weg_met_if_exists(postgres):  # noqa: F811
    import persistence.db as db

    db.init_db()

    statements = [" ".join(sql.split()) for sql, _ in postgres.log]
    assert "DROP TABLE IF EXISTS answer_feedback" in statements
    assert not any(s.startswith("CREATE TABLE IF NOT EXISTS answer_feedback") for s in statements)
