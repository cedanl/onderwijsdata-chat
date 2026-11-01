import importlib
import json

import pytest
from fastapi.testclient import TestClient

from core.foutmeldingen import ONGELDIGE_INVOER
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
    # Een echt token zonder de login-route: de login-limiet geldt voor de hele testrun.
    c.headers["Authorization"] = f"Bearer {auth.make_token('testuser')}"
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
    resp = client.get("/api/conversations/bestaat-niet")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Gesprek niet gevonden"}


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


def test_een_hernoemd_gesprek_houdt_zijn_titel_bij_de_volgende_opslag(client):
    """#757: elke opslag na een antwoord stuurt de automatische titel mee; die mag een gekozen titel niet overschrijven."""
    vraag = [{"role": "user", "content": "Hoeveel studenten?"}]
    client.put("/api/conversations/c1", json={"title": "Hoeveel studenten?", "timestamp": 1000, "messages": vraag})
    client.patch("/api/conversations/c1", json={"title": "Analyse instroom"})

    verder = [*vraag, {"role": "assistant", "content": "Zoveel."}, {"role": "user", "content": "En in 2022?"}]
    client.put("/api/conversations/c1", json={"title": "Hoeveel studenten?", "timestamp": 2000, "messages": verder})

    [conv] = client.get("/api/conversations").json()
    assert conv["title"] == "Analyse instroom"
    assert conv["timestamp"] == 2000
    assert client.get("/api/conversations/c1").json()["messages"] == verder


def _beurt(vraag: str, antwoord: str) -> list[dict]:
    return [{"role": "user", "content": vraag}, {"role": "assistant", "content": antwoord}]


def _put(c, messages, conv_id="c1"):
    return c.put(f"/api/conversations/{conv_id}", json={"title": "v1", "timestamp": 1000, "messages": messages})


def test_een_tweede_tabblad_overschrijft_de_beurten_van_het_eerste_niet(client):
    """#760: tabblad 2 bewaarde vraag B; tabblad 1, dat B niet kent, krijgt 409 en B blijft staan."""
    basis = _beurt("v1", "a1")
    assert _put(client, [*basis, *_beurt("vB", "aB")]).status_code == 200

    resp = _put(client, [*basis, *_beurt("vA", "aA")])

    assert resp.status_code == 409
    assert "ander tabblad" in resp.json()["detail"]
    assert client.get("/api/conversations/c1").json()["messages"] == [*basis, *_beurt("vB", "aB")]


def test_een_verouderde_opslag_met_minder_vragen_krijgt_409(client):
    """Een tabblad dat achterloopt en alleen een antwoord wijzigt, zou vraag 2 weggooien."""
    _put(client, [*_beurt("v1", "a1"), *_beurt("v2", "a2")])

    assert _put(client, _beurt("v1", "a1 anders")).status_code == 409


def test_een_verlengd_gesprek_en_een_gewijzigd_antwoord_worden_bewaard(client):
    """Eén tabblad: elke opslag verlengt de vragen of wijzigt een antwoord (#548/#635); dat blijft werken."""
    _put(client, _beurt("v1", "a1"))
    verlengd = [*_beurt("v1", "a1"), *_beurt("v2", "a2")]
    assert _put(client, verlengd).status_code == 200
    gewijzigd = [*_beurt("v1", "a1"), *_beurt("v2", "a2, nu volledig")]
    assert _put(client, gewijzigd).status_code == 200
    assert _put(client, gewijzigd).status_code == 200

    assert client.get("/api/conversations/c1").json()["messages"] == gewijzigd


def test_de_controle_op_vragen_kijkt_alleen_naar_het_gesprek_van_dezelfde_gebruiker(authed_client):
    """Isolatie per gebruiker (ON CONFLICT (id, username)): een gesprek van een ander met hetzelfde id telt niet mee."""
    from persistence import db

    db.upsert_conversation("iemand-anders", "c1", "Geheim", 1000, [*_beurt("v1", "a1"), *_beurt("vB", "aB")])

    assert _put(authed_client, [*_beurt("v1", "a1"), *_beurt("vA", "aA")]).status_code == 200
    assert authed_client.get("/api/conversations/c1").json()["messages"][-2]["content"] == "vA"
    anders = db.get_conversation("iemand-anders", "c1")
    assert anders is not None
    assert anders["messages"][-2]["content"] == "vB"


