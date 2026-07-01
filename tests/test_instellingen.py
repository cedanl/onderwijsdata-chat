import importlib

import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    import data.instellingen as inst
    inst._cache = None
    inst._alias_lookup = None
    yield
    inst._cache = None
    inst._alias_lookup = None


# ─── Registry ────────────────────────────────────────────────────────────────

def test_registry_returns_list():
    from data.instellingen import get_all
    result = get_all()
    assert isinstance(result, list)
    assert len(result) > 0


def test_registry_sorted_alphabetically():
    from data.instellingen import get_all
    result = get_all()
    names = [i["naam"] for i in result]
    assert names == sorted(names, key=str.lower)


def test_registry_has_required_fields():
    from data.instellingen import get_all
    for inst in get_all():
        assert "naam" in inst
        assert "type" in inst
        assert "aliassen" in inst
        assert inst["type"] in ("wo", "hbo", "mbo")
        assert isinstance(inst["aliassen"], list)


def test_registry_contains_all_types():
    from data.instellingen import get_all
    types = {i["type"] for i in get_all()}
    assert types == {"wo", "hbo", "mbo"}


def test_registry_no_duplicate_names():
    from data.instellingen import get_all
    names = [i["naam"] for i in get_all()]
    assert len(names) == len(set(names))


# ─── Alias resolve ───────────────────────────────────────────────────────────

def test_resolve_exact_name():
    from data.instellingen import resolve_alias
    assert resolve_alias("Hogeschool Utrecht") == "Hogeschool Utrecht"


def test_resolve_case_insensitive():
    from data.instellingen import resolve_alias
    assert resolve_alias("hogeschool utrecht") == "Hogeschool Utrecht"


def test_resolve_known_alias():
    from data.instellingen import resolve_alias
    assert resolve_alias("VU") == "Vrije Universiteit Amsterdam"
    assert resolve_alias("HvA") == "Hogeschool van Amsterdam"
    assert resolve_alias("TU Delft") == "Technische Universiteit Delft"


def test_resolve_alias_case_insensitive():
    from data.instellingen import resolve_alias
    assert resolve_alias("vu") == "Vrije Universiteit Amsterdam"
    assert resolve_alias("hva") == "Hogeschool van Amsterdam"


def test_resolve_mbo_alias():
    from data.instellingen import resolve_alias
    assert resolve_alias("Mondriaan") == "ROC Mondriaan"
    assert resolve_alias("ROC MN") == "ROC Midden Nederland"


def test_resolve_unknown_returns_input():
    from data.instellingen import resolve_alias
    assert resolve_alias("Onbekende Instelling") == "Onbekende Instelling"


def test_resolve_empty_string():
    from data.instellingen import resolve_alias
    assert resolve_alias("") == ""


# ─── Dashboard HO ────────────────────────────────────────────────────────────

def test_dashboard_ho_found():
    from data.dashboard import load_dashboard_ho
    result = load_dashboard_ho("Hogeschool Utrecht")
    assert result is not None
    assert "ingeschrevenen" in result
    assert "laatste_jaar" in result
    assert "sectoren" in result
    assert isinstance(result["ingeschrevenen"], dict)
    assert all(isinstance(k, (int, str)) for k in result["ingeschrevenen"])


def test_dashboard_ho_wo_found():
    from data.dashboard import load_dashboard_ho
    result = load_dashboard_ho("Vrije Universiteit Amsterdam")
    assert result is not None
    assert "ingeschrevenen" in result


def test_dashboard_ho_not_found():
    from data.dashboard import load_dashboard_ho
    result = load_dashboard_ho("Niet Bestaande Instelling")
    assert result is None


def test_dashboard_ho_has_geslacht():
    from data.dashboard import load_dashboard_ho
    result = load_dashboard_ho("Hogeschool Utrecht")
    assert "geslacht" in result


# ─── Dashboard MBO ───────────────────────────────────────────────────────────

def test_dashboard_mbo_found():
    from data.dashboard import load_dashboard_mbo
    result = load_dashboard_mbo("ROC Mondriaan")
    assert result is not None
    assert "ingeschrevenen" in result
    assert "laatste_jaar" in result
    assert "sectoren" in result


def test_dashboard_mbo_has_leerwegen():
    from data.dashboard import load_dashboard_mbo
    result = load_dashboard_mbo("ROC Mondriaan")
    assert any(k in result["sectoren"] for k in ("BBL", "BOL voltijd", "BOL deeltijd"))


def test_dashboard_mbo_not_found():
    from data.dashboard import load_dashboard_mbo
    result = load_dashboard_mbo("Niet Bestaande Instelling")
    assert result is None


def test_dashboard_mbo_has_gediplomeerden():
    from data.dashboard import load_dashboard_mbo
    result = load_dashboard_mbo("ROC Mondriaan")
    assert "gediplomeerden" in result


# ─── Dashboard composite ─────────────────────────────────────────────────────

def test_load_dashboard_resolves_alias():
    from data.dashboard import load_dashboard
    result = load_dashboard("VU")
    assert result["gevonden"] is True
    assert result["instelling"] == "Vrije Universiteit Amsterdam"


def test_load_dashboard_mbo_via_alias():
    from data.dashboard import load_dashboard
    result = load_dashboard("Mondriaan")
    assert result["gevonden"] is True
    assert result["instelling"] == "ROC Mondriaan"


def test_load_dashboard_not_found_has_suggestions():
    from data.dashboard import load_dashboard
    result = load_dashboard("Niet Bestaande Instelling XYZ")
    assert result["gevonden"] is False
    assert "beschikbare_instellingen" in result
    assert len(result["beschikbare_instellingen"]) > 0


# ─── API endpoint ────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    import core.auth as auth
    importlib.reload(auth)
    import server
    importlib.reload(server)
    from fastapi.testclient import TestClient
    return TestClient(server.app)


def test_api_instellingen_returns_list(client):
    resp = client.get("/api/instellingen")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_api_instellingen_filter_by_type(client):
    resp = client.get("/api/instellingen?type=wo")
    assert resp.status_code == 200
    data = resp.json()
    assert all(i["type"] == "wo" for i in data)
    assert len(data) > 0


def test_api_instellingen_filter_multiple_types(client):
    resp = client.get("/api/instellingen?type=wo,hbo")
    assert resp.status_code == 200
    data = resp.json()
    types = {i["type"] for i in data}
    assert types <= {"wo", "hbo"}
    assert len(types) == 2


def test_api_dashboard_ho(client):
    resp = client.get("/api/dashboard/instroom?instelling=Hogeschool+Utrecht")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True


def test_api_dashboard_alias(client):
    resp = client.get("/api/dashboard/instroom?instelling=VU")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True
    assert data["instelling"] == "Vrije Universiteit Amsterdam"


def test_api_dashboard_mbo(client):
    resp = client.get("/api/dashboard/instroom?instelling=ROC+Mondriaan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gevonden"] is True
