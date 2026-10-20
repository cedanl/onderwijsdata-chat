"""Exporteer al mijn gegevens (#645, deel 1 van #485): alles onder het eigen account, niets van een ander.

Twee accounts in CHAT_USERS, elk met gesprekken, werkboeken, feedback van alle soorten en datarecepten.
De export van Anna bevat precies haar rijen; geen tekst die alleen van Bert is, staat erin. Tokens worden
direct gemaakt, niet via de login: de login-limiter telt over de hele testrun mee.
"""

import importlib
import json
import logging
import re
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from persistence import db, export

_SOORTEN = ["conversations", "workbooks", "feedback", "algemene_feedback", "answer_feedback", "data_recipes"]
_EXPORT = "/api/mijn-gegevens/export"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CHAT_USERS", "anna:wachtwoord-a,bert:wachtwoord-b,leeg:wachtwoord-c")
    monkeypatch.setenv("CHAT_SECRET", "test-secret-for-tests")
    from core import auth

    importlib.reload(auth)
    import server

    importlib.reload(server)
    db.init_db()
    return TestClient(server.app)


def _als(client: TestClient, gebruiker: str) -> TestClient:
    from core import auth

    client.headers["Authorization"] = f"Bearer {auth.make_token(gebruiker)}"
    return client


def _gesprek(tekst: str) -> list[dict]:
    return [
        {"role": "user", "content": f"Vraag {tekst}"},
        {"role": "assistant", "content": f"Antwoord {tekst}", "tools": []},
    ]


def _vul(gebruiker: str, uniek: str) -> None:
    """Twee gesprekken, twee werkboeken (een rapport met HTML) en van elke andere soort een rij."""
    db.upsert_conversation(gebruiker, f"{gebruiker}-c1", f"Gesprek {uniek}", 1_700_000_000, _gesprek(uniek))
    db.upsert_conversation(gebruiker, f"{gebruiker}-c2", "Tweede", 1_700_000_100, _gesprek(f"{uniek}-2"))
    db.upsert_workbook(
        gebruiker,
        f"{gebruiker}-w1",
        f"Rapport {uniek}",
        "",
        messages=_gesprek(uniek),
        figures=[{"data": [], "layout": {"title": uniek}}],
        html_content=f"<html><body>{uniek}-html</body></html>",
        created_at="2026-10-14T10:00:00Z",
    )
    db.upsert_workbook(
        gebruiker,
        f"{gebruiker}-w2",
        "Dashboard",
        "",
        dashboard_spec={"titel": f"spec-{uniek}"},
        created_at="2026-10-15T10:00:00Z",
    )
    db.add_feedback(gebruiker, f"{gebruiker}-w1", "report", f"Rapport {uniek}", {"nuttig": f"4-{uniek}"})
    db.add_algemene_feedback(gebruiker, "idee", f"algemeen-{uniek}", "/chat")
    db.upsert_answer_feedback(
        gebruiker, f"{gebruiker}-c1", 1, "omlaag", f"toelichting-{uniek}", {"vraag": f"trace-{uniek}"}
    )
    db.save_recipes(gebruiker, f"{gebruiker}-c1", {f"key-{uniek}": {"laad": ["query_data", {"id": uniek}]}})


def _export(client: TestClient, gebruiker: str) -> tuple[dict, str]:
    response = _als(client, gebruiker).get(_EXPORT)
    assert response.status_code == 200
    return json.loads(response.text), response.text


# ── Toegang en vorm ──────────────────────────────────────────────────────────


def test_zonder_sessie_401(client):
    assert client.get(_EXPORT).status_code == 401
    client.headers["Authorization"] = "Bearer ongeldig"
    assert client.get(_EXPORT).status_code == 401


def test_de_export_is_geldige_json_met_alle_soorten(client):
    _vul("anna", "ANNA-UNIEK")
    data, _ = _export(client, "anna")
    assert list(data) == ["schema_version", "exported_at", "username", *_SOORTEN]
    assert data["schema_version"] == 1
    assert data["username"] == "anna"
    assert datetime.fromisoformat(data["exported_at"]).utcoffset() == timedelta(0)
    assert all(isinstance(data[soort], list) for soort in _SOORTEN)


