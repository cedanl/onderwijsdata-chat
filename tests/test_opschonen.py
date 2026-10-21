"""Bewaartermijn en opschoning (#485, privacy M5): verlopen rijen verdwijnen, actieve blijven, niets bij een fout.

Termijnen (besluit 21-10-2026): gesprekken met alles wat erbij hoort en alle feedback 90 dagen na de laatste
activiteit, rapporten en dashboards 365 dagen nadat ze voor het laatst zijn opgeslagen of geopend. De tijden van de
rijen zet de test direct in SQLite, relatief aan één vast `NU`: de grens is expliciet, niet "nu" tijdens de run.
"""

import sqlite3
import time
from datetime import UTC, datetime, timedelta

import pytest

from core import config
from persistence import db, opschonen

NU = datetime(2026, 10, 21, 3, 30, tzinfo=UTC)
_DAG = 24 * 3600


def _epoch(dagen_geleden: float) -> int:
    return int((NU - timedelta(days=dagen_geleden)).timestamp())


def _iso(dagen_geleden: float) -> str:
    return (NU - timedelta(days=dagen_geleden)).isoformat(timespec="seconds")


@pytest.fixture
def pad(tmp_path, monkeypatch):
    pad = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(pad))
    db.init_db()
    return pad


def _sql(pad, sql: str, params: tuple = ()) -> list[tuple]:
    conn = sqlite3.connect(pad)
    try:
        rijen = conn.execute(sql, params).fetchall()
        conn.commit()
        return rijen
    finally:
        conn.close()


def _alles(pad) -> dict[str, list[tuple]]:
    """Elke rij van elke tabel die de opschoning raakt, gesorteerd: om te zien dat er niets veranderde."""
    return {soort: sorted(_sql(pad, f"SELECT * FROM {soort}"), key=repr) for soort in opschonen.SOORTEN}


def _gesprek(pad, user: str, conv: str, dagen_geleden: float, recepten: tuple[str, ...] = ()) -> None:
    db.upsert_conversation(user, conv, f"Gesprek {conv}", _epoch(dagen_geleden), [{"role": "user", "content": "x"}])
    db.save_recipes(user, conv, {k: {"laad": ["get_rio_data", {"resource": k}]} for k in recepten})
    _sql(
        pad,
        "UPDATE data_recipes SET created_at = ? WHERE username = ? AND conv_id = ?",
        (_iso(dagen_geleden), user, conv),
    )


def _oordeel(pad, user: str, conv: str, index: int, dagen_geleden: float) -> None:
    db.upsert_answer_feedback(user, conv, index, "down", "klopt niet", {"vraag": "x", "antwoord": "y"})
    _sql(
        pad,
        "UPDATE answer_feedback SET created_at = ? WHERE username = ? AND conversation_id = ? AND message_index = ?",
        (_iso(dagen_geleden), user, conv, index),
    )


def _werkboek(pad, user: str, wb: str, dagen_geleden: float) -> None:
    db.upsert_workbook(user, wb, f"Rapport {wb}", "", html_content="<p>x</p>", created_at="2026-01-01T00:00:00Z")
    _sql(
        pad, "UPDATE workbooks SET laatst_gebruikt = ? WHERE id = ? AND username = ?", (_epoch(dagen_geleden), wb, user)
    )


def _ids(pad, sql: str) -> set:
    return {r if len(r) > 1 else r[0] for r in _sql(pad, sql)}


def _grenzen():
    return opschonen.grenzen(opschonen.termijnen(), NU)


# ── Termijnen en hun veiligheidsgrens ──


def test_standaardtermijnen_zijn_90_en_365_dagen():
    assert opschonen.termijnen() == opschonen.Termijnen(gesprekken=90, rapporten=365)


def test_termijnen_komen_uit_de_config(monkeypatch):
    monkeypatch.setattr(config, "BEWAARTERMIJN_GESPREKKEN_DAGEN", "30")
    monkeypatch.setattr(config, "BEWAARTERMIJN_RAPPORTEN_DAGEN", "180")
    assert opschonen.termijnen() == opschonen.Termijnen(gesprekken=30, rapporten=180)


