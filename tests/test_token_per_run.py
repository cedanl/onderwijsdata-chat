"""Een open chatverbinding volgt het intrekken en verlopen van het token (#786, besluit A).

De server toetste het token alleen bij de handshake; de hartslag (#489) hield de verbinding daarna onbeperkt open.
Nu toetst hij vóór elke run (vraag, verduidelijking, dashboard, rapport, verversen) het token van de handshake
opnieuw met `verify_token` en sluit hij bij een ongeldig token met 4001, zonder run. En "verwijder al mijn gegevens"
trekt alle tokens van het account in, niet alleen het meegestuurde.
"""

import sqlite3
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from core.rate_limit import RateLimiter

UUR = 3600


class Klok:
    """Vervangt de time-module in core.auth: tijd die de test zelf verzet."""

    def __init__(self, t: int):
        self.t = t

    def time(self) -> float:
        return float(self.t)


@pytest.fixture
def runs(tmp_path, monkeypatch):
    """Elke gestarte run, zonder model: per soort een nep die zich meldt en een event stuurt."""
    from persistence import db
    from routes import chat

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    db.init_db()
    gestart: list[str] = []

    def nep(soort: str):
        async def run(*args, **kwargs):
            gestart.append(soort)
            emit = next(a for a in args if callable(a))
            await emit({"type": "message_end", "soort": soort})

        return run

    monkeypatch.setattr(chat, "_process_message", nep("vraag"))
    monkeypatch.setattr(chat, "_generate_dashboard", nep("dashboard"))
    monkeypatch.setattr(chat, "_generate_report", nep("rapport"))
    monkeypatch.setattr(chat, "_refresh_dashboard", nep("verversen"))
    monkeypatch.setattr(chat, "_berichtlimiter", RateLimiter(max_attempts=100, window_seconds=600))
    return gestart


@pytest.fixture
def client(runs, monkeypatch):
    import server
    from core import auth
    from routes import chat

    monkeypatch.setattr(auth, "AUTH_ENABLED", True)
    monkeypatch.setattr(chat, "AUTH_ENABLED", True)
    monkeypatch.setattr(chat, "DASHBOARDS_ENABLED", True)
    return TestClient(server.app)


def _token(gebruiker: str = "anna", start: int | None = None) -> str:
    from core import auth

    return auth.make_token(gebruiker, start)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _verbind(client: TestClient, token: str):
    return client.websocket_connect("/api/chat", subprotocols=["bearer", token])


def _tot(ws, soort: str) -> dict:
    """Lees events tot het eerste van dit type; een melding over de API-sleutel kan ervoor komen."""
    while True:
        event = ws.receive_json()
        if event["type"] == soort:
            return event


def _volgende(ws) -> dict:
    """Het volgende event na een eventuele melding over de API-sleutel."""
    while (event := ws.receive_json())["type"] == "system_message":
        pass
    return event


def _sluitcode(ws) -> int:
    """De sluitcode; elk ander event betekent dat de verbinding openbleef (en de test wacht niet eeuwig)."""
    with pytest.raises(WebSocketDisconnect) as gesloten:
        pytest.fail(f"de verbinding bleef open: {_volgende(ws)}")
    return gesloten.value.code


# Per run-actie een frame dat zonder de controle een run zou starten.
FRAMES = {
    "message": {"action": "message", "content": "Hoeveel studenten?"},
    "clarification_choice": {"action": "clarification_choice", "choice": "hbo"},
    "generate_dashboard": {"action": "generate_dashboard"},
    "generate_report": {"action": "generate_report"},
    "refresh_dashboard": {"action": "refresh_dashboard"},
}


def test_elke_run_actie_wordt_getoetst():
    from routes import chat

    assert set(FRAMES) == chat.RUN_ACTIES
    assert chat.RUN_ACTIES.issubset(chat.ACTIES)


# ── Geldig token: de run loopt door ──────────────────────────────────────────


