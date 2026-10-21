"""Verwijder al mijn gegevens (#646, deel 2 van #485): alles onder het eigen account weg, niets van een ander.

Twee accounts in CHAT_USERS, elk met rijen van alle zes soorten. Na `DELETE /api/mijn-gegevens` van Anna heeft zij
nergens nog een rij, staan die van Bert en de losgekoppelde feedback (`verwijderd`, #476) er ongewijzigd, is haar
token ingetrokken en weet het geheugen niets meer van haar. Tokens worden direct gemaakt, niet via de login: de
login-limiter telt over de hele testrun mee.
"""

import logging
import sqlite3
import time
from collections import OrderedDict

import pytest
from fastapi.testclient import TestClient

from agent import recepten
from core import foutmeldingen
from persistence import db, export, verwijderen
from tests.test_mijn_gegevens_export import _vul

_URL = "/api/mijn-gegevens"
_BEVESTIGD = {"bevestig": "verwijder"}
_SOORTEN = ["conversations", "workbooks", "feedback", "algemene_feedback", "answer_feedback", "data_recipes"]
_ZESMAAL_NUL = dict.fromkeys(_SOORTEN, 0)
# Anna's rijen per soort na _vul_anna: elk aantal anders, zodat een verwisselde sleutel opvalt.
_ANNA = {
    "conversations": 3,
    "workbooks": 2,
    "feedback": 4,
    "algemene_feedback": 5,
    "answer_feedback": 6,
    "data_recipes": 1,
}
# Bert's rijen na _vul.
_BERT = {
    "conversations": 2,
    "workbooks": 2,
    "feedback": 1,
    "algemene_feedback": 1,
    "answer_feedback": 1,
    "data_recipes": 1,
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """De app met inloggen aan voor anna en bert, zonder modules te herladen: niets blijft achter."""
    import routes.auth
    import server
    from core import auth

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(auth, "USERS", {"anna": "wachtwoord-a", "bert": "wachtwoord-b"})
    monkeypatch.setattr(auth, "AUTH_ENABLED", True)
    monkeypatch.setattr(routes.auth, "_oidc_user_cache", OrderedDict())
    db.init_db()
    return TestClient(server.app)


def _token(gebruiker: str, start: int | None = None) -> str:
    from core import auth

    return auth.make_token(gebruiker, start)


def _verwijder(client: TestClient, token: str | None, body: object = _BEVESTIGD):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if body is None:
        return client.request("DELETE", _URL, headers=headers)
    return client.request("DELETE", _URL, headers=headers, json=body)


def _werkt(client: TestClient, token: str) -> bool:
    status = client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"}).status_code
    assert status in (200, 401)
    return status == 200


def _vul_anna() -> None:
    """Alle soorten, met per soort een eigen aantal (_ANNA)."""
    _vul("anna", "ANNA-UNIEK")
    db.upsert_conversation("anna", "anna-c3", "Derde", 1_700_000_200, [])
    for i in range(3):
        db.add_feedback("anna", "anna-w1", "report", "Rapport", {"nuttig": str(i)})
    for i in range(4):
        db.add_algemene_feedback("anna", "probleem", f"extra-{i}", "/rapporten")
    for i in range(5):
        db.upsert_answer_feedback("anna", "anna-c2", 10 + i, "omhoog", "", {"vraag": f"extra-trace-{i}"})


def _aantal(tabel: str, gebruiker: str) -> int:
    with db._connection() as conn:
        return db._execute(conn, f"SELECT COUNT(*) AS n FROM {tabel} WHERE username = ?", (gebruiker,)).fetchone()["n"]


def _aantallen(gebruiker: str) -> dict[str, int]:
    return {tabel: _aantal(tabel, gebruiker) for tabel in _SOORTEN}


def _rijen(gebruiker: str) -> dict[str, list[tuple]]:
    """Elke rij van deze gebruiker per tabel, volledig en gesorteerd: om 'ongewijzigd' te toetsen."""
    with db._connection() as conn:
        return {
            tabel: sorted(
                tuple(r) for r in db._execute(conn, f"SELECT * FROM {tabel} WHERE username = ?", (gebruiker,))
            )
            for tabel in _SOORTEN
        }


def _ingetrokken() -> int:
    with db._connection() as conn:
        return db._execute(conn, "SELECT COUNT(*) AS n FROM revoked_tokens").fetchone()["n"]


def _maak_losgekoppelde_feedback() -> None:
    """Een gesprek van carla met feedback, verwijderd: de feedback hangt daarna aan `verwijderd` (#476)."""
    db.upsert_conversation("carla", "carla-c1", "Weg", 1_700_000_000, [])
    db.upsert_answer_feedback("carla", "carla-c1", 1, "omlaag", "losgekoppeld-tekst", {"vraag": "losgekoppeld"})
    db.delete_conversation("carla", "carla-c1")
    assert _aantal("answer_feedback", db.VERWIJDERDE_GEBRUIKER) == 1


# ── 1. Alles van Anna weg, niets van een ander ───────────────────────────────


def test_alles_van_de_gebruiker_weg_met_de_aantallen_per_soort(client):
    _vul_anna()
    _vul("bert", "BERT-UNIEK")
    _maak_losgekoppelde_feedback()
    assert _aantallen("anna") == _ANNA
    bert_voor = _rijen("bert")
    losgekoppeld_voor = _rijen(db.VERWIJDERDE_GEBRUIKER)

    response = _verwijder(client, _token("anna"))

    assert response.status_code == 200
    assert response.json() == {"ok": True, "verwijderd": _ANNA}
    assert _aantallen("anna") == _ZESMAAL_NUL
    assert _rijen("bert") == bert_voor
    assert _aantallen("bert") == _BERT
    assert _rijen(db.VERWIJDERDE_GEBRUIKER) == losgekoppeld_voor


# ── 2. Bevestiging en sessie ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "body",
    [None, {}, {"bevestig": ""}, {"bevestig": "ja"}, {"bevestig": "Verwijder"}, {"bevestig": " verwijder"}],
    ids=["zonder body", "leeg object", "lege tekst", "ja", "hoofdletter", "spatie"],
)
def test_zonder_de_juiste_bevestiging_422_en_niets_weg(client, body):
    _vul_anna()
    token = _token("anna")

    response = _verwijder(client, token, body)

    assert response.status_code == 422
    assert response.json() == {"detail": foutmeldingen.ONGELDIGE_INVOER}
    assert _aantallen("anna") == _ANNA
    assert _werkt(client, token)
    assert _ingetrokken() == 0


