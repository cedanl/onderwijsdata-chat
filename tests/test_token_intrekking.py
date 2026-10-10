"""Uitloggen trekt het token server-side in en een sessie duurt begrensd lang (#479)."""

import base64
import hashlib
import importlib
import logging
import sqlite3
import sys
import time
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

UUR = 3600


class Klok:
    """Vervangt de time-module in core.auth en routes.auth: tijd die de test zelf verzet."""

    def __init__(self, t: int):
        self.t = t

    def time(self) -> float:
        return float(self.t)


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    db.init_db()
    return tmp_path / "test.db"


@pytest.fixture
def client(database, monkeypatch):
    """De app met inloggen aan, zonder modules te herladen: niets blijft achter voor de volgende test."""
    import routes.chat
    import server
    from core import auth

    monkeypatch.setattr(auth, "AUTH_ENABLED", True)
    monkeypatch.setattr(routes.chat, "AUTH_ENABLED", True)
    monkeypatch.setattr(routes.chat, "DASHBOARDS_ENABLED", True)
    return TestClient(server.app)


@pytest.fixture
def oidc_client(database, monkeypatch):
    """Alleen de auth-routes, met OIDC aan zodat /refresh bestaat; daarna weer zonder."""
    import routes.auth
    from config import Config
    from core import auth

    monkeypatch.setattr(auth, "AUTH_ENABLED", True)
    for naam in ("OIDC_PROVIDER", "OIDC_DISCOVERY_URL", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "SERVER_URL"):
        monkeypatch.setattr(Config, naam, "test")
    importlib.reload(routes.auth)
    app = FastAPI()
    app.include_router(routes.auth.router)
    yield TestClient(app)
    monkeypatch.undo()
    importlib.reload(routes.auth)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token(username: str = "alice") -> str:
    from core import auth

    return auth.make_token(username)


def _oud_token(username: str, exp: int) -> str:
    """Een token in het formaat van vóór #479: base64url("<user>|<exp>").<handtekening>."""
    from core import auth

    payload = base64.urlsafe_b64encode(f"{username}|{exp}".encode()).decode().rstrip("=")
    return f"{payload}.{auth._token_sign(payload)}"


def _claims(token: str) -> list[str]:
    payload = token.rsplit(".", 1)[0]
    return base64.urlsafe_b64decode(payload + "==").decode().split("|")


def _rijen(database) -> list[tuple]:
    conn = sqlite3.connect(str(database))
    rows = conn.execute("SELECT token_hash, expires_at FROM revoked_tokens ORDER BY expires_at").fetchall()
    conn.close()
    return rows


def _zet_klok(monkeypatch, t: int) -> Klok:
    import routes.auth
    from core import auth

    klok = Klok(t)
    monkeypatch.setattr(auth, "time", klok)
    monkeypatch.setattr(routes.auth, "time", klok)
    return klok


# ── Criterium 1: REST na logout ──────────────────────────────────────────────


def test_logout_trekt_het_token_in_voor_rest(client):
    token = _token()
    assert client.get("/api/conversations", headers=_bearer(token)).status_code == 200

    assert client.post("/api/auth/logout", headers=_bearer(token)).status_code == 204

    assert client.get("/api/conversations", headers=_bearer(token)).status_code == 401


def test_logout_laat_een_ander_token_van_dezelfde_gebruiker_staan(client):
    from core import auth

    token = _token()
    ander = auth.make_token("alice", start=int(time.time()) - 60)
    assert ander != token

    client.post("/api/auth/logout", headers=_bearer(token))

    assert client.get("/api/conversations", headers=_bearer(ander)).status_code == 200


# ── Criterium 2: dashboard-refresh en WebSocket ──────────────────────────────


def test_dashboard_refresh_weigert_een_ingetrokken_token(client):
    token = _token()
    assert client.post("/api/dashboard/refresh", headers=_bearer(token), json={}).status_code != 401

    client.post("/api/auth/logout", headers=_bearer(token))

    assert client.post("/api/dashboard/refresh", headers=_bearer(token), json={}).status_code == 401


def test_websocket_met_geldig_token_wordt_geaccepteerd(client):
    with client.websocket_connect("/api/chat", subprotocols=["bearer", _token()]) as ws:
        assert ws.accepted_subprotocol == "bearer"


def test_websocket_weigert_een_ingetrokken_token(client):
    token = _token()
    client.post("/api/auth/logout", headers=_bearer(token))

    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect("/api/chat", subprotocols=["bearer", token]) as ws,
    ):
        ws.receive_text()
    assert exc.value.code == 4001


# ── Criterium 3 en 7: refresh ────────────────────────────────────────────────


def test_refresh_weigert_een_ingetrokken_token(oidc_client):
    token = _token()
    oidc_client.post("/api/auth/logout", headers=_bearer(token))

    assert oidc_client.post("/api/auth/refresh", json={"token": token}).status_code == 401