@pytest.mark.parametrize("waarde", ["6", "0", "-90", "", " ", "negentig", "90.5", "1e3", None])
def test_een_ongeldige_of_te_korte_termijn_wordt_geweigerd(waarde):
    with pytest.raises(opschonen.OngeldigeTermijn):
        opschonen.termijnen(gesprekken=waarde, rapporten="365")
    with pytest.raises(opschonen.OngeldigeTermijn):
        opschonen.termijnen(gesprekken="90", rapporten=waarde)


def test_zeven_dagen_is_de_kortste_termijn():
    assert opschonen.termijnen(gesprekken="7", rapporten=" 7 ") == opschonen.Termijnen(7, 7)


def test_de_grens_ligt_de_termijn_voor_nu():
    g = _grenzen()
    assert g.gesprekken == datetime(2026, 7, 23, 3, 30, tzinfo=UTC)
    assert g.rapporten == datetime(2025, 10, 21, 3, 30, tzinfo=UTC)


def test_nu_zonder_tijdzone_wordt_geweigerd():
    with pytest.raises(ValueError):
        opschonen.grenzen(opschonen.termijnen(), datetime(2026, 10, 21))


# ── Gesprekken en wat erbij hoort ──


def test_verlopen_gesprek_verdwijnt_met_zijn_recepten_een_actief_blijft(pad):
    _gesprek(pad, "anna", "oud", 91, recepten=("cbs:oud",))
    _gesprek(pad, "anna", "nieuw", 89, recepten=("cbs:nieuw",))
    _gesprek(pad, "bert", "oud", 10, recepten=("cbs:bert",))  # zelfde id, ander account: actief

    aantallen = opschonen.schoon_op(_grenzen())

    assert _ids(pad, "SELECT username, id FROM conversations") == {("anna", "nieuw"), ("bert", "oud")}
    assert _ids(pad, "SELECT data_key FROM data_recipes") == {"cbs:nieuw", "cbs:bert"}
    assert aantallen["conversations"] == 1
    assert aantallen["data_recipes"] == 1


def test_de_grens_zelf_telt_als_actief(pad):
    grens = int(_grenzen().gesprekken.timestamp())
    db.upsert_conversation("anna", "op-de-grens", "x", grens, [])
    db.upsert_conversation("anna", "seconde-ervoor", "x", grens - 1, [])

    opschonen.schoon_op(_grenzen())

    assert _ids(pad, "SELECT id FROM conversations") == {"op-de-grens"}


def test_recept_van_een_verlopen_gesprek_gaat_mee_ook_als_het_recept_jonger_is(pad):
    _gesprek(pad, "anna", "oud", 120, recepten=("k",))
    _sql(pad, "UPDATE data_recipes SET created_at = ?", (_iso(1),))  # bijv. een klok die verschilde

    opschonen.schoon_op(_grenzen())

    assert _sql(pad, "SELECT * FROM data_recipes") == []


def test_wees_recepten_gaan_pas_na_de_termijn(pad):
    """Een recept zonder gesprek: oud is een wees, jong hoort bij een gesprek dat nog wordt opgeslagen."""
    db.save_recipes("anna", "nooit-opgeslagen-oud", {"oud": {"laad": ["x", {}]}})
    db.save_recipes("anna", "wordt-nog-opgeslagen", {"jong": {"laad": ["x", {}]}})
    _sql(pad, "UPDATE data_recipes SET created_at = ? WHERE data_key = 'oud'", (_iso(91),))
    _sql(pad, "UPDATE data_recipes SET created_at = ? WHERE data_key = 'jong'", (_iso(0),))

    opschonen.schoon_op(_grenzen())

    assert _ids(pad, "SELECT data_key FROM data_recipes") == {"jong"}


def test_oud_recept_van_een_actief_gesprek_blijft(pad):
    _gesprek(pad, "anna", "c1", 5, recepten=("k",))
    _sql(pad, "UPDATE data_recipes SET created_at = ?", (_iso(400),))

    opschonen.schoon_op(_grenzen())

    assert _ids(pad, "SELECT data_key FROM data_recipes") == {"k"}


def test_een_gesprek_met_een_tijd_in_de_toekomst_ontloopt_de_termijn_niet(pad):
    """De tijd komt van de browser; een verkeerde klok mag een gesprek niet voor altijd actief houden."""
    db.upsert_conversation("anna", "c1", "x", int(time.time()) + 10 * 365 * _DAG, [])
    assert _sql(pad, "SELECT timestamp FROM conversations")[0][0] <= int(time.time())


