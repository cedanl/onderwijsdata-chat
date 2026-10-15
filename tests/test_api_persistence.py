import importlib

import pytest
from fastapi.testclient import TestClient

from core.persoonsgegevens import GESPREKSTITEL_ZONDER_PERSOONSGEGEVENS, MAX_GESPREKSTITEL


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    from core import auth

    importlib.reload(auth)
    from persistence import db

    importlib.reload(db)
    db.init_db()
    import server

    importlib.reload(server)
    return TestClient(server.app)


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CHAT_USERS", "testuser:testpass")
    monkeypatch.setenv("CHAT_SECRET", "test-secret-for-tests")
    from core import auth

    importlib.reload(auth)
    from persistence import db

    importlib.reload(db)
    db.init_db()
    import server

    importlib.reload(server)
    c = TestClient(server.app)
    resp = c.post("/api/auth/login", json={"username": "testuser", "password": "testpass"})
    token = resp.json()["token"]
    c.headers["Authorization"] = f"Bearer {token}"
    return c


# ── Conversations (no auth) ──────────────────────────────────────────────────


def test_get_conversations_empty(client):
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_put_and_get_conversation(client):
    body = {"title": "Test", "timestamp": 1000, "messages": [{"role": "user", "content": "hi"}]}
    resp = client.put("/api/conversations/c1", json=body)
    assert resp.status_code == 200

    resp = client.get("/api/conversations")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "c1"
    assert data[0]["title"] == "Test"


def test_get_conversations_next_page(client):
    for i in range(4):
        client.put(f"/api/conversations/c{i}", json={"title": f"C{i}", "timestamp": (i + 1) * 1000, "messages": []})
    eerste = client.get("/api/conversations", params={"limit": 2}).json()
    laatste = eerste[-1]
    rest = client.get(
        "/api/conversations", params={"limit": 2, "before_ts": laatste["timestamp"], "before_id": laatste["id"]}
    ).json()
    assert [c["id"] for c in eerste + rest] == ["c3", "c2", "c1", "c0"]


def test_get_conversations_limit_is_capped(client):
    assert client.get("/api/conversations", params={"limit": 1000}).status_code == 422


# ── One conversation (#509): the list is small, the messages come when a conversation is opened ──


def test_list_carries_no_messages(client):
    body = {"title": "Test", "timestamp": 1000, "messages": [{"role": "user", "content": "hi"}]}
    client.put("/api/conversations/c1", json=body)
    assert client.get("/api/conversations").json() == [{"id": "c1", "title": "Test", "timestamp": 1000}]


def test_get_one_conversation_with_messages(client):
    messages = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hoi", "figures": ["{}"]}]
    client.put("/api/conversations/c1", json={"title": "Test", "timestamp": 1000, "messages": messages})
    resp = client.get("/api/conversations/c1")
    assert resp.status_code == 200
    assert resp.json() == {"id": "c1", "title": "Test", "timestamp": 1000, "messages": messages}


def test_get_unknown_conversation_returns_404(client):
    assert client.get("/api/conversations/bestaat-niet").status_code == 404


def test_get_conversation_of_another_user_returns_404(authed_client):
    from persistence import db

    db.upsert_conversation("iemand-anders", "c1", "Geheim", 1000, [{"role": "user", "content": "pii"}])
    assert authed_client.get("/api/conversations/c1").status_code == 404


def test_delete_conversation(client):
    client.put("/api/conversations/c1", json={"title": "X", "timestamp": 1, "messages": []})
    resp = client.delete("/api/conversations/c1")
    assert resp.status_code == 200
    assert client.get("/api/conversations").json() == []


def test_patch_conversation_title_only(client):
    body = {"title": "Oud", "timestamp": 1000, "messages": [{"role": "user", "content": "hi"}]}
    client.put("/api/conversations/c1", json=body)

    resp = client.patch("/api/conversations/c1", json={"title": "Nieuw"})
    assert resp.status_code == 200

    [conv] = client.get("/api/conversations").json()
    assert conv["title"] == "Nieuw"
    assert conv["timestamp"] == 1000
    assert client.get("/api/conversations/c1").json()["messages"] == body["messages"]


def test_patch_conversation_strips_title(client):
    client.put("/api/conversations/c1", json={"title": "Oud", "timestamp": 1, "messages": []})
    client.patch("/api/conversations/c1", json={"title": "  Nieuw  "})
    assert client.get("/api/conversations").json()[0]["title"] == "Nieuw"


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}])
def test_patch_conversation_rejects_empty_title(client, body):
    client.put("/api/conversations/c1", json={"title": "Oud", "timestamp": 1, "messages": []})
    resp = client.patch("/api/conversations/c1", json=body)
    assert resp.status_code == 422
    assert client.get("/api/conversations").json()[0]["title"] == "Oud"