def test_refresh_houdt_de_sessiestart_en_verlengt_met_de_ttl(oidc_client, monkeypatch):
    from core import auth

    start = 1_800_000_000
    klok = _zet_klok(monkeypatch, start)
    token = _token()
    klok.t = start + 7 * UUR

    resp = oidc_client.post("/api/auth/refresh", json={"token": token})

    assert resp.status_code == 200
    user, nieuw_start, exp = _claims(resp.json()["token"])
    assert (user, int(nieuw_start), int(exp)) == ("alice", start, start + 7 * UUR + auth.SESSION_TTL)


def test_herhaald_refreshen_komt_nooit_voorbij_de_maximale_sessieduur(oidc_client, monkeypatch):
    from core import auth

    start = 1_800_000_000
    grens = start + auth.SESSION_MAX
    klok = _zet_klok(monkeypatch, start)
    token = _token()

    while True:
        klok.t += 7 * UUR
        klok.t = min(klok.t, grens)
        resp = oidc_client.post("/api/auth/refresh", json={"token": token})
        if klok.t >= grens:
            break
        assert resp.status_code == 200
        token = resp.json()["token"]
        _, nieuw_start, exp = _claims(token)
        assert int(nieuw_start) == start
        assert int(exp) <= grens

    assert resp.status_code == 401
    assert int(_claims(token)[2]) == grens


def test_refresh_net_voor_de_grens_geeft_een_token_tot_de_grens(oidc_client, monkeypatch):
    from core import auth

    start = 1_800_000_000
    klok = _zet_klok(monkeypatch, start)
    token = auth.make_token("alice", start=start - auth.SESSION_MAX + UUR)

    resp = oidc_client.post("/api/auth/refresh", json={"token": token})

    assert resp.status_code == 200
    assert int(_claims(resp.json()["token"])[2]) == start + UUR
    klok.t = start + UUR
    assert oidc_client.post("/api/auth/refresh", json={"token": resp.json()["token"]}).status_code == 401


def test_refresh_van_een_oud_token_geeft_het_nieuwe_formaat(oidc_client, monkeypatch):
    from core import auth

    t0 = 1_800_000_000
    klok = _zet_klok(monkeypatch, t0)
    oud = _oud_token("alice", t0 + 24 * UUR)
    klok.t = t0 + UUR

    resp = oidc_client.post("/api/auth/refresh", json={"token": oud})

    assert resp.status_code == 200
    user, start, exp = _claims(resp.json()["token"])
    assert (user, int(start), int(exp)) == ("alice", t0, t0 + UUR + auth.SESSION_TTL)


# ── Criterium 4: logout is idempotent en werkt zonder login ──────────────────


def test_tweede_logout_geeft_204_en_schrijft_niets(client, database):
    token = _token()
    assert client.post("/api/auth/logout", headers=_bearer(token)).status_code == 204
    voor = _rijen(database)

    assert client.post("/api/auth/logout", headers=_bearer(token)).status_code == 204

    assert _rijen(database) == voor
    assert len(voor) == 1


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer onzin"},
        {"Authorization": "Bearer abc.def"},
        {"Authorization": "Basic YWxpY2U6Z2VoZWlt"},
    ],
)
def test_logout_zonder_geldig_token_geeft_204_en_schrijft_niets(client, database, headers):
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert _rijen(database) == []


def test_logout_met_verlopen_token_geeft_204_en_schrijft_niets(client, database):
    verlopen = _oud_token("alice", int(time.time()) - 10)

    assert client.post("/api/auth/logout", headers=_bearer(verlopen)).status_code == 204
    assert _rijen(database) == []


def test_logout_met_vervalst_token_schrijft_niets(client, database):
    payload = _token().rsplit(".", 1)[0]

    assert client.post("/api/auth/logout", headers=_bearer(f"{payload}.{'0' * 64}")).status_code == 204
    assert _rijen(database) == []


def test_logout_zonder_login_raakt_de_database_niet(monkeypatch):
    import server
    from core import auth
    from persistence import db

    def geen_db(*args, **kwargs):
        raise AssertionError("logout zonder login mag de database niet raken")

    monkeypatch.setattr(auth, "AUTH_ENABLED", False)
    monkeypatch.setattr(db, "revoke_token_hash", geen_db)
    monkeypatch.setattr(db, "is_token_revoked", geen_db)
    monkeypatch.setattr(db, "_connect", geen_db)
    client = TestClient(server.app)

    assert client.post("/api/auth/logout", headers=_bearer(_token())).status_code == 204
    assert auth._resolve_user(None) == auth.FALLBACK_USER
    assert auth._resolve_user("Bearer wat-dan-ook") == auth.FALLBACK_USER


# ── Criterium 6: oude tokens blijven werken ──────────────────────────────────


def test_oud_token_werkt_op_rest(client):
    oud = _oud_token("alice", int(time.time()) + UUR)

    assert client.get("/api/conversations", headers=_bearer(oud)).status_code == 200