# ── Feedback ──


def test_feedback_van_een_actief_gesprek_blijft_ook_als_hij_oud_is(pad):
    _gesprek(pad, "anna", "c1", 1)
    _oordeel(pad, "anna", "c1", 1, 200)

    opschonen.schoon_op(_grenzen())

    assert _ids(pad, "SELECT username, conversation_id FROM answer_feedback") == {("anna", "c1")}


def test_feedback_van_een_verlopen_gesprek(pad):
    """Oude feedback gaat mee; jonge wordt losgekoppeld zoals bij verwijderen (#476) en houdt zijn eigen termijn."""
    _gesprek(pad, "anna", "c1", 100)
    _oordeel(pad, "anna", "c1", 1, 95)
    _oordeel(pad, "anna", "c1", 3, 10)

    aantallen = opschonen.schoon_op(_grenzen())

    rijen = _sql(pad, "SELECT username, conversation_id, message_index FROM answer_feedback")
    assert len(rijen) == 1
    username, conv_id, index = rijen[0]
    assert (username, index) == (db.VERWIJDERDE_GEBRUIKER, 3)
    assert conv_id != "c1"
    assert aantallen["answer_feedback"] == 1


def test_losgekoppelde_feedback_verdwijnt_na_de_termijn(pad):
    _gesprek(pad, "anna", "c1", 1)
    _oordeel(pad, "anna", "c1", 1, 91)
    _oordeel(pad, "anna", "c1", 3, 89)
    db.delete_conversation("anna", "c1")  # #476: beide losgekoppeld

    opschonen.schoon_op(_grenzen())

    assert _ids(pad, "SELECT message_index FROM answer_feedback") == {3}


def test_feedback_op_rapporten_en_algemene_feedback_na_90_dagen(pad):
    db.add_feedback("anna", "wb-1", "report", "Instroom hbo", {"contact": "anna@example.org"})
    db.add_feedback("anna", "wb-2", "report", "Uitval mbo", {"contact": "nog jong"})
    db.add_algemene_feedback("anna", "idee", "oud bericht", "/")
    db.add_algemene_feedback("anna", "idee", "nieuw bericht", "/")
    _sql(pad, "UPDATE feedback SET created_at = ? WHERE workbook_id = 'wb-1'", (_iso(91),))
    _sql(pad, "UPDATE feedback SET created_at = ? WHERE workbook_id = 'wb-2'", (_iso(89),))
    _sql(pad, "UPDATE algemene_feedback SET created_at = ? WHERE tekst = 'oud bericht'", (_iso(91),))
    _sql(pad, "UPDATE algemene_feedback SET created_at = ? WHERE tekst = 'nieuw bericht'", (_iso(89),))

    aantallen = opschonen.schoon_op(_grenzen())

    assert _ids(pad, "SELECT workbook_id FROM feedback") == {"wb-2"}
    assert _ids(pad, "SELECT tekst FROM algemene_feedback") == {"nieuw bericht"}
    assert (aantallen["feedback"], aantallen["algemene_feedback"]) == (1, 1)


# ── Rapporten en dashboards ──


def test_werkboek_verdwijnt_na_365_dagen_niet_na_90(pad):
    _werkboek(pad, "anna", "oud", 366)
    _werkboek(pad, "anna", "half-jaar", 200)
    _werkboek(pad, "anna", "nieuw", 1)

    aantallen = opschonen.schoon_op(_grenzen())

    assert _ids(pad, "SELECT id FROM workbooks") == {"half-jaar", "nieuw"}
    assert aantallen["workbooks"] == 1


def test_opslaan_en_openen_verlengen_een_werkboek(pad):
    _werkboek(pad, "anna", "opgeslagen", 400)
    _werkboek(pad, "anna", "geopend", 400)
    _werkboek(pad, "bert", "geopend", 400)  # zelfde id, ander account: niet aangeraakt
    voor = int(time.time())

    db.upsert_workbook("anna", "opgeslagen", "Nieuwe titel", "")
    db.werkboek_geopend("anna", "geopend")

    tijden = dict(_sql(pad, "SELECT username || '/' || id, laatst_gebruikt FROM workbooks"))
    assert tijden["anna/opgeslagen"] >= voor
    assert tijden["anna/geopend"] >= voor
    assert tijden["bert/geopend"] == _epoch(400)


