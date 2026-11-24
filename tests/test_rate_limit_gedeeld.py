"""De limieten tellen in de database zodat meerdere pods één limiet delen (#984).

SQLite deelt niets (één proces), dus de tests zetten `deelt_staat` aan: dezelfde SQL, andere database. De
Postgres-eigen regel (advisory lock) staat in de laatste test, met een stand-in voor de verbinding.
"""

import contextlib
import hashlib
import importlib
import logging
import sqlite3
import threading

import pytest

from core.rate_limit import RateLimiter


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    monkeypatch.setattr(db, "deelt_staat", lambda: True)
    return db


def _pod(max_attempts=2, window_seconds=60, naam="test"):
    """Een eigen RateLimiter, zoals een tweede pod er een heeft: eigen geheugen, dezelfde database."""
    return RateLimiter(max_attempts=max_attempts, window_seconds=window_seconds, naam=naam)


def test_twee_pods_delen_een_limiet(db):
    pod_a, pod_b = _pod(), _pod()
    assert pod_a.probeer("anna") is None
    assert pod_b.probeer("anna") is None
    assert pod_a.probeer("anna") is not None, "de derde poging valt op pod A, ook al zaten de eerste twee op B en A"
    assert pod_b.probeer("anna") is not None


def test_een_herstart_zet_niemand_op_nul(db):
    voor = _pod()
    voor.probeer("anna")
    voor.probeer("anna")
    na = _pod()
    assert na.probeer("anna") is not None


def test_buckets_en_sleutels_zijn_gescheiden(db):
    assert _pod(1, naam="a").probeer("anna") is None
    assert _pod(1, naam="b").probeer("anna") is None, "andere limiet, eigen telling"
    assert _pod(1, naam="a").probeer("bob") is None, "andere sleutel, eigen telling"


def test_de_wachttijd_komt_uit_de_database(db):
    pod = _pod(max_attempts=1, window_seconds=30)
    assert pod.probeer("anna") is None
    wacht = _pod(1, 30).probeer("anna")
    assert 1 <= wacht <= 30
    assert 1 <= _pod(1, 30).retry_after("anna") <= 30
    assert _pod(1, 30).retry_after("bob") is None


def test_retry_after_telt_niet_mee(db):
    pod = _pod(max_attempts=2)
    for _ in range(5):
        assert pod.retry_after("anna") is None
    assert pod.probeer("anna") is None
    assert pod.probeer("anna") is None


def test_na_het_venster_mag_het_weer(db, monkeypatch):
    nu = [1_000_000.0]
    monkeypatch.setattr(db.time, "time", lambda: nu[0])
    pod = _pod(max_attempts=1, window_seconds=10)
    assert pod.probeer("anna") is None
    assert pod.probeer("anna") is not None
    nu[0] += 11
    assert pod.probeer("anna") is None


def test_de_database_bevat_de_sleutel_alleen_als_hmac_en_niet_als_kale_sha256(db, tmp_path, monkeypatch):
    """#1117: een kale sha256 van een e-mailadres of IPv4-adres is met één hash of 2^32 pogingen terug te rekenen."""
    monkeypatch.setenv("CHAT_SECRET", "test-geheim")
    sleutel = "anna@hu.nl|10.1.2.3"
    _pod().probeer(sleutel)
    conn = sqlite3.connect(tmp_path / "test.db")
    rijen = conn.execute("SELECT bucket, sleutel FROM rate_limit_hits").fetchall()
    conn.close()
    assert len(rijen) == 1
    opgeslagen = rijen[0][1]
    assert "anna" not in opgeslagen and "10.1.2.3" not in opgeslagen
    kaal = hashlib.sha256(sleutel.encode()).hexdigest()
    assert opgeslagen != kaal and kaal not in opgeslagen


def test_een_ander_geheim_is_een_andere_teller(db, monkeypatch):
    """De limiet blijft per sleutel werken zolang het geheim gelijk is; roteren zet de tellers op nul."""
    monkeypatch.setenv("CHAT_SECRET", "geheim-1")
    pod = _pod(1)
    assert pod.probeer("anna") is None
    assert pod.probeer("anna") is not None
    monkeypatch.setenv("CHAT_SECRET", "geheim-2")
    assert pod.probeer("anna") is None


