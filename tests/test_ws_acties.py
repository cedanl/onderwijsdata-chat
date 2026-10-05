"""Per WebSocket-actie een handler in een dispatch-map (#206).

chat_websocket leest berichten en dispatcht; elke actie is los te testen met dezelfde
handtekening (msg, session, emit, lopende taak) -> lopende taak.
"""

import asyncio

from routes import chat


def _run(action: str, msg: dict, session: dict, task=None):
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    async def scenario():
        return await chat.ACTIES[action]({"action": action, **msg}, session, emit, task)

    return asyncio.run(scenario()), events


def test_elke_actie_van_de_frontend_heeft_een_handler():
    assert set(chat.ACTIES) == {
        "stop",
        "reset",
        "settings",
        "history",
        "message",
        "clarification_choice",
        "generate_dashboard",
        "generate_report",
        "refresh_dashboard",
    }


def test_stop_zet_het_stopsignaal_en_laat_de_taak_lopen():
    session = chat._new_session()
    session["stop_event"] = asyncio.Event()
    taak = object()

    terug, events = _run("stop", {}, session, taak)

    assert session["stop_event"].is_set()
    assert terug is taak and events == []


def test_reset_begint_een_nieuw_gesprek_en_meldt_dat():
    session = chat._new_session(username="alice")
    session["messages"] = [{"role": "user", "content": "oud"}]

    terug, events = _run("reset", {}, session)

    assert terug is None
    assert session["messages"] == [] and session["username"] == "alice"
    assert events == [{"type": "reset_done"}]


def test_settings_vervangt_de_instellingen():
    session = chat._new_session()

    terug, events = _run("settings", {"settings": {"model": "x"}}, session)

    assert session["chat_settings"] == {"model": "x"}
    assert terug is None and events == []


def test_history_opent_een_opgeslagen_gesprek():
    session = chat._new_session()
    session["turns"] = [{"question": "vorig"}]

    terug, _ = _run("history", {"messages": [{"role": "user", "content": "Hallo"}]}, session)

    assert terug is None
    assert session["turns"] == []
    assert session["messages"] == [{"role": "user", "content": "Hallo"}]


def test_een_onbekende_actie_wordt_genegeerd():
    async def scenario():
        async def emit(event):
            raise AssertionError(event)

        return await chat._dispatch({"action": "bestaat_niet"}, chat._new_session(), emit, None)

    assert asyncio.run(scenario()) is None