def test_bijlage_met_datum_json_en_nooit_in_een_cache(client):
    response = _als(client, "leeg").get(_EXPORT)
    vandaag = datetime.now(UTC).strftime("%Y-%m-%d")
    assert response.headers["content-disposition"] == f'attachment; filename="openedudata-mijn-gegevens-{vandaag}.json"'
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store"
    assert json.loads(response.text)["exported_at"].startswith(vandaag)


def test_een_gebruiker_zonder_gegevens_krijgt_zes_lege_lijsten(client):
    _vul("anna", "ANNA-UNIEK")
    data, _ = _export(client, "leeg")
    assert data["username"] == "leeg"
    assert [data[soort] for soort in _SOORTEN] == [[]] * 6


# ── Inhoud en isolatie ───────────────────────────────────────────────────────


def test_alleen_de_eigen_rijen_per_soort(client):
    _vul("anna", "ANNA-UNIEK")
    _vul("bert", "BERT-UNIEK")
    data, body = _export(client, "anna")

    assert [c["id"] for c in data["conversations"]] == ["anna-c2", "anna-c1"]
    assert [w["id"] for w in data["workbooks"]] == ["anna-w2", "anna-w1"]
    assert [f["workbook_id"] for f in data["feedback"]] == ["anna-w1"]
    assert [f["tekst"] for f in data["algemene_feedback"]] == ["algemeen-ANNA-UNIEK"]
    assert [(f["conversation_id"], f["message_index"]) for f in data["answer_feedback"]] == [("anna-c1", 1)]
    assert [(r["conv_id"], r["data_key"]) for r in data["data_recipes"]] == [("anna-c1", "key-ANNA-UNIEK")]
    assert "BERT" not in body
    assert "bert" not in body


def test_json_kolommen_zijn_ontleed(client):
    _vul("anna", "ANNA-UNIEK")
    data, _ = _export(client, "anna")

    assert data["conversations"][1]["messages"] == _gesprek("ANNA-UNIEK")
    rapport = next(w for w in data["workbooks"] if w["id"] == "anna-w1")
    assert rapport["html_content"] == "<html><body>ANNA-UNIEK-html</body></html>"
    assert rapport["messages"] == _gesprek("ANNA-UNIEK")
    assert rapport["figures"] == [{"data": [], "layout": {"title": "ANNA-UNIEK"}}]
    assert rapport["dashboard_spec"] is None
    dashboard = next(w for w in data["workbooks"] if w["id"] == "anna-w2")
    assert dashboard["dashboard_spec"] == {"titel": "spec-ANNA-UNIEK"}
    assert dashboard["messages"] is None
    assert dashboard["figures"] is None
    assert dashboard["html_content"] is None
    assert data["feedback"][0]["answers"] == {"nuttig": "4-ANNA-UNIEK"}
    oordeel = data["answer_feedback"][0]
    assert (oordeel["oordeel"], oordeel["toelichting"]) == ("omlaag", "toelichting-ANNA-UNIEK")
    assert oordeel["trace"] == {"vraag": "trace-ANNA-UNIEK"}
    assert data["data_recipes"][0]["recipe"] == {"laad": ["query_data", {"id": "ANNA-UNIEK"}]}


def test_niet_ascii_blijft_leesbaar(client):
    db.upsert_conversation("anna", "c1", "Café", 1_700_000_000, _gesprek("één"))
    _, body = _export(client, "anna")
    assert "Café" in body
    assert "één" in body


def test_een_onleesbare_json_kolom_gaat_als_tekst_mee(client):
    db.upsert_conversation("anna", "c1", "Oud", 1_700_000_000, [])
    with db._connection() as conn:
        db._execute(conn, "UPDATE conversations SET messages = ? WHERE id = ?", ("{kapot", "c1"))
        conn.commit()
    data, _ = _export(client, "anna")
    assert data["conversations"][0]["messages"] == "{kapot"


