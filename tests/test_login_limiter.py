"""De login-limiter telt per gebruikersnaam + adres (#504, S5).

Achter de ingress ziet uvicorn vaak voor iedereen hetzelfde adres. Met alleen het
IP als sleutel deelden alle wachtwoordgebruikers één budget van 5 pogingen per
minuut, en kon iemand zonder inloggegevens de login voor iedereen blokkeren.
"""

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CHAT_USERS", "anna:pw1,bob:pw2")
    monkeypatch.setenv("CHAT_SECRET", "test-secret-for-tests")
    from core import auth, config

    importlib.reload(config)
    importlib.reload(auth)
    import routes.auth
    import server

    importlib.reload(routes.auth)
    importlib.reload(server)
    return TestClient(server.app)


def _login(client, user, pw):
    return client.post("/api/auth/login", json={"username": user, "password": pw})


def test_vijf_mislukte_pogingen_blokkeren_die_gebruikersnaam(client):
    for _ in range(5):
        assert _login(client, "anna", "fout").status_code == 401
    resp = _login(client, "anna", "fout")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_vol_budget_van_de_een_blokkeert_de_ander_niet(client):
    """Eén aanvaller (zelfde adres, hier altijd testclient) kan bob niet blokkeren via anna."""
    for _ in range(6):
        _login(client, "anna", "fout")
    assert _login(client, "anna", "fout").status_code == 429
    assert _login(client, "bob", "pw2").status_code == 200


def test_ook_de_juiste_wachtwoordpoging_telt_mee_binnen_het_budget(client):
    """Na een vol budget is ook het juiste wachtwoord even geblokkeerd: de limiter
    verraadt niet welke poging goed was."""
    for _ in range(5):
        _login(client, "anna", "fout")
    assert _login(client, "anna", "pw1").status_code == 429


def test_gebruikersnaam_zonder_waarde_telt_als_gast(client):
    for _ in range(5):
        _login(client, "", "x")
    assert _login(client, "", "x").status_code == 429
    assert _login(client, "anna", "pw1").status_code == 200