def test_gelijktijdige_pods_laten_nooit_meer_door_dan_de_limiet(db):
    pods = [_pod(max_attempts=5) for _ in range(4)]
    toegestaan = []

    def werk(pod):
        toegestaan.extend(pod.probeer("anna") is None for _ in range(6))

    draden = [threading.Thread(target=werk, args=(pod,)) for pod in pods]
    for draad in draden:
        draad.start()
    for draad in draden:
        draad.join()
    assert sum(toegestaan) == 5


def test_verlopen_pogingen_gaan_weg_bij_het_opstarten(db, monkeypatch, tmp_path):
    nu = [1_000_000.0]
    monkeypatch.setattr(db.time, "time", lambda: nu[0])
    _pod(window_seconds=10).probeer("anna")
    nu[0] += 11
    db.init_db()
    conn = sqlite3.connect(tmp_path / "test.db")
    assert conn.execute("SELECT COUNT(*) FROM rate_limit_hits").fetchone()[0] == 0
    conn.close()


def test_opruimen_haalt_ook_sleutels_weg_die_niet_terugkomen(db, monkeypatch, tmp_path):
    nu = [1_000_000.0]
    monkeypatch.setattr(db.time, "time", lambda: nu[0])
    _pod(window_seconds=10).probeer("eenmalig")
    nu[0] += 11
    db.rate_limit_opruimen("test")
    conn = sqlite3.connect(tmp_path / "test.db")
    assert conn.execute("SELECT COUNT(*) FROM rate_limit_hits").fetchone()[0] == 0
    conn.close()


def test_zonder_naam_telt_het_geheugen_ook_met_gedeelde_database(db, tmp_path):
    pod = RateLimiter(max_attempts=1, window_seconds=60)
    assert pod.probeer("anna") is None
    assert pod.probeer("anna") is not None
    conn = sqlite3.connect(tmp_path / "test.db")
    assert conn.execute("SELECT COUNT(*) FROM rate_limit_hits").fetchone()[0] == 0
    conn.close()


def test_zonder_gedeelde_database_telt_het_geheugen(db, monkeypatch, tmp_path):
    monkeypatch.setattr(db, "deelt_staat", lambda: False)
    pod = _pod(max_attempts=1)
    assert pod.probeer("anna") is None
    assert pod.probeer("anna") is not None
    conn = sqlite3.connect(tmp_path / "test.db")
    assert conn.execute("SELECT COUNT(*) FROM rate_limit_hits").fetchone()[0] == 0
    conn.close()


def test_een_databasefout_valt_terug_op_het_geheugen_en_logt_een_keer(db, monkeypatch, caplog):
    def kapot(*args, **kwargs):
        raise RuntimeError("verbinding weg")

    monkeypatch.setattr(db, "rate_limit_poging", kapot)
    pod = _pod(max_attempts=2)
    with caplog.at_level(logging.WARNING, logger="core.rate_limit"):
        assert pod.probeer("anna") is None
        assert pod.probeer("anna") is None
        assert pod.probeer("anna") is not None, "de limiet geldt dan per pod, hij vervalt niet"
        assert pod.retry_after("anna") is not None
    meldingen = [r for r in caplog.records if "telt per pod" in r.getMessage()]
    assert len(meldingen) == 1
    assert "verbinding weg" not in meldingen[0].getMessage(), "alleen het soort fout, geen details"


def _geen_geheugen(pod):
    """Het geheugen van deze pod mag niet meetellen: de database gaf een antwoord."""

    def fout(key):
        pytest.fail("de pod telde in zijn eigen geheugen terwijl de database bereikbaar was")

    pod._geheugen_toestaan = fout
    return pod


def test_een_vergrendelde_database_probeert_het_opnieuw_en_telt_niet_in_het_geheugen(db, monkeypatch):
    """#1194: een voorbijgaande 'database is locked' liet een pod in zijn eigen geheugen tellen, zodat vier pods samen
    één poging te veel doorlieten."""
    aanroepen = []
    slaap = []

    def eerst_vergrendeld(*args, **kwargs):
        aanroepen.append(args)
        if len(aanroepen) == 1:
            raise sqlite3.OperationalError("database is locked")
        return 7_000

    monkeypatch.setattr(db, "rate_limit_poging", eerst_vergrendeld)
    monkeypatch.setattr("core.rate_limit.time.sleep", slaap.append)
    pod = _geen_geheugen(_pod(max_attempts=1))
    assert pod.probeer("anna") == 7, "de wachttijd komt uit de tweede poging naar de database"
    assert len(aanroepen) == 2
    assert sum(slaap) < 1


