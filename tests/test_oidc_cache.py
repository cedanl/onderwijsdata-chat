"""De SRAM-gebruikersinfo staat in de database en is begrensd in tijd en omvang (#487 privacy M4, #984).

Ze stond in `_oidc_user_cache`, een OrderedDict in het geheugen van de pod: een tweede pod vond de gebruiker niet en een
herstart vergat iedereen. Nu staat ze in de tabel `oidc_gebruikers` onder een pseudoniem van de accountnaam. Een rij
vervalt na SESSION_MAX (wandklok, `time.time`), boven het maximum gaat de langst niet gebruikte gebruiker eruit, de
opschoning ruimt verlopen rijen op, en uitloggen of "verwijder al mijn gegevens" (in zijn transactie, #1209) haalt de
rij weg.
"""

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.auth import SESSION_MAX
from persistence import db, opschonen
from routes import auth


@pytest.fixture(autouse=True)
def lege_database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "oidc.db"))
    db.init_db()


def _klok(monkeypatch, start: float = 1_800_000_000.0):
    """Een vaste wandklok voor routes.auth; de database krijgt de tijd van de aanroeper mee."""
    nu = {"t": start}
    monkeypatch.setattr(auth.time, "time", lambda: nu["t"])
    return nu


def _rijen() -> list[dict]:
    with db._connection() as conn:
        return [dict(r) for r in db._execute(conn, "SELECT * FROM oidc_gebruikers ORDER BY gebruikt")]


def test_bewaart_en_geeft_terug():
    auth._store_oidc_user("anna@hu.nl", {"name": "Anna", "organisatie": "HU"})
    assert auth._get_oidc_user("anna@hu.nl") == {"name": "Anna", "organisatie": "HU"}
    assert auth._get_oidc_user("onbekend") is None


def test_er_is_geen_gebruikerscache_in_het_geheugen():
    assert not hasattr(auth, "_oidc_user_cache")
    assert not [naam for naam, waarde in vars(auth).items() if isinstance(waarde, dict) and naam.startswith("_oidc")]


def test_de_rij_staat_onder_een_pseudoniem_niet_onder_de_naam():
    auth._store_oidc_user("anna@hu.nl", {"name": "Anna"})
    (rij,) = _rijen()
    assert rij["sleutel"].startswith("h1:")
    assert "anna" not in rij["sleutel"]
    assert json.loads(rij["gegevens"]) == {"name": "Anna"}


def test_login_export_en_verwijderen_delen_een_sleutel():
    """#1209: de export en het verwijderen (persistence) vinden de rij via `db.oidc_sleutel`, dezelfde afleiding als de
    login, met het domein `oidc_gebruiker`: een ander pseudoniem dan in `tokengebruik`."""
    from core.pseudoniem import pseudoniem

    auth._store_oidc_user("anna@hu.nl", {"name": "Anna"})
    (rij,) = _rijen()
    assert rij["sleutel"] == db.oidc_sleutel("anna@hu.nl") == pseudoniem("oidc_gebruiker", "anna@hu.nl")
    assert auth._oidc_sleutel("anna@hu.nl") == db.oidc_sleutel("anna@hu.nl")
    assert db.oidc_sleutel("anna@hu.nl") != db.tokengebruik_sleutel("anna@hu.nl")