@pytest.mark.parametrize(
    ("token", "body"),
    [(None, _BEVESTIGD), ("ongeldig", _BEVESTIGD), (None, None), ("ongeldig", {"bevestig": "ja"})],
    ids=["zonder token", "ongeldig token", "zonder token en body", "ongeldig token, foute bevestiging"],
)
def test_zonder_geldige_sessie_401_en_niets_weg(client, token, body):
    """De sessie wordt vóór de body gecontroleerd: zonder sessie altijd 401, ook met een foute bevestiging."""
    _vul_anna()

    response = _verwijder(client, token, body)

    assert response.status_code == 401
    assert _aantallen("anna") == _ANNA


def test_een_ingetrokken_token_401_en_niets_weg(client):
    from core import auth

    _vul_anna()
    token = _token("anna")
    auth.revoke_token(token)

    assert _verwijder(client, token).status_code == 401
    assert _aantallen("anna") == _ANNA


# ── 3. Token ingetrokken, tweede token idempotent ────────────────────────────


def test_het_eigen_token_is_daarna_ingetrokken_een_ander_token_werkt_en_is_idempotent(client):
    _vul_anna()
    token = _token("anna")
    ander_apparaat = _token("anna", start=int(time.time()) - 60)
    assert token != ander_apparaat

    assert _verwijder(client, token).status_code == 200

    assert not _werkt(client, token)
    assert _ingetrokken() == 1
    assert _werkt(client, ander_apparaat)
    tweede = _verwijder(client, ander_apparaat)
    assert tweede.status_code == 200
    assert tweede.json() == {"ok": True, "verwijderd": _ZESMAAL_NUL}


# ── 4. Het geheugen vergeet de gebruiker ─────────────────────────────────────


def test_het_geheugen_vergeet_recepten_en_sram_gegevens_van_alleen_deze_gebruiker(client):
    import routes.auth

    _vul_anna()
    recepten.onthoud("anna", "key-ANNA-UNIEK", {"laad": ["query_data", {"id": "ANNA-UNIEK"}]})
    recepten.onthoud("anna", "nooit-bewaard", {"laad": ["get_cbs_data", {"dataset_id": "85423NED"}]})
    recepten.onthoud("bert", "key-bert", {"laad": ["get_duo_data", {"id": "b"}]})
    routes.auth._store_oidc_user("anna", {"name": "Anna"})
    routes.auth._store_oidc_user("bert", {"name": "Bert"})

    assert _verwijder(client, _token("anna")).status_code == 200

    assert [sleutel for sleutel in recepten._wachtend if sleutel[0] == "anna"] == []
    assert ("bert", "key-bert") in recepten._wachtend
    assert "anna" not in routes.auth._oidc_user_cache
    assert routes.auth._get_oidc_user("bert") == {"name": "Bert"}


# ── 5. Eén transactie ────────────────────────────────────────────────────────


def _faal_bij_de_vierde_delete(monkeypatch) -> None:
    echte = db._execute
    deletes = {"n": 0}

    def execute(conn, sql, params=()):
        if sql.lstrip().upper().startswith("DELETE FROM"):
            deletes["n"] += 1
            if deletes["n"] == 4:
                raise sqlite3.OperationalError("database is locked")
        return echte(conn, sql, params)

    monkeypatch.setattr(db, "_execute", execute)


def test_een_fout_halverwege_laat_alle_rijen_staan(client, monkeypatch):
    _vul_anna()
    with monkeypatch.context() as m, pytest.raises(sqlite3.OperationalError):
        _faal_bij_de_vierde_delete(m)
        verwijderen.verwijder_alles("anna")

    assert _aantallen("anna") == _ANNA