def test_losgekoppelde_feedback_hoort_bij_niemand(client):
    _vul("anna", "ANNA-UNIEK")
    assert _als(client, "anna").delete("/api/conversations/anna-c1").status_code == 200
    with db._connection() as conn:
        losgekoppeld = db._execute(conn, "SELECT username FROM answer_feedback").fetchall()
    assert [r["username"] for r in losgekoppeld] == [db.VERWIJDERDE_GEBRUIKER]

    data, body = _export(client, "anna")
    assert data["answer_feedback"] == []
    assert "toelichting-ANNA-UNIEK" not in body
    # Ook een account dat toevallig zo heet, krijgt ze niet.
    assert list(export.answer_feedback(db.VERWIJDERDE_GEBRUIKER)) == []


def test_geen_tokens_of_hashes_in_de_export(client):
    from core import auth

    _vul("anna", "ANNA-UNIEK")
    ingetrokken = auth.make_token("anna")
    auth.revoke_token(ingetrokken)
    with db._connection() as conn:
        hashes = [r["token_hash"] for r in db._execute(conn, "SELECT token_hash FROM revoked_tokens").fetchall()]
    assert hashes

    response = _als(client, "anna").get(_EXPORT)
    token = client.headers["Authorization"].removeprefix("Bearer ")
    for geheim in [*hashes, ingetrokken, token]:
        assert geheim not in response.text
    assert "revoked" not in response.text


# ── Log en opbouw ────────────────────────────────────────────────────────────


def test_het_log_telt_alleen(client, caplog):
    _vul("anna", "ANNA-UNIEK")
    caplog.set_level(logging.INFO)
    _export(client, "anna")

    log = "\n".join(r.getMessage() for r in caplog.records)
    assert "conversations=2" in log
    assert "answer_feedback=1" in log
    for tekst in ("Vraag ANNA-UNIEK", "Antwoord ANNA-UNIEK", "toelichting-ANNA-UNIEK", "algemeen-ANNA-UNIEK", "anna"):
        assert tekst not in log


def test_de_stukken_vormen_samen_de_json(tmp_path, monkeypatch):
    """De generator alleen, zonder app: kop, dan per soort een lijst, met een vaste tijd."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    db.init_db()
    nu = datetime(2026, 10, 20, 9, 30, tzinfo=UTC)
    stukken = list(export.export_json_chunks("niemand-in-deze-db", nu))
    assert len(stukken) > 1
    data = json.loads("".join(stukken))
    assert data["exported_at"] == "2026-10-20T09:30:00+00:00"
    assert [data[soort] for soort in _SOORTEN] == [[]] * 6


def test_werkboeken_een_voor_een(client, monkeypatch):
    """Eerst de ids, daarna per werkboek één query, pas als het vorige al is geschreven (#633).

    Bij elk werkboek dat de generator oplevert, zijn er precies zoveel werkboeken uit de database
    gehaald als er al zijn geschreven: hij laadt er nooit vooruit, dus nooit alle HTML tegelijk.
    """
    groot = "x" * 200_000
    for i in range(5):
        db.upsert_workbook("anna", f"w{i}", f"R{i}", "", html_content=groot, created_at=f"2026-10-1{i}")

    opgehaald: list[str] = []
    echte_rij = export._rij

    def tel(sql, params):
        if "html_content" in sql:
            opgehaald.append(params[0])
        return echte_rij(sql, params)

    monkeypatch.setattr(export, "_rij", tel)
    geschreven = 0
    for stuk in export.export_json_chunks("anna"):
        if groot in stuk:
            geschreven += 1
            assert len(opgehaald) == geschreven
            assert len(stuk) < len(groot) + 1000
    assert geschreven == 5
    assert opgehaald == ["w4", "w3", "w2", "w1", "w0"]


def test_elke_query_filtert_op_de_gebruiker(monkeypatch):
    """Geen query zonder `username = ?`, en elke parameterlijst draagt de gebruikersnaam."""
    queries: list[tuple[str, tuple]] = []

    def vang(sql, params):
        queries.append((sql, params))
        return []

    monkeypatch.setattr(export, "_rijen", vang)
    list(export.export_json_chunks("anna"))
    assert len(queries) == 6
    for sql, params in queries:
        assert re.search(r"WHERE username = \?", sql)
        assert "anna" in params