def test_oud_token_kan_worden_ingetrokken(client):
    oud = _oud_token("alice", int(time.time()) + UUR)

    assert client.post("/api/auth/logout", headers=_bearer(oud)).status_code == 204

    assert client.get("/api/conversations", headers=_bearer(oud)).status_code == 401


def test_oud_token_werkt_op_de_websocket(client):
    oud = _oud_token("alice", int(time.time()) + UUR)

    with client.websocket_connect("/api/chat", subprotocols=["bearer", oud]) as ws:
        assert ws.accepted_subprotocol == "bearer"


# ── Criterium 8 en 9: tabel en opruimen ──────────────────────────────────────


def test_denylist_bewaart_de_hash_tot_de_exp_van_het_token(client, database):
    token = _token()
    exp = int(_claims(token)[2])

    client.post("/api/auth/logout", headers=_bearer(token))

    assert _rijen(database) == [(hashlib.sha256(token.encode()).hexdigest(), exp)]


def _voeg_rij_toe(database, token_hash: str, expires_at: int) -> None:
    conn = sqlite3.connect(str(database))
    conn.execute("INSERT INTO revoked_tokens (token_hash, expires_at) VALUES (?, ?)", (token_hash, expires_at))
    conn.commit()
    conn.close()


def test_intrekken_ruimt_verlopen_rijen_op(database):
    from persistence import db

    nu = int(time.time())
    _voeg_rij_toe(database, "verlopen", nu - 10)
    _voeg_rij_toe(database, "actief", nu + 100)

    db.revoke_token_hash("nieuw", nu + 200)

    assert [h for h, _ in _rijen(database)] == ["actief", "nieuw"]


def test_init_db_ruimt_verlopen_rijen_op(database):
    from persistence import db

    nu = int(time.time())
    _voeg_rij_toe(database, "verlopen", nu - 10)
    _voeg_rij_toe(database, "actief", nu + 100)

    db.init_db()

    assert [h for h, _ in _rijen(database)] == ["actief"]


def test_is_token_revoked(database):
    from persistence import db

    db.revoke_token_hash("h", int(time.time()) + 100)

    assert db.is_token_revoked("h") is True
    assert db.is_token_revoked("ander") is False


def test_bestaande_database_krijgt_de_tabel_zonder_dataverlies(database):
    from persistence import db

    conn = sqlite3.connect(str(database))
    conn.execute("DROP TABLE revoked_tokens")
    conn.commit()
    conn.close()
    db.upsert_conversation("alice", "c1", "Titel", 1_700_000_000, [{"role": "user", "content": "hoi"}])

    db.init_db()

    assert _rijen(database) == []
    assert [c["id"] for c in db.list_conversations("alice")] == ["c1"]


def test_init_db_maakt_de_tabel_ook_in_postgres(monkeypatch):
    from persistence import db

    extras = types.SimpleNamespace(RealDictCursor=object)
    psycopg2 = types.SimpleNamespace(extras=extras)
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg2)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras)

    sql: list[str] = []

    class Cursor:
        def execute(self, query, params=()):
            sql.append(" ".join(query.split()))

        def fetchone(self):
            return (1,)

        def fetchall(self):
            return []

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(db, "_USE_POSTGRES", True)
    monkeypatch.setattr(db, "_connect", Conn)

    db.init_db()

    assert any(s.startswith("CREATE TABLE IF NOT EXISTS revoked_tokens") for s in sql)
    assert any("ON revoked_tokens(expires_at)" in s for s in sql)
    assert "DELETE FROM revoked_tokens WHERE expires_at < %s" in sql


# ── Criterium 10: geen token of hash in logs ─────────────────────────────────


def test_geen_token_of_hash_in_logs(oidc_client, client, caplog):
    caplog.set_level(logging.DEBUG)
    token = _token()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    ververst = oidc_client.post("/api/auth/refresh", json={"token": token}).json()["token"]

    antwoorden = [
        client.post("/api/auth/logout", headers=_bearer(token)),
        client.get("/api/conversations", headers=_bearer(token)),
        oidc_client.post("/api/auth/refresh", json={"token": token}),
        client.post("/api/dashboard/refresh", headers=_bearer(token), json={}),
    ]

    assert [r.status_code for r in antwoorden] == [204, 401, 401, 401]
    for geheim in (token, token_hash, ververst, hashlib.sha256(ververst.encode()).hexdigest()):
        assert geheim not in caplog.text
        assert all(geheim not in r.text for r in antwoorden)


# ── Een databasestoring is geen "sessie voorbij" ────────────────────────────


def test_databasestoring_geeft_500_en_geen_401(client, monkeypatch):
    from persistence import db

    def storing(token_hash):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "is_token_revoked", storing)
    client = TestClient(client.app, raise_server_exceptions=False)

    assert client.get("/api/conversations", headers=_bearer(_token())).status_code == 500
