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


# ─── Maximale berichtlengte (#481, SECURITY.md S7) ──────────────────────────


def _zonder_agent(monkeypatch, maximum: int = 10) -> list[str]:
    """Small limit, and a _process_message that only records what it would have asked."""
    gevraagd: list[str] = []

    async def opnemen(content, session, emit, model):
        gevraagd.append(content)

    monkeypatch.setattr(chat, "MAX_MESSAGE_CHARS", maximum)
    monkeypatch.setattr(chat, "_process_message", opnemen)
    return gevraagd


class _KlaarTaak:
    """A previous run that has ended: not busy, and handed back unchanged on a refusal."""

    def done(self) -> bool:
        return True


def _run_tot_einde(action: str, msg: dict, session: dict, task=None):
    """Like _run, but awaits the task the handler started, inside the same event loop."""
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    async def scenario():
        terug = await chat.ACTIES[action]({"action": action, **msg}, session, emit, task)
        if terug is not None and terug is not task:
            await terug
        return terug

    return asyncio.run(scenario()), events


def test_de_standaard_maximale_berichtlengte_is_4000():
    from core import config

    assert isinstance(config.MAX_MESSAGE_CHARS, int)
    assert config.MAX_MESSAGE_CHARS == 4000


def test_een_te_lang_bericht_wordt_geweigerd_zonder_taak(monkeypatch):
    gevraagd = _zonder_agent(monkeypatch)
    session = chat._new_session()
    session["messages"] = [{"role": "user", "content": "eerder"}]
    vorige = _KlaarTaak()

    terug, events = _run("message", {"content": "x" * 11}, session, vorige)

    assert terug is vorige
    assert gevraagd == []
    assert session["messages"] == [{"role": "user", "content": "eerder"}]
    assert len(events) == 1
    event = events[0]
    assert event["type"] == "error" and event["modelafhankelijk"] is False
    assert "11" in event["message"] and "10" in event["message"]


def test_de_foutmelding_herhaalt_de_inhoud_niet(monkeypatch):
    _zonder_agent(monkeypatch)

    _, events = _run("message", {"content": "geheimgeheim"}, chat._new_session())

    assert "geheim" not in events[0]["message"]


def test_een_bericht_van_precies_het_maximum_wordt_verwerkt(monkeypatch):
    gevraagd = _zonder_agent(monkeypatch)

    terug, events = _run_tot_einde("message", {"content": "  " + "x" * 10 + " \n"}, chat._new_session())

    assert isinstance(terug, asyncio.Task)
    assert gevraagd == ["x" * 10]
    assert events == []


def test_drukte_gaat_voor_de_lengtecontrole(monkeypatch):
    _zonder_agent(monkeypatch)

    async def scenario():
        events: list[dict] = []

        async def emit(event):
            events.append(event)

        lopend = asyncio.create_task(asyncio.sleep(10))
        terug = await chat._handle_message({"content": "x" * 11}, chat._new_session(), emit, lopend)
        lopend.cancel()
        return terug is lopend, events

    zelfde, events = asyncio.run(scenario())

    assert zelfde
    assert [e["type"] for e in events] == ["busy"]


def test_een_leeg_bericht_blijft_stil(monkeypatch):
    gevraagd = _zonder_agent(monkeypatch)

    terug, events = _run("message", {"content": "   "}, chat._new_session())

    assert terug is None and events == [] and gevraagd == []


def test_een_te_lange_verduidelijkingskeuze_wordt_geweigerd(monkeypatch):
    gevraagd = _zonder_agent(monkeypatch)
    session = chat._new_session()

    terug, events = _run("clarification_choice", {"choice": "y" * 11}, session)

    assert terug is None and gevraagd == []
    assert session["messages"] == []
    assert session.get("clarify_keuzes", []) == []
    assert len(events) == 1
    assert events[0]["type"] == "error" and events[0]["modelafhankelijk"] is False


def test_een_gewone_verduidelijkingskeuze_werkt_nog(monkeypatch):
    gevraagd = _zonder_agent(monkeypatch)

    terug, events = _run_tot_einde("clarification_choice", {"choice": "2024/2025"}, chat._new_session())

    assert isinstance(terug, asyncio.Task)
    assert gevraagd == ["2024/2025"] and events == []


def test_de_geschiedenis_kent_geen_lengtegrens_per_bericht(monkeypatch):
    """Oude gesprekken heropenen breekt nooit: de grens geldt alleen voor nieuwe invoer."""
    monkeypatch.setattr(chat, "MAX_MESSAGE_CHARS", 10)
    lang = "z" * 50

    berichten = chat._parse_history([{"role": "user", "content": lang}, {"role": "assistant", "content": lang}])

    assert berichten == [{"role": "user", "content": lang}, {"role": "assistant", "content": lang}]
