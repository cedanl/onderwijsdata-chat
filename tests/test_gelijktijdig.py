"""Begrenzing van wat er tegelijk loopt op één pod (#688).

De berichtlimiet telt verzoeken in de tijd; hier gaat het om het aantal open chatverbindingen en
gelijktijdige model- en sandboxruns. Boven een grens een leesbare melding, geen stille wachtrij.
"""

import asyncio
import importlib
import json
import threading

import pandas as pd
import pytest
from starlette.websockets import WebSocketDisconnect

from core.gelijktijdig import DRUK, Druk, Procesplaatsen, Runplaatsen, Verbindingen
from routes import chat
from tools import sandbox

# ── Verbindingen ──


def test_per_gebruiker_en_in_totaal():
    v = Verbindingen(per_sleutel=2, totaal=3)
    assert v.open("anna") and v.open("anna")
    assert not v.open("anna")  # derde van anna
    assert v.open("bob")
    assert not v.open("carla")  # totaal vol
    assert v.aantal == 3

    v.sluit("anna")
    assert v.open("carla")


def test_zonder_gebruiker_telt_alleen_het_totaal():
    v = Verbindingen(per_sleutel=1, totaal=3)
    assert v.open(None) and v.open(None) and v.open(None)
    assert not v.open(None)
    v.sluit(None)
    assert v.open(None)


def test_een_geweigerde_verbinding_telt_niet_mee():
    v = Verbindingen(per_sleutel=1, totaal=10)
    assert v.open("anna")
    assert not v.open("anna")
    v.sluit("anna")
    assert v.aantal == 0
    assert v.open("anna")


# ── Runplaatsen ──


def test_een_run_wacht_op_een_plaats_en_krijgt_anders_een_melding():
    async def scenario():
        plaatsen = Runplaatsen(max_tegelijk=1, wacht_s=0.05)
        async with plaatsen.plaats():
            with pytest.raises(Druk, match="druk"):
                async with plaatsen.plaats():
                    pass
        # Na het vrijgeven is er weer plaats.
        async with plaatsen.plaats():
            return True

    assert asyncio.run(scenario())


def test_een_wachtende_run_start_zodra_er_plaats_vrijkomt():
    async def scenario():
        plaatsen = Runplaatsen(max_tegelijk=1, wacht_s=1)
        volgorde = []

        async def run(naam, duur):
            async with plaatsen.plaats():
                volgorde.append(f"{naam} start")
                await asyncio.sleep(duur)
                volgorde.append(f"{naam} klaar")

        await asyncio.gather(run("a", 0.05), run("b", 0))
        return volgorde

    assert asyncio.run(scenario()) == ["a start", "a klaar", "b start", "b klaar"]


def test_de_chat_start_geen_run_als_het_te_druk_is(monkeypatch):
    gestart = []
    vrij: list[asyncio.Event] = []

    async def lange_run(content, session, emit, model):
        gestart.append(content)
        await vrij[0].wait()

    monkeypatch.setattr(chat, "_process_message", lange_run)

    async def scenario():
        vrij.append(asyncio.Event())
        monkeypatch.setattr(chat, "_runplaatsen", Runplaatsen(max_tegelijk=1, wacht_s=0.05))
        events: list[dict] = []

        async def emit(event):
            events.append(event)

        eerste = await chat.ACTIES["message"]({"content": "eerste"}, chat._new_session(username="anna"), emit, None)
        await asyncio.sleep(0)
        tweede = await chat.ACTIES["message"]({"content": "tweede"}, chat._new_session(username="bob"), emit, None)
        assert eerste is not None and tweede is not None
        await tweede
        vrij[0].set()
        await eerste
        return events

    events = asyncio.run(scenario())
    assert gestart == ["eerste"]
    assert events == [{"type": "error", "message": DRUK, "modelafhankelijk": False}]


# ── De WebSocket ──


def _pong(ws) -> bool:
    """Ping en lees tot het antwoord: zonder modelsleutel komt eerst een systeemmelding."""
    ws.send_text(json.dumps({"action": "ping"}))
    return any(json.loads(ws.receive_text())["type"] == "pong" for _ in range(3))


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
    from fastapi.testclient import TestClient

    return TestClient(server.app)


def test_een_verbinding_te_veel_krijgt_een_melding_en_1013(client, monkeypatch):
    verbindingen = Verbindingen(per_sleutel=1, totaal=1)
    monkeypatch.setattr(chat, "_verbindingen", verbindingen)

    with client.websocket_connect("/api/chat") as eerste:
        with client.websocket_connect("/api/chat") as tweede:
            melding = json.loads(tweede.receive_text())
            assert melding["type"] == "error" and "te veel vensters" in melding["message"]
            with pytest.raises(WebSocketDisconnect) as dicht:
                tweede.receive_text()
            assert dicht.value.code == 1013
        assert verbindingen.aantal == 1
        assert _pong(eerste)

    # De plaats komt vrij als de browser sluit, ook voor de volgende.
    with client.websocket_connect("/api/chat") as derde:
        assert _pong(derde)
    assert verbindingen.aantal == 0


# ── De sandbox ──


def test_de_sandbox_draait_niet_meer_processen_dan_toegestaan(monkeypatch):
    plaatsen = Procesplaatsen(max_tegelijk=1, wacht_s=0.05)
    monkeypatch.setattr(sandbox, "_PROCESSEN", plaatsen)
    monkeypatch.setattr(sandbox, "_voer_uit", lambda *a: pytest.fail("geen kindproces zonder plaats"))

    with plaatsen.plaats() as vrij:
        assert vrij
        uitkomst = sandbox.voer_uit("result = 1", pd.DataFrame(), {})
    assert uitkomst.fout == sandbox.BEZET


def test_procesplaatsen_werken_over_threads():
    plaatsen = Procesplaatsen(max_tegelijk=1, wacht_s=1)
    bezet, los = threading.Event(), threading.Event()

    def houd_vast():
        with plaatsen.plaats():
            bezet.set()
            los.wait()

    t = threading.Thread(target=houd_vast)
    t.start()
    bezet.wait()
    threading.Timer(0.05, los.set).start()
    with plaatsen.plaats() as vrij:
        assert vrij
    t.join()
