import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    # Reload auth first (reads env at module level), then server (imports from auth)
    from core import auth

    importlib.reload(auth)
    import server

    importlib.reload(server)
    return TestClient(server.app)


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_returns_status_ok(client):
    resp = client.get("/health")
    data = resp.json()
    assert data["status"] == "ok"


def test_version_returns_200(client):
    resp = client.get("/version")
    assert resp.status_code == 200


def test_api_version_geeft_json_en_geen_spa(client):
    """#405: /api/version viel terug op de SPA-HTML."""
    resp = client.get("/api/version")
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["version"] == client.get("/version").json()["version"]


def test_version_returns_version_string(client):
    resp = client.get("/version")
    data = resp.json()
    assert "version" in data
    assert isinstance(data["version"], str)
    assert len(data["version"].split(".")) >= 2


def test_version_volgt_de_release_uit_het_chart(client, monkeypatch):
    # Het image wordt op main gebouwd, dus pyproject.toml wist niet welke release er draait.
    from config import Config

    monkeypatch.setattr(Config, "APP_VERSION", "2.1.0")
    assert client.get("/version").json()["version"] == "2.1.0"
    assert client.get("/api/version").json()["version"] == "2.1.0"


def test_version_valt_zonder_chart_terug_op_pyproject(client, monkeypatch):
    from config import Config

    monkeypatch.setattr(Config, "APP_VERSION", None)
    assert client.get("/version").json()["version"].count(".") == 2


def test_version_noemt_de_commit_uit_het_image(client, monkeypatch):
    # #231: zonder commit was niet vast te stellen welke code een omgeving draait.
    from config import Config

    monkeypatch.setattr(Config, "GIT_COMMIT", "021632f")
    assert client.get("/version").json()["commit"] == "021632f"


def test_version_zonder_build_arg_zegt_onbekend(client, monkeypatch):
    from config import Config

    monkeypatch.setattr(Config, "GIT_COMMIT", None)
    assert client.get("/version").json()["commit"] == "onbekend"


def test_version_noemt_de_meegebouwde_catalogusrevisies(client):
    # #361: playground liep een CBS-catalogus-commit achter, en /version liet dat niet zien.
    catalogus = client.get("/version").json()["catalogus"]
    assert [p["pakket"] for p in catalogus] == ["onderwijsdata", "riodata"]
    assert all(p["versie"] for p in catalogus)
    assert all(len(p["commit"] or "") == 40 for p in catalogus)  # git-dependency: de commit uit uv.lock


def test_catalogusversie_zonder_package_geeft_geen_fout():
    from core.catalogusversie import _pakket

    assert _pakket("bestaat-niet-xyz") == {"pakket": "bestaat-niet-xyz", "versie": None, "commit": None}


def test_version_noemt_de_dataversie_van_uwv_en_roa(client):
    # CH-46 (#471): CBS, DUO en RIO stonden via de catalogus in /version, UWV en ROA niet.
    resp = client.get("/version")
    arbeidsmarkt = resp.json()["arbeidsmarkt"]
    assert [(b["bron"], b["dataset"]) for b in arbeidsmarkt] == [("UWV", "uwv-open-match-data"), ("ROA", "ais2030")]
    uwv, roa = arbeidsmarkt
    assert "2023-05-16" in uwv["periode"]  # einde van de bevroren snapshotreeks
    assert roa["periode"] == "Editie 2025"
    assert client.get("/api/version").json()["arbeidsmarkt"] == arbeidsmarkt


def test_version_laat_versie_commit_en_catalogus_ongemoeid(client):
    data = client.get("/version").json()
    assert set(data) == {"version", "commit", "catalogus", "arbeidsmarkt"}
    assert [p["pakket"] for p in data["catalogus"]] == ["onderwijsdata", "riodata"]


def test_version_downloadt_geen_arbeidsmarktdata(client, monkeypatch):
    # De app laadt UWV en ROA pas bij het eerste gebruik; een probe op /version mag dat niet starten.
    import httpx

    from core.catalogusversie import arbeidsmarktversie
    from data import arbeidsmarkt

    def geen_download(*args, **kwargs):
        raise AssertionError("/version mag geen data downloaden")

    monkeypatch.setattr(arbeidsmarkt, "_uwv", geen_download)
    monkeypatch.setattr(arbeidsmarkt, "_roa", geen_download)
    monkeypatch.setattr(httpx, "get", geen_download)
    arbeidsmarktversie.cache_clear()
    try:
        resp = client.get("/version")
    finally:
        arbeidsmarktversie.cache_clear()
    assert resp.status_code == 200
    assert [b["bron"] for b in resp.json()["arbeidsmarkt"]] == ["UWV", "ROA"]
    assert all(b["periode"] for b in resp.json()["arbeidsmarkt"])


def test_arbeidsmarktbron_zonder_record_geeft_geen_periode():
    from core.catalogusversie import _arbeidsmarktbron

    records = [{"_roa_id": "ais2028", "periode": "Editie 2024"}]
    assert _arbeidsmarktbron("ROA", "ais2030", records, "_roa_id") == {
        "bron": "ROA",
        "dataset": "ais2030",
        "periode": None,
    }
    assert _arbeidsmarktbron("UWV", "uwv-open-match-data", [], "_ckan_id")["periode"] is None


def test_arbeidsmarktbron_neemt_de_periode_letterlijk_over():
    from core.catalogusversie import _arbeidsmarktbron

    records = [{"_roa_id": "ais2028", "periode": "Editie 2024"}, {"_roa_id": "ais2030", "periode": "Editie 2025"}]
    assert _arbeidsmarktbron("ROA", "ais2030", records, "_roa_id")["periode"] == "Editie 2025"


def test_version_zonder_arbeidsmarktrecord_geeft_200(client, monkeypatch):
    from riodata import roa

    from core.catalogusversie import arbeidsmarktversie

    monkeypatch.setattr(roa, "catalog", list)
    arbeidsmarktversie.cache_clear()
    try:
        resp = client.get("/version")
    finally:
        arbeidsmarktversie.cache_clear()
    assert resp.status_code == 200
    assert resp.json()["arbeidsmarkt"][1] == {"bron": "ROA", "dataset": "ais2030", "periode": None}


async def _gezond() -> bool:
    return True


async def _kapot() -> bool:
    return False


@pytest.mark.parametrize(
    ("check", "naam"), [("check_database_connection", "database"), ("check_llm_configuration", "llm")]
)
def test_ready_meldt_falende_check_als_503(client, monkeypatch, check, naam):
    """#482: de probe kijkt naar de statuscode; /ready gaf 200 met een JSON-array."""
    import health

    monkeypatch.setattr(health, "check_database_connection", _gezond)
    monkeypatch.setattr(health, "check_llm_configuration", _gezond)
    monkeypatch.setattr(health, check, _kapot)
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.headers["content-type"].startswith("application/json")
    data = resp.json()
    assert isinstance(data, dict)
    assert data["status"] == "not_ready"
    assert data["checks"][naam] is False


def test_ready_geeft_200_als_alles_werkt(client, monkeypatch):
    import health

    monkeypatch.setattr(health, "check_database_connection", _gezond)
    monkeypatch.setattr(health, "check_llm_configuration", _gezond)
    resp = client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert data["status"] == "ready"
    assert data["checks"] == {"database": True, "llm": True}
