"""Twee pods die tegelijk starten, migreren om de beurt (#984).

Postgres is hier niet beschikbaar; de tests gebruiken een stand-in voor `_execute` en de verbinding en toetsen de
volgorde: slot nemen, wachten als het bezet is, werken, loslaten (ook na een fout, dan eerst een rollback).
"""

import pytest

import persistence.db as db


class Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.rij = None

    def execute(self, sql, params=()):
        log = self.conn.log
        if "pg_try_advisory_lock" in sql:
            log.append("probeer")
            self.rij = (self.conn.antwoorden.pop(0),)
        elif "pg_advisory_unlock" in sql:
            if self.conn.unlock_faalt:
                raise RuntimeError("verbinding weg")
            log.append("los")
            self.rij = (True,)
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return self.rij

    def close(self):
        pass


class Verbinding:
    def __init__(self, log):
        self.log = log
        self.antwoorden = [True]
        self.unlock_faalt = False

    def cursor(self, cursor_factory=None):
        return Cursor(self)

    def rollback(self):
        self.log.append("rollback")

    def commit(self):
        self.log.append("commit")

    def close(self):
        self.log.append("dicht")


@pytest.fixture
def postgres(monkeypatch):
    log: list = []
    monkeypatch.setattr(db, "_USE_POSTGRES", True)
    monkeypatch.setattr(db.time, "sleep", lambda s: log.append("slaap"))
    return log, Verbinding(log)


def test_slot_nemen_werken_loslaten(postgres):
    log, conn = postgres
    with db._migratielock(conn):
        log.append("werk")
    assert log == ["probeer", "werk", "rollback", "los", "commit"]


def test_een_bezet_slot_laat_de_tweede_pod_wachten(postgres):
    log, conn = postgres
    conn.antwoorden = [False, False, True]
    with db._migratielock(conn):
        log.append("werk")
    assert log[:6] == ["probeer", "slaap", "probeer", "slaap", "probeer", "werk"]


def test_het_slot_gaat_ook_los_na_een_fout(postgres):
    log, conn = postgres
    with pytest.raises(ValueError), db._migratielock(conn):
        raise ValueError("migratie stuk")
    assert log == ["probeer", "rollback", "los", "commit"], (
        "eerst rollback: een afgebroken transactie weigert de unlock"
    )


def test_mislukt_het_loslaten_dan_gaat_de_verbinding_dicht(postgres):
    log, conn = postgres
    conn.unlock_faalt = True
    with db._migratielock(conn):
        pass
    assert log[-1] == "dicht", "anders ligt een verbinding met het slot in de pool en wachten de andere pods vergeefs"


def test_zonder_slot_binnen_de_tijd_faalt_de_start(postgres, monkeypatch):
    log, conn = postgres
    conn.antwoorden = [False] * 1000
    klok = iter(range(0, 10_000, 30))
    monkeypatch.setattr(db.time, "monotonic", lambda: next(klok))
    with pytest.raises(RuntimeError, match="migratieslot"), db._migratielock(conn):
        pass
    assert "los" not in log, "een slot dat we nooit kregen, laten we ook niet los"


def test_op_sqlite_gebeurt_er_niets(monkeypatch):
    monkeypatch.setattr(db, "_USE_POSTGRES", False)
    with db._migratielock(object()):  # geen cursor, geen query: een attribuut lezen zou falen
        pass


def test_init_db_draait_onder_het_slot(tmp_path, monkeypatch):
    import contextlib
    import importlib

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    importlib.reload(db)
    gebeurtenissen = []

    @contextlib.contextmanager
    def spion(conn):
        gebeurtenissen.append("slot")
        yield
        gebeurtenissen.append("los")

    monkeypatch.setattr(db, "_migratielock", spion)
    migreer = db._migrate
    monkeypatch.setattr(db, "_migrate", lambda conn: (gebeurtenissen.append("migreer"), migreer(conn))[1])
    db.init_db()
    assert gebeurtenissen == ["slot", "migreer", "los"]