def _tweede_exemplaar():
    """routes/auth.py nog een keer geladen, als losse module: een tweede app-exemplaar zonder gedeeld geheugen."""
    spec = importlib.util.spec_from_file_location("routes_auth_tweede", Path(auth.__file__))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "routes"
    sys.modules["routes_auth_tweede"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules["routes_auth_tweede"]
    return module


def test_een_tweede_exemplaar_op_dezelfde_database_vindt_de_gebruiker():
    tweede = _tweede_exemplaar()
    assert tweede is not auth

    auth._store_oidc_user("anna@hu.nl", {"name": "Anna", "org": "hu"})
    assert tweede._get_oidc_user("anna@hu.nl") == {"name": "Anna", "org": "hu"}

    tweede.vergeet_oidc_gebruiker("anna@hu.nl")
    assert auth._get_oidc_user("anna@hu.nl") is None


def test_een_rij_vervalt_na_de_maximale_sessieduur(monkeypatch):
    nu = _klok(monkeypatch)
    auth._store_oidc_user("anna@hu.nl", {"name": "Anna"})
    assert _rijen()[0]["expires_at"] == int(nu["t"] + SESSION_MAX)
    nu["t"] += SESSION_MAX - 1
    assert auth._get_oidc_user("anna@hu.nl") == {"name": "Anna"}
    nu["t"] += 2
    assert auth._get_oidc_user("anna@hu.nl") is None
    assert _rijen() == []


def test_opnieuw_inloggen_verlengt_de_vervaltijd(monkeypatch):
    nu = _klok(monkeypatch)
    auth._store_oidc_user("anna@hu.nl", {"name": "Anna"})
    nu["t"] += SESSION_MAX - 10
    auth._store_oidc_user("anna@hu.nl", {"name": "Anna B"})
    nu["t"] += 20
    assert auth._get_oidc_user("anna@hu.nl") == {"name": "Anna B"}


def test_boven_het_maximum_gaat_de_langst_niet_gebruikte_eruit(monkeypatch):
    nu = _klok(monkeypatch)
    monkeypatch.setattr(auth, "_OIDC_CACHE_MAX", 2)
    auth._store_oidc_user("a", {"n": 1})
    nu["t"] += 1
    auth._store_oidc_user("b", {"n": 2})
    nu["t"] += 1
    auth._get_oidc_user("a")  # a is weer de jongste
    nu["t"] += 1
    auth._store_oidc_user("c", {"n": 3})
    assert len(_rijen()) == 2
    assert auth._get_oidc_user("b") is None
    assert auth._get_oidc_user("a") == {"n": 1}
    assert auth._get_oidc_user("c") == {"n": 3}


def test_het_maximum_van_duizend_houdt(monkeypatch):
    nu = _klok(monkeypatch)
    assert auth._OIDC_CACHE_MAX == 1000
    auth._store_oidc_user("gebruiker-0", {"n": 0})
    # 998 rijen ertussen in één transactie, zoals de functie ze schrijft: duizend keer inloggen duurt op SQLite minuten.
    with db._connection() as conn:
        for i in range(1, 999):
            db._execute(
                conn,
                "INSERT INTO oidc_gebruikers (sleutel, gegevens, expires_at, gebruikt) VALUES (?, ?, ?, ?)",
                (
                    auth._oidc_sleutel(f"gebruiker-{i}"),
                    json.dumps({"n": i}),
                    int(nu["t"] + SESSION_MAX),
                    int(nu["t"] * 1000) + i,
                ),
            )
        conn.commit()
    nu["t"] += 1
    auth._store_oidc_user("gebruiker-999", {"n": 999})
    assert len(_rijen()) == 1000
    nu["t"] += 1
    auth._store_oidc_user("gebruiker-1000", {"n": 1000})
    assert len(_rijen()) == 1000
    assert auth._get_oidc_user("gebruiker-0") is None  # de langst niet gebruikte
    assert auth._get_oidc_user("gebruiker-1") == {"n": 1}
    assert auth._get_oidc_user("gebruiker-1000") == {"n": 1000}


def test_verlopen_rijen_verdwijnen_bij_het_opslaan_van_een_ander(monkeypatch):
    nu = _klok(monkeypatch)
    auth._store_oidc_user("oud", {"n": 1})
    nu["t"] += SESSION_MAX + 1
    auth._store_oidc_user("nieuw", {"n": 2})
    assert [json.loads(r["gegevens"]) for r in _rijen()] == [{"n": 2}]


def test_de_opschoning_verwijdert_verlopen_rijen(monkeypatch):
    nu = _klok(monkeypatch)
    auth._store_oidc_user("oud", {"n": 1})
    nu["t"] += 10
    auth._store_oidc_user("jong", {"n": 2})

    moment = datetime.fromtimestamp(nu["t"] - 10 + SESSION_MAX + 1, UTC)
    g = opschonen.grenzen(opschonen.termijnen(90, 365), moment)
    assert "oidc_gebruikers" in opschonen.SOORTEN
    assert opschonen.tel(g)["oidc_gebruikers"] == 1
    assert opschonen.schoon_op(g)["oidc_gebruikers"] == 1
    assert [json.loads(r["gegevens"]) for r in _rijen()] == [{"n": 2}]


def test_de_start_ruimt_verlopen_rijen_op(monkeypatch):
    _klok(monkeypatch, start=1_000_000.0)  # lang geleden: verlopen bij de echte klok van init_db
    auth._store_oidc_user("oud", {"n": 1})
    assert len(_rijen()) == 1
    db.init_db()
    assert _rijen() == []


def test_vergeten_haalt_alleen_deze_gebruiker_weg():
    auth._store_oidc_user("anna", {"name": "Anna"})
    auth._store_oidc_user("bert", {"name": "Bert"})
    auth.vergeet_oidc_gebruiker("anna")
    assert auth._get_oidc_user("anna") is None
    assert auth._get_oidc_user("bert") == {"name": "Bert"}


def test_een_databasefout_bij_lezen_gaat_door_als_fout(monkeypatch):
    """Een storing is geen onbekende gebruiker: /user geeft dan 500, geen kale gebruiker (#508)."""

    def kapot(*_args):
        raise RuntimeError("database weg")

    monkeypatch.setattr(db, "oidc_gebruiker_lees", kapot)
    with pytest.raises(RuntimeError):
        auth._get_oidc_user("anna@hu.nl")