def test_een_fout_halverwege_geeft_500_en_het_token_blijft_geldig(client, monkeypatch):
    import server

    _vul_anna()
    token = _token("anna")
    zonder_raise = TestClient(server.app, raise_server_exceptions=False)
    with monkeypatch.context() as m:
        _faal_bij_de_vierde_delete(m)
        response = _verwijder(zonder_raise, token)

    assert response.status_code == 500
    assert _aantallen("anna") == _ANNA
    assert _ingetrokken() == 0
    assert _werkt(client, token)
    # Opnieuw proberen lukt.
    assert _verwijder(client, token).json() == {"ok": True, "verwijderd": _ANNA}


# ── 6. Zonder login, onbekende naam, `verwijderd` ────────────────────────────


def test_zonder_login_404_en_niets_weg(client, monkeypatch):
    from core import auth

    monkeypatch.setattr(auth, "AUTH_ENABLED", False)
    _vul(auth.FALLBACK_USER, "GAST-UNIEK")
    gast_voor = _aantallen(auth.FALLBACK_USER)

    response = _verwijder(client, None)

    assert response.status_code == 404
    assert response.json() == {"detail": "Zonder inloggen is er geen eigen account om te verwijderen."}
    assert _aantallen(auth.FALLBACK_USER) == gast_voor
    assert _ingetrokken() == 0


def test_een_naam_buiten_chat_users_wist_alleen_zijn_eigen_rijen(client):
    """Een ondertekend token komt alleen na een login; OIDC-gebruikers staan nooit in CHAT_USERS."""
    _vul_anna()
    _vul("bert", "BERT-UNIEK")
    _vul("dirk@hu.nl", "DIRK-UNIEK")
    anna_voor, bert_voor = _rijen("anna"), _rijen("bert")

    response = _verwijder(client, _token("dirk@hu.nl"))

    assert response.status_code == 200
    assert response.json()["verwijderd"]["conversations"] == 2
    assert _aantallen("dirk@hu.nl") == _ZESMAAL_NUL
    assert (_rijen("anna"), _rijen("bert")) == (anna_voor, bert_voor)


def test_een_account_dat_verwijderd_heet_laat_de_losgekoppelde_feedback_staan(client):
    _maak_losgekoppelde_feedback()
    losgekoppeld_voor = _rijen(db.VERWIJDERDE_GEBRUIKER)

    response = _verwijder(client, _token(db.VERWIJDERDE_GEBRUIKER))

    assert response.status_code == 200
    assert response.json()["verwijderd"]["answer_feedback"] == 0
    assert _rijen(db.VERWIJDERDE_GEBRUIKER) == losgekoppeld_voor


# ── 7. Log en antwoord: alleen aantallen ─────────────────────────────────────


def test_log_en_antwoord_noemen_alleen_aantallen(client, caplog):
    _vul_anna()
    recepten.onthoud("anna", "nooit-bewaard", {"laad": ["get_cbs_data", {"dataset_id": "RECEPT-UNIEK"}]})
    caplog.set_level(logging.INFO)

    response = _verwijder(client, _token("anna"))

    log = "\n".join(r.getMessage() for r in caplog.records)
    # Elke opgeslagen tekst van Anna (titel, berichten, HTML, toelichting, trace, recept) draagt ANNA-UNIEK.
    for tekst in ("ANNA-UNIEK", "extra-trace", "RECEPT-UNIEK", "anna"):
        assert tekst not in log
        assert tekst not in response.text
    regels = [r.getMessage() for r in caplog.records if r.name == "routes.mijn_gegevens"]
    assert len(regels) == 1
    assert regels[0] == (
        "verwijder mijn gegevens: conversations=3, workbooks=2, feedback=4, algemene_feedback=5, "
        "answer_feedback=6, data_recipes=1"
    )
    assert next(r for r in caplog.records if r.name == "routes.mijn_gegevens").levelno == logging.INFO


# ── 8. Geen tabel vergeten ───────────────────────────────────────────────────


def test_elke_tabel_met_een_gebruikersnaam_wordt_gewist_en_geexporteerd(tmp_path, monkeypatch):
    """Een nieuwe tabel met `username` moet in verwijderen én in de export, anders faalt deze test."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    db.init_db()
    with db._connection() as conn:
        tabellen = [r["name"] for r in db._execute(conn, "SELECT name FROM sqlite_master WHERE type = 'table'")]
        met_gebruiker = {
            t for t in tabellen if any(k["name"] == "username" for k in db._execute(conn, f"PRAGMA table_info({t})"))
        }

    assert met_gebruiker == set(_SOORTEN)
    assert list(verwijderen.DELETES) == list(export.SOORTEN) == _SOORTEN


def test_elke_delete_filtert_op_de_gebruiker():
    for soort, sql in verwijderen.DELETES.items():
        assert sql == f"DELETE FROM {soort} WHERE username = ?"
