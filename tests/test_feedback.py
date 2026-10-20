import importlib
import json
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from core.feedback import QUESTIONS, validate_answers

_SCALE = next(q for q in QUESTIONS if q["type"] == "scale")
_CHOICE = next(q for q in QUESTIONS if q["type"] == "choice")
_TEXT = next(q for q in QUESTIONS if q["type"] == "text")
_MULTI = next(q for q in QUESTIONS if q["id"] == "dashboardtool")


def _stored() -> list[dict]:
    conn = sqlite3.connect(os.environ["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM feedback").fetchall()]
    conn.close()
    return rows


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    return db


def _client(tmp_path, monkeypatch, enabled: str = "true") -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ENABLE_FEEDBACK", enabled)
    monkeypatch.delenv("CHAT_USERS", raising=False)
    monkeypatch.delenv("CHAT_SECRET", raising=False)
    from core import auth, config

    importlib.reload(auth)
    importlib.reload(config)
    from persistence import db

    importlib.reload(db)
    db.init_db()
    from routes import config as config_route
    from routes import feedback as feedback_route

    importlib.reload(config_route)
    importlib.reload(feedback_route)
    import routes

    importlib.reload(routes)
    import server

    importlib.reload(server)
    return TestClient(server.app)


@pytest.fixture
def client(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    from persistence import db

    # Feedback mag alleen op een eigen werkboek (#389); zonder login heet iedereen "gast".
    for wb_id in ("wb-1", "wb-2"):
        db.upsert_workbook("gast", wb_id, "Instroom hbo", "")
    return client


def _body(**answers):
    return {
        "workbook_id": "wb-1",
        "report_type": "report",
        "report_title": "Instroom hbo",
        "answers": answers or {_SCALE["id"]: "4"},
    }


# ── Vragenlijst ──────────────────────────────────────────────────────────────


def test_questions_have_unique_ids_and_known_types():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids))
    assert 5 <= len(QUESTIONS) <= 12
    assert {q["type"] for q in QUESTIONS} <= {"scale", "choice", "multi", "text"}
    assert all(q["options"] for q in QUESTIONS if q["type"] != "text")


def test_validate_keeps_valid_answers_and_drops_empty_ones():
    answers = {_SCALE["id"]: _SCALE["options"][0], _TEXT["id"]: "  meer duiding  ", _CHOICE["id"]: ""}
    assert validate_answers(answers) == {_SCALE["id"]: _SCALE["options"][0], _TEXT["id"]: "meer duiding"}


def test_vertrouwen_heeft_een_eigen_toelichting():
    """Het waarom achter (wan)trouwen blijft gekoppeld aan de vertrouwensvraag, niet aan 'verbeteren'."""
    ids = [q["id"] for q in QUESTIONS]
    assert ids.index("vertrouwen_waarom") == ids.index("vertrouwen") + 1
    answers = {"vertrouwen": "Deels", "vertrouwen_waarom": "  De totalen tellen niet op.  "}
    assert validate_answers(answers) == {"vertrouwen": "Deels", "vertrouwen_waarom": "De totalen tellen niet op."}


def test_conferentievragen_staan_in_een_eigen_blok_over_de_instelling():
    """De vragen over de instelling (conferentie) volgen na de rapportvragen, onder één kopje."""
    ids = [q["id"] for q in QUESTIONS]
    start = ids.index("poc")
    assert QUESTIONS[start]["section"] == "Over jouw instelling"
    assert [q["id"] for q in QUESTIONS[start:]] == ["poc", "dashboardtool", "doelgroep", "ceda_oppakken", "contact"]
    assert [q["id"] for q in QUESTIONS if q.get("section")] == ["poc"]


def test_validate_multi_keeps_the_chosen_options_as_a_list():
    assert validate_answers({"dashboardtool": ["Power BI", "Tableau"]}) == {"dashboardtool": ["Power BI", "Tableau"]}


def test_validate_multi_accepts_anders_with_and_without_detail():
    assert validate_answers({"doelgroep": ["Studenten", "Anders: Alumni"]}) == {
        "doelgroep": ["Studenten", "Anders: Alumni"]
    }
    assert validate_answers({"doelgroep": ["Anders"]}) == {"doelgroep": ["Anders"]}
    assert validate_answers({"doelgroep": ["Anders:   Alumni "]}) == {"doelgroep": ["Anders: Alumni"]}


def test_validate_multi_drops_duplicates_and_empty_lists():
    assert validate_answers({"dashboardtool": ["Qlik", "Qlik"], "nuttig": "4"}) == {
        "dashboardtool": ["Qlik"],
        "nuttig": "4",
    }
    assert validate_answers({"dashboardtool": [], "nuttig": "4"}) == {"nuttig": "4"}