def test_openen_via_de_api_verlengt_het_werkboek(pad, monkeypatch):
    from fastapi.testclient import TestClient

    import server
    from core import auth

    monkeypatch.setattr(auth, "AUTH_ENABLED", False)  # iedereen is dan `gast`
    _werkboek(pad, auth.FALLBACK_USER, "wb1", 400)
    antwoord = TestClient(server.app).get("/api/workbooks/wb1")
    assert antwoord.status_code == 200
    assert _sql(pad, "SELECT laatst_gebruikt FROM workbooks")[0][0] >= int(time.time()) - 5


def test_een_bestaand_werkboek_krijgt_bij_de_migratie_nu_als_laatst_gebruikt(tmp_path, monkeypatch):
    """Van vóór #485 is niet bekend wanneer een werkboek is geopend: de termijn begint bij de migratie."""
    pad = tmp_path / "oud.db"
    monkeypatch.setenv("DATABASE_PATH", str(pad))
    _sql(
        pad,
        "CREATE TABLE workbooks (id TEXT NOT NULL, username TEXT NOT NULL, title TEXT NOT NULL, "
        "description TEXT NOT NULL DEFAULT '', messages TEXT, figures TEXT, instelling TEXT, html_content TEXT, "
        "dashboard_spec TEXT, created_at TEXT NOT NULL, PRIMARY KEY (id, username))",
    )
    _sql(pad, "INSERT INTO workbooks (id, username, title, created_at) VALUES ('w', 'anna', 'Oud', '2024-01-01')")
    voor = int(time.time())

    db.init_db()

    assert _sql(pad, "SELECT laatst_gebruikt FROM workbooks")[0][0] >= voor
    opschonen.schoon_op(opschonen.grenzen(opschonen.termijnen(), datetime.now(UTC)))
    assert _ids(pad, "SELECT id FROM workbooks") == {"w"}


# ── Droog, transactie en de opdrachtregel ──


def _gevuld(pad) -> None:
    """Van elke soort verlopen en actieve rijen, bij twee accounts."""
    _gesprek(pad, "anna", "oud", 100, recepten=("a1", "a2"))
    _gesprek(pad, "anna", "nieuw", 3, recepten=("a3",))
    _gesprek(pad, "bert", "oud", 300, recepten=("b1",))
    db.save_recipes("bert", "wees", {"b2": {"laad": ["x", {}]}})
    _sql(pad, "UPDATE data_recipes SET created_at = ? WHERE data_key = 'b2'", (_iso(150),))
    _oordeel(pad, "anna", "oud", 1, 99)
    _oordeel(pad, "anna", "oud", 3, 2)
    _oordeel(pad, "anna", "nieuw", 1, 150)
    _oordeel(pad, "bert", "oud", 1, 299)
    db.add_feedback("anna", "wb", "report", "R", {"q": "a"})
    _sql(pad, "UPDATE feedback SET created_at = ?", (_iso(120),))
    db.add_algemene_feedback("bert", "", "tekst", "/")
    _werkboek(pad, "anna", "oud", 700)
    _werkboek(pad, "anna", "nieuw", 100)


def test_droog_telt_wat_de_echte_run_verwijdert_en_verwijdert_zelf_niets(pad):
    _gevuld(pad)
    voor = _alles(pad)

    geteld = opschonen.tel(_grenzen())

    assert _alles(pad) == voor
    verwijderd = opschonen.schoon_op(_grenzen())
    assert geteld == verwijderd
    assert verwijderd == {
        "conversations": 2,
        "data_recipes": 4,
        "answer_feedback": 2,
        "feedback": 1,
        "algemene_feedback": 0,
        "workbooks": 1,
    }
    # Een tweede run vindt niets meer.
    assert set(opschonen.schoon_op(_grenzen()).values()) == {0}


def test_een_fout_halverwege_laat_alles_staan(pad, monkeypatch):
    _gevuld(pad)
    voor = _alles(pad)

    def kapot(*args):
        raise RuntimeError("database weg")

    monkeypatch.setattr(db, "_ontkoppel_feedback", kapot)
    with pytest.raises(RuntimeError):
        opschonen.schoon_op(_grenzen())

    assert _alles(pad) == voor