def test_een_aanhoudend_vergrendelde_database_valt_begrensd_terug_op_het_geheugen(db, monkeypatch, caplog):
    aanroepen = []
    slaap = []

    def vergrendeld(*args, **kwargs):
        aanroepen.append(args)
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "rate_limit_poging", vergrendeld)
    monkeypatch.setattr("core.rate_limit.time.sleep", slaap.append)
    pod = _pod(max_attempts=1)
    with caplog.at_level(logging.WARNING, logger="core.rate_limit"):
        assert pod.probeer("anna") is None
    assert 1 < len(aanroepen) <= 3, "een paar keer opnieuw, niet eindeloos"
    assert sum(slaap) < 1, "minder dan een seconde extra wachten"
    assert pod.probeer("anna") is not None, "daarna telt het geheugen van deze pod"
    assert any("telt per pod" in r.getMessage() for r in caplog.records)


def test_een_onbereikbare_database_valt_terug_op_het_geheugen_per_pod(db, monkeypatch, tmp_path, caplog):
    """De keuze bij een database die echt weg is (#1194): beschikbaarheid boven strengheid. Geen fout, geen herkansing,
    en de limiet geldt per pod."""
    monkeypatch.setattr(db, "_db_path", lambda: tmp_path / "bestaat-niet" / "test.db")
    slaap = []
    monkeypatch.setattr("core.rate_limit.time.sleep", slaap.append)
    pod_a, pod_b = _pod(max_attempts=1), _pod(max_attempts=1)
    with caplog.at_level(logging.WARNING, logger="core.rate_limit"):
        assert pod_a.probeer("anna") is None
        assert pod_a.probeer("anna") is not None
        assert pod_b.probeer("anna") is None, "pod B kent de telling van pod A niet"
        assert pod_b.probeer("anna") is not None
    assert slaap == [], "een database die niet opent, is geen vergrendeling: meteen terugvallen"
    assert any("telt per pod" in r.getMessage() for r in caplog.records)


def test_een_mislukte_opruiming_gooit_een_getelde_poging_niet_weg(db, monkeypatch, caplog):
    """De opruiming na het tellen stond in dezelfde `try`: faalde zij, dan telde de poging in de database én in het
    geheugen (#1194)."""
    nu = [1_000.0]
    monkeypatch.setattr("core.rate_limit.time.monotonic", lambda: nu[0])

    def kapot(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "rate_limit_opruimen", kapot)
    pod = _geen_geheugen(_pod(max_attempts=1, window_seconds=60))
    nu[0] += 61
    with caplog.at_level(logging.WARNING, logger="core.rate_limit"):
        assert pod.probeer("anna") is None
    assert _pod(max_attempts=1).probeer("anna") is not None, "de poging staat in de database"
    assert not any("telt per pod" in r.getMessage() for r in caplog.records), "de telling lukte gewoon"


def test_postgres_neemt_een_advisory_lock_per_bucket_en_sleutel(monkeypatch):
    import persistence.db as db

    uitgevoerd = []

    class Rij(dict):
        pass

    class Cursor:
        def __init__(self, sql):
            self.sql = sql

        def fetchone(self):
            return Rij(n=0, eerste=None) if "COUNT(*)" in self.sql else None

    class Verbinding:
        def commit(self):
            uitgevoerd.append(("commit", ()))

    def nep_execute(conn, sql, params=()):
        uitgevoerd.append((sql, params))
        return Cursor(sql)

    @contextlib.contextmanager
    def nep_connection():
        yield Verbinding()

    monkeypatch.setattr(db, "_USE_POSTGRES", True)
    monkeypatch.setattr(db, "_connection", nep_connection)
    monkeypatch.setattr(db, "_execute", nep_execute)
    assert db.rate_limit_poging("login", "abc", 5, 60_000) is None
    sqls = [s for s, _ in uitgevoerd]
    assert "pg_advisory_xact_lock" in sqls[0]
    assert uitgevoerd[0][1] == ("login:abc",)
    assert sqls.index("commit") > max(i for i, s in enumerate(sqls) if "INSERT" in s)