def test_patch_unknown_conversation_returns_404(client):
    resp = client.patch("/api/conversations/bestaat-niet", json={"title": "X"})
    assert resp.status_code == 404


# ── Persoonsgegevens in de gesprekstitel (#552, F5) ──────────────────────────
# De frontend maakt van zo'n titel al een generieke; de server doet het ook, voor een
# aangepaste client of een directe API-aanroep. Maskeren, niet weigeren: autosave blijft werken.

PERSOONSGEGEVENS_IN_TITEL = ["BSN 111222333", "Mail jan@example.nl", "Bel 06 12345678"]
GEWONE_TITELS = ["Nummer 123456789", "Instroom hbo 2023", "Studenten HU 2024"]


def _bewaar(client, titel):
    return client.put("/api/conversations/c1", json={"title": titel, "timestamp": 1000, "messages": []})


def _titels(client):
    return client.get("/api/conversations").json()[0]["title"], client.get("/api/conversations/c1").json()["title"]


@pytest.mark.parametrize("titel", PERSOONSGEGEVENS_IN_TITEL)
def test_put_masks_personal_data_in_title(client, titel):
    resp = _bewaar(client, titel)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert _titels(client) == (GESPREKSTITEL_ZONDER_PERSOONSGEGEVENS,) * 2


@pytest.mark.parametrize("titel", PERSOONSGEGEVENS_IN_TITEL)
def test_patch_masks_personal_data_in_title(client, titel):
    _bewaar(client, "Oud")
    assert client.patch("/api/conversations/c1", json={"title": titel}).json() == {"ok": True}
    assert _titels(client) == (GESPREKSTITEL_ZONDER_PERSOONSGEGEVENS,) * 2


@pytest.mark.parametrize("titel", [111222333, 111222333.0])
def test_put_masks_bsn_sent_as_json_number(client, titel):
    assert _bewaar(client, titel).json() == {"ok": True}
    assert _titels(client) == (GESPREKSTITEL_ZONDER_PERSOONSGEGEVENS,) * 2


def test_put_and_patch_cut_a_long_title(client):
    """Een titel zonder grens zou de herkenning kwadratisch lang laten rekenen (#552)."""
    lang = "a" * 100_000
    assert _bewaar(client, lang).json() == {"ok": True}
    assert _titels(client) == ("a" * MAX_GESPREKSTITEL,) * 2
    assert client.patch("/api/conversations/c1", json={"title": "b" * 100_000}).json() == {"ok": True}
    assert _titels(client) == ("b" * MAX_GESPREKSTITEL,) * 2


@pytest.mark.parametrize("titel", GEWONE_TITELS)
def test_put_and_patch_keep_titles_without_personal_data(client, titel):
    _bewaar(client, titel)
    assert _titels(client) == (titel,) * 2
    client.patch("/api/conversations/c1", json={"title": f"{titel} (2)"})
    assert _titels(client) == (f"{titel} (2)",) * 2


# ── Workbooks (no auth) ──────────────────────────────────────────────────────


def test_get_workbooks_empty(client):
    resp = client.get("/api/workbooks")
    assert resp.status_code == 200
    assert resp.json() == []


def test_put_and_get_workbook(client):
    body = {
        "title": "Dashboard",
        "description": "test",
        "messages": [{"role": "user", "content": "data"}],
        "figures": [],
        "instelling": "HU",
        "htmlContent": "<html></html>",
        "createdAt": "2024-01-01T00:00:00Z",
    }
    resp = client.put("/api/workbooks/wb1", json=body)
    assert resp.status_code == 200

    resp = client.get("/api/workbooks")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "wb1"
    assert data[0]["title"] == "Dashboard"


def test_delete_workbook(client):
    client.put(
        "/api/workbooks/wb1",
        json={
            "title": "X",
            "description": "",
            "createdAt": "2024-01-01T00:00:00Z",
        },
    )
    resp = client.delete("/api/workbooks/wb1")
    assert resp.status_code == 200
    assert client.get("/api/workbooks").json() == []


# ── Auth enforcement ──────────────────────────────────────────────────────────


def test_auth_enabled_no_token_returns_401(authed_client):
    c = TestClient(authed_client.app)
    resp = c.get("/api/conversations")
    assert resp.status_code == 401


def test_auth_enabled_with_token_works(authed_client):
    authed_client.put("/api/conversations/c1", json={"title": "T", "timestamp": 1, "messages": []})
    resp = authed_client.get("/api/conversations")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
