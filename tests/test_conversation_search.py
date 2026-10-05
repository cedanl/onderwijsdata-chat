"""Zoeken in de gespreksgeschiedenis, op titel en inhoud (#124)."""

import importlib

import pytest
from fastapi.testclient import TestClient


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
    c = TestClient(server.app)
    gesprekken = [
        ("c1", "Instroom mbo", 1000, [{"role": "user", "content": "Hoeveel studenten bij ROC Tilburg?"}]),
        ("c2", "Uitval hbo", 2000, [{"role": "assistant", "content": "Eén op de vijf stopt in het eerste jaar."}]),
        ("c3", "Diploma's wo", 3000, [{"role": "user", "content": "rendement"}]),
    ]
    for conv_id, title, ts, messages in gesprekken:
        c.put(f"/api/conversations/{conv_id}", json={"title": title, "timestamp": ts, "messages": messages})
    return c


def _ids(client, **params):
    resp = client.get("/api/conversations", params=params)
    assert resp.status_code == 200
    return [c["id"] for c in resp.json()]


def test_zoekt_in_de_titel(client):
    assert _ids(client, q="uitval") == ["c2"]


def test_zoekt_in_de_berichten(client):
    assert _ids(client, q="tilburg") == ["c1"]


def test_vindt_tekens_buiten_ascii(client):
    assert _ids(client, q="eén op") == ["c2"]


def test_zoekt_niet_in_de_opslagstructuur(client):
    """'content' en 'role' zijn sleutels in de opgeslagen JSON, geen tekst uit het gesprek."""
    assert _ids(client, q="content") == []


def test_lege_zoekterm_geeft_de_gewone_lijst(client):
    assert _ids(client, q="  ") == ["c3", "c2", "c1"]


def test_resultaat_houdt_de_volgorde_en_het_limiet(client):
    assert _ids(client, q="o", limit=2) == ["c3", "c2"]