def test_twee_schrijvers_tegelijk_de_tweede_overschrijft_niet(client, monkeypatch):
    """Tabblad 2 schrijft nadat tabblad 1 de bewaarde versie las, maar vóór het zijn versie schrijft.

    De vergelijking zag nog de oude versie; het schrijven mag dan niet slagen, anders is vraag B weg.
    """
    from persistence import db

    _put(client, _beurt("v1", "a1"))
    tabblad_2 = [*_beurt("v1", "a1"), *_beurt("vB", "aB")]
    origineel = db._execute
    gelezen = []

    def tussendoor(conn, sql, params=()):
        resultaat = origineel(conn, sql, params)
        if sql.startswith("SELECT messages FROM conversations") and not gelezen:
            gelezen.append(True)
            with db._connection() as ander:
                origineel(
                    ander,
                    "UPDATE conversations SET messages = ? WHERE id = ? AND username = ?",
                    (json.dumps(tabblad_2), *params),
                )
                ander.commit()
        return resultaat

    monkeypatch.setattr(db, "_execute", tussendoor)
    resp = _put(client, [*_beurt("v1", "a1"), *_beurt("vA", "aA")])
    monkeypatch.setattr(db, "_execute", origineel)

    assert resp.status_code == 409
    assert client.get("/api/conversations/c1").json()["messages"] == tabblad_2


def test_de_eerste_opslag_zet_de_titel(client):
    client.put("/api/conversations/c1", json={"title": "Hoeveel studenten?", "timestamp": 1000, "messages": []})
    assert client.get("/api/conversations").json()[0]["title"] == "Hoeveel studenten?"


def test_patch_conversation_strips_title(client):
    client.put("/api/conversations/c1", json={"title": "Oud", "timestamp": 1, "messages": []})
    client.patch("/api/conversations/c1", json={"title": "  Nieuw  "})
    assert client.get("/api/conversations").json()[0]["title"] == "Nieuw"


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}])
def test_patch_conversation_rejects_empty_title(client, body):
    client.put("/api/conversations/c1", json={"title": "Oud", "timestamp": 1, "messages": []})
    resp = client.patch("/api/conversations/c1", json=body)
    assert resp.status_code == 422
    assert resp.json() == {"detail": ONGELDIGE_INVOER}
    assert client.get("/api/conversations").json()[0]["title"] == "Oud"


@pytest.mark.parametrize("limit", ["500", "0", "999777"])
def test_list_with_invalid_limit_is_a_dutch_string_without_the_input(client, limit):
    """#637: pydantic's list echoed the value and spoke English ("Input should be ...")."""
    resp = client.get("/api/conversations", params={"limit": limit})
    assert resp.status_code == 422
    assert resp.json() == {"detail": ONGELDIGE_INVOER}
    assert "999777" not in resp.text and "Input should" not in resp.text


def test_patch_unknown_conversation_returns_404(client):
    resp = client.patch("/api/conversations/bestaat-niet", json={"title": "X"})
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Gesprek niet gevonden"}


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


@pytest.mark.parametrize("titel", [["BSN 111222333"], [111222333], {"t": "BSN 111222333"}, True])
def test_put_never_stores_a_title_that_is_neither_text_nor_number(client, titel):
    """Postgres slaat een JSON-lijst als tekst op, BSN en al; de server bewaart dus alleen gecontroleerde tekst."""
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
    assert data[0]["type"] == "report"
    assert "html_content" not in data[0]

    werkboek = client.get("/api/workbooks/wb1").json()
    assert werkboek["html_content"] == "<html></html>"
    assert werkboek["instelling"] == "HU"


def test_get_workbook_dat_er_niet_is(client):
    assert client.get("/api/workbooks/bestaat-niet").status_code == 404


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


def test_unknown_conversation_with_a_valid_token_is_404(authed_client):
    """#637, point 3: not reproduced; the reported 401 came from a request without Authorization header."""
    resp = authed_client.get("/api/conversations/bestaat-niet-123")
    assert resp.status_code == 404
    assert resp.content == b'{"detail":"Gesprek niet gevonden"}'


def test_unknown_conversation_without_authorization_header_is_401(authed_client):
    resp = TestClient(authed_client.app).get("/api/conversations/bestaat-niet-123")
    assert resp.status_code == 401
    assert resp.content == b'{"detail":"Niet geautoriseerd"}'


def test_auth_enabled_with_token_works(authed_client):
    authed_client.put("/api/conversations/c1", json={"title": "T", "timestamp": 1, "messages": []})
    resp = authed_client.get("/api/conversations")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
