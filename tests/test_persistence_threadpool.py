"""Databaseaanroepen horen in de threadpool, niet op de event loop (#508).

De databaselaag is synchroon. Een `async def`-handler die haar rechtstreeks aanroept, zet
de event loop stil zolang de aanroep loopt, en daarmee elke lopende chat-stream van alle
gebruikers. Een gewone `def`-handler draait FastAPI in zijn threadpool.
"""

import asyncio
import importlib
import inspect
import threading
import time

import httpx
import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
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
    return server.app


@pytest.mark.asyncio
async def test_trage_databaseaanroep_houdt_een_gelijktijdig_verzoek_niet_tegen(app, monkeypatch):
    from persistence import db

    def traag(*args, **kwargs):
        time.sleep(0.5)
        return []

    monkeypatch.setattr(db, "list_conversations", traag)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Op een geblokkeerde loop komt de slaap van 0,1 s pas na de databaseaanroep van 0,5 s terug,
        # en /health dus ook; de klok loopt daarom vanaf het starten van het trage verzoek.
        start = time.perf_counter()
        trage = asyncio.create_task(client.get("/api/conversations"))
        await asyncio.sleep(0.1)
        snel = await client.get("/health")
        duur = time.perf_counter() - start
        assert snel.status_code == 200
        assert duur < 0.4, (
            f"/health kwam pas na {duur:.2f}s: de databaseaanroep van een ander verzoek hield de loop vast"
        )
        assert (await trage).status_code == 200


@pytest.mark.asyncio
async def test_readiness_check_draait_de_database_in_een_thread(monkeypatch):
    import health
    from persistence import db

    aanroep_thread = []
    monkeypatch.setattr(db, "ping", lambda: aanroep_thread.append(threading.current_thread()))
    assert await health.check_database_connection() is True
    assert aanroep_thread and aanroep_thread[0] is not threading.main_thread()


@pytest.mark.asyncio
async def test_readiness_check_meldt_een_onbereikbare_database(monkeypatch):
    import health
    from persistence import db

    def kapot():
        raise RuntimeError("geen verbinding")

    monkeypatch.setattr(db, "ping", kapot)
    assert await health.check_database_connection() is False


def test_handlers_met_databaseaanroepen_zijn_geen_coroutines():
    """Het patroon zelf vastgepind: een nieuwe `async def` met een databaseaanroep valt hier."""
    from fastapi.routing import APIRoute

    from routes import answer_feedback, feedback, persistence

    routes = [r for router in (persistence.router, feedback.router, answer_feedback.router) for r in router.routes]
    assert routes and all(isinstance(r, APIRoute) for r in routes)
    for route in routes:
        assert isinstance(route, APIRoute)
        assert not inspect.iscoroutinefunction(route.endpoint), f"{route.path} draait op de event loop"


# ── De denylist en het recept achter een snippet: ook uit de database, dus niet op de loop (#763) ──


def _op_de_loop() -> bool:
    """Draait de aanroeper op de event loop? In een thread van to_thread is er geen lopende loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def test_de_websocket_handshake_leest_de_denylist_buiten_de_loop(app, monkeypatch):
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from core.auth import WS_SUBPROTOCOL
    from routes import chat

    op_loop: list[bool] = []

    def verify(token):
        op_loop.append(_op_de_loop())
        return None

    monkeypatch.setattr(chat, "AUTH_ENABLED", True)
    monkeypatch.setattr(chat, "verify_token", verify)
    with (
        pytest.raises(WebSocketDisconnect) as gesloten,
        TestClient(app).websocket_connect("/api/chat", subprotocols=[WS_SUBPROTOCOL, "verlopen-token"]) as ws,
    ):
        ws.receive_text()

    assert gesloten.value.code == 4001
    assert op_loop == [False]


def test_dashboard_refresh_leest_de_denylist_buiten_de_loop(app, monkeypatch):
    from fastapi.testclient import TestClient

    from routes import chat

    op_loop: list[bool] = []

    def verify(token):
        op_loop.append(_op_de_loop())
        return None

    monkeypatch.setattr(chat, "AUTH_ENABLED", True)
    monkeypatch.setattr(chat, "DASHBOARDS_ENABLED", True)
    monkeypatch.setattr(chat, "verify_token", verify)
    antwoord = TestClient(app).post("/api/dashboard/refresh", json={}, headers={"Authorization": "Bearer x"})

    assert antwoord.status_code == 401
    assert op_loop == [False]


@pytest.mark.asyncio
async def test_de_snippet_na_een_tool_blokkeert_de_loop_niet(monkeypatch):
    from agent import loop as loop_module
    from agent.loop import ToolCall
    from tools import store

    gezien: list = []

    def traag(name, args, result, recept_van=None):
        gezien.append((_op_de_loop(), store.eigen_keys()))
        time.sleep(0.5)
        return "snippet"

    monkeypatch.setattr(loop_module, "dispatch", lambda name, args: ("resultaat", None))
    monkeypatch.setattr(loop_module, "_generate_snippet", traag)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    import pandas as pd

    store.put("cbs:85423NED", pd.DataFrame({"JAAR": ["2025"]}))
    with store.gesprek(lambda: ["cbs:85423NED"]):
        taak = asyncio.create_task(loop_module._execute_tool(ToolCall("t1", "query_data", "{}", {}), emit))
        start = time.perf_counter()
        await asyncio.sleep(0.01)
        duur = time.perf_counter() - start
        await taak
    store.clear()

    assert duur < 0.2, f"de loop stond {duur:.2f}s stil voor één snippet"
    # De snippet ziet in de thread dezelfde keys als het gesprek: to_thread neemt de context mee.
    assert gezien == [(False, ["cbs:85423NED"])]
    assert next(e for e in events if e["type"] == "tool_end")["snippet"] == "snippet"