@pytest.mark.parametrize("actie", sorted(FRAMES))
def test_met_een_geldig_token_start_de_run(client, runs, actie):
    with _verbind(client, _token()) as ws:
        ws.send_json(FRAMES[actie])
        _tot(ws, "message_end")

    assert len(runs) == 1


# ── Uitloggen in een ander tabblad ───────────────────────────────────────────


@pytest.mark.parametrize("actie", sorted(FRAMES))
def test_na_uitloggen_elders_sluit_de_volgende_run_met_4001_zonder_run(client, runs, actie):
    token = _token()
    with _verbind(client, token) as ws:
        ws.send_json({"action": "ping"})
        _tot(ws, "pong")
        assert client.post("/api/auth/logout", headers=_bearer(token)).status_code == 204

        ws.send_json(FRAMES[actie])

        assert _sluitcode(ws) == 4001
    assert runs == []


def test_eerst_een_run_dan_uitloggen_dan_4001(client, runs):
    token = _token()
    with _verbind(client, token) as ws:
        ws.send_json(FRAMES["message"])
        _tot(ws, "message_end")
        client.post("/api/auth/logout", headers=_bearer(token))

        ws.send_json(FRAMES["message"])

        assert _sluitcode(ws) == 4001
    assert runs == ["vraag"]


def test_de_hartslag_leest_het_token_niet_opnieuw(client, runs, monkeypatch):
    """Alleen wat een run start, toetst: een ping per paar seconden hoort niet bij elke keer een DB-lookup."""
    from routes import chat

    token = _token()
    with _verbind(client, token) as ws:
        client.post("/api/auth/logout", headers=_bearer(token))
        monkeypatch.setattr(chat, "verify_token", lambda t: pytest.fail("ping mag het token niet toetsen"))

        ws.send_json({"action": "ping"})

        assert _tot(ws, "pong") == {"type": "pong"}


# ── Verlopen token ───────────────────────────────────────────────────────────


def test_een_token_dat_verloopt_terwijl_de_verbinding_open_is_geeft_4001(client, runs, monkeypatch):
    from core import auth

    klok = Klok(1_800_000_000)
    monkeypatch.setattr(auth, "time", klok)
    token = _token()
    with _verbind(client, token) as ws:
        ws.send_json(FRAMES["message"])
        _tot(ws, "message_end")
        klok.t += auth.SESSION_TTL + 1

        ws.send_json(FRAMES["message"])

        assert _sluitcode(ws) == 4001
    assert runs == ["vraag"]


# ── Een databasestoring is geen "sessie voorbij" ────────────────────────────


def test_een_storing_bij_de_controle_geeft_een_melding_geen_run_en_de_verbinding_blijft(client, runs, monkeypatch):
    from persistence import db

    echte = db.is_token_revoked
    aanroepen = {"n": 0}

    def eerst_goed_dan_storing(*args):
        aanroepen["n"] += 1
        if aanroepen["n"] > 1:
            raise sqlite3.OperationalError("database is locked")
        return echte(*args)

    monkeypatch.setattr(db, "is_token_revoked", eerst_goed_dan_storing)
    with _verbind(client, _token()) as ws:
        ws.send_json(FRAMES["message"])

        fout = _volgende(ws)
        ws.send_json({"action": "ping"})
        assert _tot(ws, "pong") == {"type": "pong"}

    assert fout["type"] == "error"
    assert "fout-ID" in fout["message"]
    assert "locked" not in fout["message"]
    assert runs == []


# ── Verwijder al mijn gegevens: alle tokens van het account ─────────────────


def _verwijder(client: TestClient, token: str):
    return client.request("DELETE", "/api/mijn-gegevens", headers=_bearer(token), json={"bevestig": "verwijder"})


def test_na_verwijderen_gelden_ook_de_andere_tokens_van_het_account_niet_meer(client):
    nu = int(time.time())
    hier = _token("anna", start=nu - 60)
    ander_apparaat = _token("anna", start=nu - 30)
    bert = _token("bert", start=nu - 60)

    assert _verwijder(client, hier).status_code == 200

    for token in (hier, ander_apparaat):
        assert client.get("/api/conversations", headers=_bearer(token)).status_code == 401
    assert client.get("/api/conversations", headers=_bearer(bert)).status_code == 200
    # Terugzetten vanaf het andere apparaat kan niet meer (de aanleiding in #786).
    put = client.put("/api/conversations/c1", headers=_bearer(ander_apparaat), json={"title": "t", "messages": []})
    assert put.status_code == 401