def test_opdrachtregel_droog_en_echt(pad, capsys):
    _gevuld(pad)
    voor = _alles(pad)

    assert opschonen.main(["--droog"], nu=NU) == 0
    uitvoer = capsys.readouterr().out
    assert _alles(pad) == voor
    assert "droog" in uitvoer
    assert "conversations=2" in uitvoer
    assert "2026-07-23T03:30:00+00:00" in uitvoer  # de grens staat in de uitvoer
    assert "anna" not in uitvoer and "bert" not in uitvoer  # alleen aantallen

    assert opschonen.main([], nu=NU) == 0
    assert "conversations=2" in capsys.readouterr().out
    assert _ids(pad, "SELECT username, id FROM conversations") == {("anna", "nieuw")}


def test_opdrachtregel_verwijdert_niets_bij_een_foute_termijn(pad, monkeypatch, capsys):
    _gevuld(pad)
    voor = _alles(pad)
    monkeypatch.setattr(config, "BEWAARTERMIJN_GESPREKKEN_DAGEN", "3")

    assert opschonen.main([], nu=NU) == 2

    assert _alles(pad) == voor
    assert "BEWAARTERMIJN_GESPREKKEN_DAGEN" in capsys.readouterr().err


def test_opdrachtregel_meldt_een_databasefout_zonder_te_verwijderen(tmp_path, monkeypatch, capsys):
    """Een database zonder tabellen (bijv. een verkeerd pad): fout, exitcode 1, en de opschoning maakt niets aan."""
    pad = tmp_path / "leeg.db"
    monkeypatch.setenv("DATABASE_PATH", str(pad))

    assert opschonen.main([], nu=NU) == 1

    assert "mislukt" in capsys.readouterr().err
    assert _sql(pad, "SELECT name FROM sqlite_master") == []


# ── Postgres: hetzelfde werk in één transactie, met %s-parameters ──


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 0

    def execute(self, sql, params=()):
        if self.conn.faalt_op and self.conn.faalt_op in sql:
            raise RuntimeError("verbinding weg")
        self.conn.sql.append((sql, params))
        return self

    def fetchall(self):
        return (
            [{"id": "c1", "username": "anna"}] if self.conn.sql[-1][0].startswith("DELETE FROM conversations") else []
        )

    def fetchone(self):
        return {"n": 0}


class _Conn:
    def __init__(self):
        self.sql, self.commits, self.rollbacks, self.closed, self.faalt_op = [], 0, 0, 0, None

    def cursor(self, cursor_factory=None):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = 1


@pytest.fixture
def postgres(monkeypatch):
    """Een stand-in voor de (optionele) driver: elke verbinding is dezelfde _Conn."""
    import sys
    from types import SimpleNamespace

    conn = _Conn()
    extras = SimpleNamespace(RealDictCursor=object)
    psycopg2 = SimpleNamespace(extras=extras, connect=lambda uri: conn)
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg2)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras)
    monkeypatch.setattr(db, "_USE_POSTGRES", True)
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setenv("POSTGRES_URI", "postgresql://test")
    yield conn
    monkeypatch.setattr(db, "_pool", None)


def test_postgres_een_commit_en_postgres_parameters(postgres):
    opschonen.schoon_op(_grenzen())

    assert postgres.commits == 1
    statements = [sql for sql, _ in postgres.sql]
    assert all("?" not in sql for sql in statements)
    assert statements[0].startswith("DELETE FROM conversations") and "RETURNING id, username" in statements[0]
    # Het verwijderde gesprek: zijn recepten weg, zijn jonge feedback losgekoppeld (#476).
    assert any(s.startswith("DELETE FROM data_recipes WHERE username") for s in statements)
    assert any(s.startswith("UPDATE answer_feedback SET username") for s in statements)
    for tabel in opschonen.SOORTEN:
        assert any(s.startswith(f"DELETE FROM {tabel}") for s in statements)


def test_postgres_een_fout_commit_niets(postgres):
    postgres.faalt_op = "DELETE FROM workbooks"
    with pytest.raises(RuntimeError):
        opschonen.schoon_op(_grenzen())
    assert postgres.commits == 0
    assert postgres.rollbacks >= 1


def test_postgres_droog_commit_niets_en_verwijdert_niets(postgres):
    opschonen.tel(_grenzen())
    assert postgres.commits == 0
    assert all(sql.startswith("SELECT COUNT(*)") for sql, _ in postgres.sql)
