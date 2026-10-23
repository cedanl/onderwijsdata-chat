"""Een bovengrens op de grootte van een verzoek (#682).

`PUT /api/conversations/{id}` en `PUT /api/workbooks/{id}` namen elk lichaam aan (`body: dict`, geen schema),
en uvicorn liet WebSocket-berichten tot 16 MiB toe. Eén ingelogde gebruiker kon zo het geheugen van de pod
en de database vullen. Gemeten op 23-10: het grootste gesprek 163 kB, het grootste werkboek 85 kB.
"""

import importlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import MAX_REQUEST_BYTES
from core.verzoeklimiet import TE_GROOT, Verzoeklimiet

DOCKERFILE = Path(__file__).parent.parent / "Dockerfile"


def _app(max_bytes: int) -> FastAPI:
    app = FastAPI()

    @app.put("/echo")
    def echo(body: dict) -> dict:
        return {"sleutels": len(body)}

    app.add_middleware(Verzoeklimiet, max_bytes=max_bytes)
    return app


def test_een_verzoek_onder_de_grens_komt_door():
    client = TestClient(_app(100))
    assert client.put("/echo", json={"a": 1}).json() == {"sleutels": 1}


def test_een_te_groot_verzoek_krijgt_413_op_zijn_lengte():
    client = TestClient(_app(100))
    response = client.put("/echo", json={"a": "x" * 200})
    assert response.status_code == 413
    assert response.json() == {"detail": TE_GROOT}


def test_een_te_groot_verzoek_zonder_lengte_krijgt_ook_413():
    """Chunked, dus zonder Content-Length: dan telt de middleware wat er binnenkomt."""
    client = TestClient(_app(100))

    def delen():
        yield b'{"a": "'
        yield b"x" * 200
        yield b'"}'

    response = client.put("/echo", content=delen(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.json() == {"detail": TE_GROOT}


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


@pytest.mark.parametrize("pad", ["/api/conversations/g1", "/api/workbooks/w1"])
def test_de_app_weigert_een_te_groot_gesprek_of_werkboek(client, pad):
    lichaam = {"title": "t", "timestamp": 1, "messages": [{"role": "user", "content": "x" * MAX_REQUEST_BYTES}]}
    response = client.put(pad, json=lichaam)
    assert response.status_code == 413
    assert response.json() == {"detail": TE_GROOT}
    # Ook een geweigerd verzoek draagt de beveiligingsheaders.
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_de_grens_laat_ruim_ruimte_boven_het_grootste_gemeten_gesprek():
    assert MAX_REQUEST_BYTES >= 20 * 163_000


def test_uvicorn_begrenst_websocketberichten_op_dezelfde_grens():
    regels = [r for r in DOCKERFILE.read_text().splitlines() if r.startswith("CMD ")]
    cmd = json.loads(regels[-1].removeprefix("CMD "))
    assert cmd[cmd.index("--ws-max-size") + 1] == str(MAX_REQUEST_BYTES)
