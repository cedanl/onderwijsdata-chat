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
