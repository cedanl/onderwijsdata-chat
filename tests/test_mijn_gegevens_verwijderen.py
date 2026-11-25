"""Verwijder al mijn gegevens (#646, deel 2 van #485): alles onder het eigen account weg, niets van een ander.

Twee accounts in CHAT_USERS, elk met rijen van alle acht soorten (sinds #1209 ook het SRAM-profiel). Na
`DELETE /api/mijn-gegevens` van Anna heeft zij nergens nog een rij, staan die van Bert er ongewijzigd, zijn al haar
tokens ingetrokken (#786) en weet het geheugen niets meer van haar. Tokens worden direct gemaakt, niet via de login: de
login-limiter telt over de hele testrun mee.
"""

import logging
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from agent import beurtbewijs, recepten
from core import foutmeldingen
from core.pseudoniem import pseudoniem
from core.tokenbudget import _sleutel
from persistence import db, export, verwijderen
from tests.test_mijn_gegevens_export import _vul

_URL = "/api/mijn-gegevens"
_BEVESTIGD = {"bevestig": "verwijder"}
_SOORTEN = [
    "conversations",
    "workbooks",
    "feedback",
    "algemene_feedback",
    "data_recipes",
    "beurtbewijs",
    "tokengebruik",
    "oidc_gebruiker",
]
_ALLES_NUL = dict.fromkeys(_SOORTEN, 0)
# Anna's rijen per soort na _vul_anna: elk aantal anders, zodat een verwisselde sleutel opvalt.
_ANNA = {
    "conversations": 3,
    "workbooks": 2,
    "feedback": 4,
    "algemene_feedback": 5,
    "data_recipes": 1,
    "beurtbewijs": 2,
    "tokengebruik": 3,
    "oidc_gebruiker": 1,
}
# Bert's rijen na _vul.
_BERT = {
    "conversations": 2,
    "workbooks": 2,
    "feedback": 1,
    "algemene_feedback": 1,
    "data_recipes": 1,
    "beurtbewijs": 1,
    "tokengebruik": 1,
    "oidc_gebruiker": 1,
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """De app met inloggen aan voor anna en bert, zonder modules te herladen: niets blijft achter."""
    import server
    from core import auth

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(auth, "USERS", {"anna": "wachtwoord-a", "bert": "wachtwoord-b"})
    monkeypatch.setattr(auth, "AUTH_ENABLED", True)
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
    db.save_beurtbewijs(
        "anna",
        "anna-c2",
        {
            "hash-extra": {
                "lineage": {},
                "rekenbewijs": [],
                "created_at": "2026-11-03T10:00:00+00:00",
            }
        },
    )
    for dag in ("2026-11-03", "2026-11-04"):
        db.tokengebruik_boek(_sleutel("anna"), dag, 10)


# De soort `oidc_gebruiker` is één rij in de tabel `oidc_gebruikers` (#984, #1209); de andere soorten heten als hun tabel.
_TABEL = {"oidc_gebruiker": "oidc_gebruikers"}


def _filter(soort: str, gebruiker: str) -> tuple[str, str, tuple]:
    """`tokengebruik` en het SRAM-profiel staan onder een pseudoniem van de naam (#1112, #984), de andere tabellen onder
    de naam zelf. Het pseudoniem wordt hier zelf afgeleid, los van de code onder test."""
    tabel = _TABEL.get(soort, soort)
    if soort == "tokengebruik":
        return tabel, "sleutel = ?", (_sleutel(gebruiker),)
    if soort == "oidc_gebruiker":
        return tabel, "sleutel = ?", (pseudoniem("oidc_gebruiker", gebruiker),)
    return tabel, "username = ?", (gebruiker,)


def _aantal(soort: str, gebruiker: str) -> int:
    tabel, waar, params = _filter(soort, gebruiker)
    with db._connection() as conn:
        return db._execute(conn, f"SELECT COUNT(*) AS n FROM {tabel} WHERE {waar}", params).fetchone()["n"]


def _aantallen(gebruiker: str) -> dict[str, int]:
    return {soort: _aantal(soort, gebruiker) for soort in _SOORTEN}


def _rijen(gebruiker: str) -> dict[str, list[tuple]]:
    """Elke rij van deze gebruiker per soort, volledig en gesorteerd: om 'ongewijzigd' te toetsen. Van het SRAM-profiel
    niet de kolom `gebruikt`: die schuift bij elk lezen op (#487)."""
    rijen = {}
    with db._connection() as conn:
        for soort in _SOORTEN:
            tabel, waar, params = _filter(soort, gebruiker)
            kolommen = "sleutel, gegevens, expires_at" if soort == "oidc_gebruiker" else "*"
            sql = f"SELECT {kolommen} FROM {tabel} WHERE {waar}"
            rijen[soort] = sorted(tuple(r) for r in db._execute(conn, sql, params))
    return rijen


def _ingetrokken() -> int:
    """Intrekkingen van één token (uitloggen) plus die van alle tokens van een account (#786)."""
    with db._connection() as conn:
        return sum(
            db._execute(conn, f"SELECT COUNT(*) AS n FROM {tabel}").fetchone()["n"]
            for tabel in ("revoked_tokens", "revoked_users")
        )


# ── 1. Alles van Anna weg, niets van een ander ───────────────────────────────


def test_alles_van_de_gebruiker_weg_met_de_aantallen_per_soort(client):
    _vul_anna()
    _vul("bert", "BERT-UNIEK")
    assert _aantallen("anna") == _ANNA
    bert_voor = _rijen("bert")

    response = _verwijder(client, _token("anna"))

    assert response.status_code == 200
    assert response.json() == {"ok": True, "verwijderd": _ANNA}
    assert _aantallen("anna") == _ALLES_NUL
    assert _rijen("bert") == bert_voor
    assert _aantallen("bert") == _BERT


def test_van_de_bronregels_in_de_bewijsrijen_blijft_niets_over(client):
    """#987: de bronregels staan in de rij zelf, dus ze gaan met de rij mee."""
    _vul_anna()
    _vul("bert", "BERT-UNIEK")

    _verwijder(client, _token("anna"))

    with db._connection() as conn:
        bronnen = [r["bronnen"] for r in db._execute(conn, "SELECT bronnen FROM beurtbewijs")]
    assert bronnen and not any("ANNA-UNIEK" in b for b in bronnen)
    assert any("BERT-UNIEK" in b for b in bronnen)


def test_van_de_figuurstappen_in_de_bewijsrijen_blijft_niets_over(client):
    """#993: de stappen achter de figuren staan in de rij zelf, dus ze gaan met de rij mee."""
    _vul_anna()
    _vul("bert", "BERT-UNIEK")

    _verwijder(client, _token("anna"))

    with db._connection() as conn:
        figuren = [r["figuren"] for r in db._execute(conn, "SELECT figuren FROM beurtbewijs")]
    assert figuren and not any("ANNA-UNIEK" in f for f in figuren)
    assert any("BERT-UNIEK" in f for f in figuren)


def test_het_tokengebruik_van_de_gebruiker_gaat_mee_dat_van_een_ander_blijft(client):
    """#1074: het verbruik per dag staat onder een pseudoniem van de naam (#1112), niet onder `username`; het hoort
    toch bij het account. De export toont alleen de eigen dagen, het verwijderen wist alleen die, met het aantal."""
    from core import tokenbudget

    db.tokengebruik_boek(tokenbudget._sleutel("anna"), "2026-11-01", 100)
    db.tokengebruik_boek(tokenbudget._sleutel("anna"), "2026-11-02", 200)
    db.tokengebruik_boek(tokenbudget._sleutel("bert"), "2026-11-02", 999)
    anna, bert = _token("anna"), _token("bert")

    export = client.get("/api/mijn-gegevens/export", headers={"Authorization": f"Bearer {anna}"}).json()
    assert export["tokengebruik"] == [{"dag": "2026-11-01", "eenheden": 100}, {"dag": "2026-11-02", "eenheden": 200}]

    response = _verwijder(client, anna)

    assert response.json()["verwijderd"]["tokengebruik"] == 2
    assert tokenbudget.gebruik("anna") == (0, 0)
    assert _aantal("tokengebruik", "anna") == 0
    with db._connection() as conn:
        over = [tuple(r) for r in db._execute(conn, "SELECT sleutel, dag, eenheden FROM tokengebruik")]
    assert over == [(tokenbudget._sleutel("bert"), "2026-11-02", 999)]
    export_bert = client.get("/api/mijn-gegevens/export", headers={"Authorization": f"Bearer {bert}"}).json()
    assert export_bert["tokengebruik"] == [{"dag": "2026-11-02", "eenheden": 999}]


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


# ── 3. Alle tokens van het account ingetrokken (#786) ─────────────────────


def test_alle_tokens_van_het_account_zijn_daarna_ingetrokken_die_van_een_ander_niet(client):
    _vul_anna()
    token = _token("anna")
    ander_apparaat = _token("anna", start=int(time.time()) - 60)
    bert = _token("bert")
    assert token != ander_apparaat

    assert _verwijder(client, token).status_code == 200

    assert not _werkt(client, token)
    assert not _werkt(client, ander_apparaat)
    assert _werkt(client, bert)
    assert _ingetrokken() == 1
    assert _verwijder(client, ander_apparaat).status_code == 401


# ── 4. Het geheugen vergeet de gebruiker ─────────────────────────────────────


def test_het_geheugen_vergeet_recepten_bewijsrijen_en_sram_gegevens_van_alleen_deze_gebruiker(client):
    import routes.auth

    _vul_anna()
    recepten.onthoud("anna", "key-ANNA-UNIEK", {"laad": ["query_data", {"id": "ANNA-UNIEK"}]})
    recepten.onthoud("anna", "nooit-bewaard", {"laad": ["get_cbs_data", {"dataset_id": "85423NED"}]})
    recepten.onthoud("bert", "key-bert", {"laad": ["get_duo_data", {"id": "b"}]})
    for gebruiker in ("anna", "bert"):  # een antwoord dat nog niet is opgeslagen (ADR-009)
        beurtbewijs._klaar[gebruiker, "hash-nooit-bewaard"] = {}
    routes.auth._store_oidc_user("anna", {"name": "Anna"})
    routes.auth._store_oidc_user("bert", {"name": "Bert"})

    assert _verwijder(client, _token("anna")).status_code == 200

    assert [sleutel for sleutel in recepten._wachtend if sleutel[0] == "anna"] == []
    assert ("bert", "key-bert") in recepten._wachtend
    assert list(beurtbewijs._klaar) == [("bert", "hash-nooit-bewaard")]
    assert routes.auth._get_oidc_user("anna") is None
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


def _faal_bij_het_sram_profiel(monkeypatch) -> None:
    """De DELETE van het SRAM-profiel faalt: die komt als laatste in de transactie (#1209)."""
    echte = db._execute

    def execute(conn, sql, params=()):
        if sql.lstrip().upper().startswith("DELETE FROM OIDC_GEBRUIKERS WHERE SLEUTEL"):
            raise sqlite3.OperationalError("database is locked")
        return echte(conn, sql, params)

    monkeypatch.setattr(db, "_execute", execute)


def test_het_sram_profiel_gaat_mee_in_de_transactie_en_een_fout_daar_laat_alles_staan(client, monkeypatch):
    """#1209: het SRAM-profiel ging na de transactie weg, apart; faalde dat, dan waren de rijen al weg. Nu is het de
    laatste DELETE in dezelfde transactie: faalt die, dan blijven alle rijen en het profiel staan en blijven de tokens
    geldig, zodat opnieuw proberen kan."""
    import routes.auth
    import server

    _vul_anna()
    token = _token("anna")
    zonder_raise = TestClient(server.app, raise_server_exceptions=False)

    with monkeypatch.context() as m, pytest.raises(sqlite3.OperationalError):
        _faal_bij_het_sram_profiel(m)
        verwijderen.verwijder_alles("anna")
    assert _aantallen("anna") == _ANNA

    with monkeypatch.context() as m:
        _faal_bij_het_sram_profiel(m)
        response = _verwijder(zonder_raise, token)

    assert response.status_code == 500
    assert _aantallen("anna") == _ANNA
    assert routes.auth._get_oidc_user("anna") is not None
    assert _ingetrokken() == 0
    assert _werkt(client, token)
    assert _verwijder(client, token).json() == {"ok": True, "verwijderd": _ANNA}
    assert _aantallen("anna") == _ALLES_NUL


def test_de_route_wist_het_sram_profiel_niet_meer_na_de_transactie(client, monkeypatch):
    """#1209: `vergeet_oidc_gebruiker` hoort bij uitloggen; het verwijderen doet het in de transactie. Zou de route het
    daarna nog aanroepen, dan gaf deze kapotte functie een 500."""

    def stuk(_sleutel):
        raise AssertionError("oidc_gebruiker_vergeet hoort niet bij verwijderen")

    _vul_anna()
    monkeypatch.setattr(db, "oidc_gebruiker_vergeet", stuk)

    response = _verwijder(client, _token("anna"))

    assert response.status_code == 200
    assert response.json()["verwijderd"]["oidc_gebruiker"] == 1
    assert _aantal("oidc_gebruiker", "anna") == 0


# ── 6. Zonder login, onbekende naam, `verwijderd` ────────────────────────────


def test_zonder_login_404_en_niets_weg(client, monkeypatch):
    from core import auth

    monkeypatch.setattr(auth, "AUTH_ENABLED", False)
    _vul(auth.FALLBACK_USER, "GAST-UNIEK")
    gast_voor = _aantallen(auth.FALLBACK_USER)

    response = _verwijder(client, None)

    assert response.status_code == 404
    assert response.json() == {"detail": "Zonder inloggen is er geen eigen account om te exporteren of te verwijderen."}
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
    assert _aantallen("dirk@hu.nl") == _ALLES_NUL
    assert (_rijen("anna"), _rijen("bert")) == (anna_voor, bert_voor)


# ── 7. Log en antwoord: alleen aantallen ─────────────────────────────────────


def test_log_en_antwoord_noemen_alleen_aantallen(client, caplog):
    _vul_anna()
    recepten.onthoud("anna", "nooit-bewaard", {"laad": ["get_cbs_data", {"dataset_id": "RECEPT-UNIEK"}]})
    caplog.set_level(logging.INFO)

    response = _verwijder(client, _token("anna"))

    log = "\n".join(r.getMessage() for r in caplog.records)
    # Elke opgeslagen tekst van Anna (titel, berichten, HTML, feedback, recept, SRAM-profiel) draagt ANNA-UNIEK; haar
    # e-mailadres in het profiel draagt `anna`.
    for tekst in ("ANNA-UNIEK", "RECEPT-UNIEK", "anna", "example.org"):
        assert tekst not in log
        assert tekst not in response.text
    regels = [r.getMessage() for r in caplog.records if r.name == "routes.mijn_gegevens"]
    assert len(regels) == 1
    assert regels[0] == (
        "verwijder mijn gegevens: conversations=3, workbooks=2, feedback=4, algemene_feedback=5, "
        "data_recipes=1, beurtbewijs=2, tokengebruik=3, oidc_gebruiker=1"
    )
    assert next(r for r in caplog.records if r.name == "routes.mijn_gegevens").levelno == logging.INFO


# ── 8. Geen tabel vergeten ───────────────────────────────────────────────────


def test_elke_tabel_met_een_gebruikersnaam_wordt_gewist_en_geexporteerd(tmp_path, monkeypatch):
    """Een nieuwe tabel met `username` moet in verwijderen én in de export, anders faalt deze test. `tokengebruik` en
    `oidc_gebruikers` hebben geen kolom `username` maar een pseudoniem van de naam (#1112, #984), en horen er toch bij
    (#1074, #1209)."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    db.init_db()
    with db._connection() as conn:
        tabellen = [r["name"] for r in db._execute(conn, "SELECT name FROM sqlite_master WHERE type = 'table'")]
        met_gebruiker = {
            t for t in tabellen if any(k["name"] == "username" for k in db._execute(conn, f"PRAGMA table_info({t})"))
        }

    assert met_gebruiker == set(_SOORTEN) - {"tokengebruik", "oidc_gebruiker"}
    assert "oidc_gebruikers" in tabellen
    assert list(verwijderen.DELETES) == list(export.SOORTEN) == _SOORTEN


def test_elke_delete_filtert_op_de_gebruiker():
    *op_naam, tokengebruik, oidc_gebruiker = verwijderen.DELETES.items()
    for soort, sql in op_naam:
        assert sql == f"DELETE FROM {soort} WHERE username = ?"
    assert tokengebruik == ("tokengebruik", "DELETE FROM tokengebruik WHERE sleutel = ?")
    assert oidc_gebruiker == ("oidc_gebruiker", "DELETE FROM oidc_gebruikers WHERE sleutel = ?")