def test_contactgegevens_zijn_vrije_tekst_en_optioneel():
    assert validate_answers({"contact": "  a@b.nl "}) == {"contact": "a@b.nl"}
    assert validate_answers({"contact": " ", "poc": "3"}) == {"poc": "3"}


@pytest.mark.parametrize(
    "answers",
    [
        {"dashboardtool": "Power BI"},
        {"dashboardtool": ["Excel"]},
        {"dashboardtool": [5]},
        {"dashboardtool": ["Anders: " + "x" * 201]},
        {"dashboardtool": ["Anders:"]},
        {"nuttig": ["4"]},
        {"contact": ["a@b.nl"]},
        {},
        {_TEXT["id"]: "   "},
        {"onbekend": "x"},
        {_SCALE["id"]: "9"},
        {_CHOICE["id"]: "Wellicht"},
        {_TEXT["id"]: "x" * 2001},
        {_TEXT["id"]: 5},
    ],
)
def test_validate_rejects(answers):
    with pytest.raises(ValueError):
        validate_answers(answers)


# ── Opslag ───────────────────────────────────────────────────────────────────


def test_add_feedback_stores_one_row_per_submission(db):
    db.add_feedback("alice", "wb-1", "report", "Instroom hbo", {"nuttig": "4"})
    rows = _stored()
    assert len(rows) == 1
    row = rows[0]
    assert row["username"] == "alice"
    assert row["workbook_id"] == "wb-1"
    assert row["report_type"] == "report"
    assert row["report_title"] == "Instroom hbo"
    assert json.loads(row["answers"]) == {"nuttig": "4"}
    assert row["created_at"]


# ── API ──────────────────────────────────────────────────────────────────────


def test_config_announces_feedback(client):
    assert client.get("/api/config").json()["feedback_enabled"] is True


def test_get_questions(client):
    resp = client.get("/api/feedback/questions")
    assert resp.status_code == 200
    assert resp.json() == list(QUESTIONS)


def test_post_feedback_stores_it_for_the_user(client):
    resp = client.post("/api/feedback", json=_body())
    assert resp.status_code == 200
    rows = _stored()
    assert [(r["username"], r["workbook_id"]) for r in rows] == [("gast", "wb-1")]


def test_list_feedback_workbooks_per_user(db):
    db.add_feedback("alice", "wb-2", "report", "", {"nuttig": "4"})
    db.add_feedback("alice", "wb-1", "report", "", {"nuttig": "3"})
    db.add_feedback("alice", "wb-1", "report", "", {"nuttig": "5"})
    db.add_feedback("bob", "wb-3", "report", "", {"nuttig": "5"})
    assert db.list_feedback_workbooks("alice") == ["wb-1", "wb-2"]
    assert db.list_feedback_workbooks("carol") == []


def test_given_lists_reports_with_feedback_for_logged_in_user(client):
    from core.auth import get_current_user
    from persistence import db
    from server import app

    db.add_feedback("alice", "wb-1", "report", "", {"nuttig": "4"})
    app.dependency_overrides[get_current_user] = lambda: "alice"
    try:
        assert client.get("/api/feedback/given").json() == ["wb-1"]
    finally:
        app.dependency_overrides.clear()


def test_given_is_empty_for_guests(client):
    # Alle gasten heten "gast": hun feedback mag niet bij elkaar als gegeven tonen.
    assert client.post("/api/feedback", json=_body()).status_code == 200
    assert client.get("/api/feedback/given").json() == []


def test_post_feedback_rejects_invalid_answers(client):
    resp = client.post("/api/feedback", json=_body(onbekend="x"))
    assert resp.status_code == 422


def test_post_feedback_is_rate_limited_per_report(client):
    for _ in range(3):
        assert client.post("/api/feedback", json=_body()).status_code == 200
    resp = client.post("/api/feedback", json=_body())
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    other = {**_body(), "workbook_id": "wb-2"}
    assert client.post("/api/feedback", json=other).status_code == 200


def test_workbook_belongs_to(db):
    db.upsert_workbook("alice", "wb-1", "Instroom hbo", "")
    assert db.workbook_belongs_to("alice", "wb-1") is True
    assert db.workbook_belongs_to("bob", "wb-1") is False
    assert db.workbook_belongs_to("alice", "wb-onbekend") is False


def test_post_feedback_on_someone_elses_workbook_is_refused(client):
    from persistence import db

    db.upsert_workbook("alice", "wb-van-alice", "Instroom hbo", "")
    resp = client.post("/api/feedback", json={**_body(), "workbook_id": "wb-van-alice"})
    assert resp.status_code == 404
    assert _stored() == []


def test_feedback_disabled(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, enabled="false")
    assert client.get("/api/config").json()["feedback_enabled"] is False
    assert client.get("/api/feedback/questions").status_code == 404
    assert client.post("/api/feedback", json=_body()).status_code == 404