def test_na_verwijderen_sluit_een_open_verbinding_op_een_ander_apparaat_bij_de_volgende_vraag(client, runs):
    nu = int(time.time())
    hier = _token("anna", start=nu - 60)
    with _verbind(client, _token("anna", start=nu - 30)) as anna, _verbind(client, _token("bert")) as bert:
        assert _verwijder(client, hier).status_code == 200

        anna.send_json(FRAMES["message"])
        bert.send_json(FRAMES["message"])

        assert _sluitcode(anna) == 4001
        _tot(bert, "message_end")
    assert runs == ["vraag"]


def test_een_ververst_token_van_voor_het_verwijderen_geldt_ook_niet_meer(client, monkeypatch):
    """Verversen houdt de sessiestart (#479): een token van na het verwijderen uit een oude sessie telt niet."""
    from core import auth

    nu = int(time.time())
    oude_sessie = nu - 2 * UUR
    assert _verwijder(client, _token("anna", start=oude_sessie)).status_code == 200

    ververst = auth.make_token("anna", start=oude_sessie)

    assert auth.verify_token(ververst) is None


def test_een_login_na_het_verwijderen_geldt_weer(client):
    from core import auth

    nu = int(time.time())
    assert _verwijder(client, _token("anna", start=nu - 60)).status_code == 200

    assert auth.verify_token(_token("anna", start=nu + 1)) == "anna"


# ── De tabel revoked_users ───────────────────────────────────────────────────


def test_revoked_users_bewaart_alleen_een_hash_tot_alle_tokens_verlopen_zijn(client):
    import hashlib

    from core import auth
    from persistence import db

    nu = int(time.time())
    assert _verwijder(client, _token("anna", start=nu - 60)).status_code == 200

    with db._connection() as conn:
        rijen = [dict(r) for r in db._execute(conn, "SELECT * FROM revoked_users")]
        assert db._execute(conn, "SELECT COUNT(*) AS n FROM revoked_tokens").fetchone()["n"] == 0
    [rij] = rijen
    assert rij["user_hash"] == hashlib.sha256(b"anna").hexdigest()
    assert "anna" not in str(rij)
    assert nu <= rij["revoked_before"] <= int(time.time())
    assert rij["expires_at"] == rij["revoked_before"] + max(auth.SESSION_MAX, 24 * UUR)


def test_intrekken_per_account_grenst_op_de_sessiestart(runs):
    from persistence import db

    db.revoke_user_tokens("u", 1000, 99_999_999_999)

    assert db.is_token_revoked("t", "u", 999) is True
    assert db.is_token_revoked("t", "u", 1000) is True
    assert db.is_token_revoked("t", "u", 1001) is False
    assert db.is_token_revoked("t", "ander", 999) is False


def test_een_latere_intrekking_vervangt_de_eerdere(runs):
    from persistence import db

    db.revoke_user_tokens("u", 1000, 99_999_999_998)
    db.revoke_user_tokens("u", 2000, 99_999_999_999)

    assert db.is_token_revoked("t", "u", 1500) is True
    with db._connection() as conn:
        assert [tuple(r) for r in db._execute(conn, "SELECT * FROM revoked_users")] == [("u", 2000, 99_999_999_999)]


def test_verlopen_intrekkingen_per_account_worden_opgeruimd(runs):
    from persistence import db

    nu = int(time.time())
    db.revoke_user_tokens("oud", 1000, nu - 10)
    db.revoke_user_tokens("actief", 1000, nu + 100)

    with db._connection() as conn:
        assert [r["user_hash"] for r in db._execute(conn, "SELECT user_hash FROM revoked_users")] == ["actief"]
