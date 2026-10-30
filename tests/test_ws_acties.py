"""Per WebSocket-actie een handler in een dispatch-map (#206).

chat_websocket leest berichten en dispatcht; elke actie is los te testen met dezelfde
handtekening (msg, session, emit, lopende taak) -> lopende taak.
"""

import asyncio
import importlib
import json
import logging

import pytest

from agent import history
from core import config
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
        "ping",
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


def test_ping_antwoordt_pong_en_laat_de_taak_lopen():
    """#489: de hartslag van de frontend; het antwoord bewijst dat de lijn leeft."""
    session = chat._new_session()
    taak = object()

    terug, events = _run("ping", {}, session, taak)

    assert terug is taak
    assert events == [{"type": "pong"}]


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


def _dispatch(msg: dict, task=None):
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    async def scenario():
        return await chat._dispatch(msg, chat._new_session(), emit, task)

    return asyncio.run(scenario()), events


@pytest.mark.parametrize(
    "msg",
    [{"action": "bestaat-niet-31337"}, {}, {"action": []}, {"action": {"a": 1}}, {"action": None}],
    ids=["onbekend", "zonder-action", "lijst", "object", "null"],
)
def test_een_onbekende_actie_krijgt_direct_een_foutframe(msg):
    """#637: zonder antwoord wachtte de client tot zijn time-out; een lijst als actie gaf een TypeError."""
    taak = object()

    terug, events = _dispatch(msg, taak)

    assert terug is taak
    assert events == [{"type": "error", "message": chat.ONBEKENDE_ACTIE, "modelafhankelijk": False}]
    assert "31337" not in chat.ONBEKENDE_ACTIE


@pytest.mark.parametrize("actie", [["x" * 100_000], "y" * 100_000], ids=["lijst", "string"])
def test_een_onbekende_actie_logt_het_type_en_een_ingekorte_waarde(actie, caplog):
    """#637: de verbinding blijft open, dus een enorme actie mag niet per frame volledig in de log."""
    caplog.set_level(logging.WARNING, logger=chat.logger.name)

    _dispatch({"action": actie}, None)

    [regel] = [r.getMessage() for r in caplog.records if "Onbekende websocket-actie" in r.getMessage()]
    assert type(actie).__name__ in regel
    assert len(regel) < 200


@pytest.fixture
def ws_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    db.init_db()
    from fastapi.testclient import TestClient

    import server

    monkeypatch.setattr(chat, "AUTH_ENABLED", False)
    return TestClient(server.app)


MAX_FRAMES_TOT_PONG = 10


def _frames_tot_pong(ws, msg: dict) -> list[dict]:
    """De frames na msg tot en met de pong op een ping erachter, zonder de system_message over de API-key.

    Lezen tot de pong (en nooit een vast aantal) laat een test falen in plaats van eeuwig wachten als het
    foutframe uitblijft: de pong komt altijd, het foutframe niet. Het plafond begrenst de lus als er toch
    nooit een pong komt.
    """
    ws.send_text(json.dumps(msg))
    ws.send_text(json.dumps({"action": "ping"}))
    frames: list[dict] = []
    for _ in range(MAX_FRAMES_TOT_PONG):
        frame = json.loads(ws.receive_text())
        if frame["type"] == "system_message":
            continue
        frames.append(frame)
        if frame["type"] == "pong":
            return frames
    raise AssertionError(f"geen pong binnen {MAX_FRAMES_TOT_PONG} frames: {frames}")


def test_onbekende_actie_over_de_websocket_houdt_de_verbinding_open(ws_client):
    fout = {"type": "error", "message": chat.ONBEKENDE_ACTIE, "modelafhankelijk": False}
    with ws_client.websocket_connect("/api/chat") as ws:
        for msg in ({"action": "bestaat-niet"}, {}, {"action": []}):
            frames = _frames_tot_pong(ws, msg)
            assert frames == [fout, {"type": "pong"}], msg
            assert "bestaat-niet" not in json.dumps(frames)


# ─── Misvormde frames sluiten de verbinding niet (#758) ──────────────────────

_FOUT = {"type": "error", "message": chat.ONBEKENDE_ACTIE, "modelafhankelijk": False}


def _ruw_tot_pong(ws, raw: str) -> list[dict]:
    """Als _frames_tot_pong, maar het frame gaat ongewijzigd over de lijn, ook als het geen JSON is."""
    ws.send_text(raw)
    ws.send_text(json.dumps({"action": "ping"}))
    frames: list[dict] = []
    for _ in range(MAX_FRAMES_TOT_PONG):
        frame = json.loads(ws.receive_text())
        if frame["type"] == "system_message":
            continue
        frames.append(frame)
        if frame["type"] == "pong":
            return frames
    raise AssertionError(f"geen pong binnen {MAX_FRAMES_TOT_PONG} frames: {frames}")


@pytest.mark.parametrize(
    "raw",
    [
        "niet-json 31337",
        "[1, 2]",
        '"tekst 31337"',
        "5",
        "null",
        json.dumps({"action": "settings", "settings": "x"}),
        json.dumps({"action": "history", "messages": 5}),
    ],
    ids=["geen-json", "lijst", "string", "getal", "null", "settings-string", "history-getal"],
)
def test_een_misvormd_frame_wordt_geweigerd_en_de_verbinding_blijft(ws_client, raw, caplog):
    with caplog.at_level(logging.DEBUG), ws_client.websocket_connect("/api/chat") as ws:
        assert _ruw_tot_pong(ws, raw) == [_FOUT, {"type": "pong"}]
    # Het log noemt het type, niet de inhoud (#637).
    assert "31337" not in caplog.text


def test_na_settings_zonder_object_werkt_een_volgend_bericht(ws_client, monkeypatch):
    gevraagd = _zonder_agent(monkeypatch, maximum=1000)
    with ws_client.websocket_connect("/api/chat") as ws:
        _frames_tot_pong(ws, {"action": "settings", "settings": {"instelling": "HU"}})
        assert _frames_tot_pong(ws, {"action": "settings", "settings": "x"}) == [_FOUT, {"type": "pong"}]
        ws.send_text(json.dumps({"action": "message", "content": "Hoeveel studenten?"}))
        _frames_tot_pong(ws, {"action": "ping"})
    assert gevraagd == ["Hoeveel studenten?"]


def test_settings_zonder_object_laat_de_vorige_instellingen_staan():
    session = chat._new_session()
    session["chat_settings"] = {"instelling": "HU"}
    taak = object()

    terug, events = _run("settings", {"settings": ["x"]}, session, taak)

    assert session["chat_settings"] == {"instelling": "HU"}
    assert terug is taak and events == [_FOUT]


def test_history_zonder_lijst_laat_het_open_gesprek_en_de_taak_staan():
    session = chat._new_session()
    session["messages"] = [{"role": "user", "content": "eerder"}]
    taak = object()

    terug, events = _run("history", {"messages": 5, "conv_id": "c1"}, session, taak)

    assert session["messages"] == [{"role": "user", "content": "eerder"}]
    assert terug is taak and events == [_FOUT]


def test_een_andere_fout_in_de_lus_stopt_de_lopende_taak(ws_client, monkeypatch):
    """Eindigt de lus niet door een disconnect, dan draaide een taak door tot haar volgende emit."""
    gestopt: list = []
    taak = object()
    ronde = {"n": 0}

    async def dispatch(msg, session, emit, current_task):
        ronde["n"] += 1
        if ronde["n"] == 1:
            return taak
        raise RuntimeError("kapot")

    monkeypatch.setattr(chat, "_dispatch", dispatch)
    monkeypatch.setattr(chat, "_stop_task", lambda session, task: gestopt.append(task))
    with pytest.raises(RuntimeError), ws_client.websocket_connect("/api/chat") as ws:
        ws.send_text(json.dumps({"action": "message", "content": "a"}))
        ws.send_text(json.dumps({"action": "message", "content": "b"}))
        ws.receive_text()
        ws.receive_text()
    assert gestopt == [taak]


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


def test_een_opgevulde_verduidelijkingskeuze_gaat_gestript_door(monkeypatch):
    """Witruimte telt niet mee en gaat ook niet mee naar de agent: gemeten is wat verstuurd wordt."""
    gevraagd = _zonder_agent(monkeypatch)
    session = chat._new_session()

    terug, events = _run_tot_einde("clarification_choice", {"choice": " \n\t" * 1000 + "2024" + "  "}, session)

    assert isinstance(terug, asyncio.Task) and events == []
    assert gevraagd == ["2024"]
    assert session["clarify_keuzes"] == ["2024"]


def test_een_opgevulde_te_lange_verduidelijkingskeuze_wordt_geweigerd(monkeypatch):
    gevraagd = _zonder_agent(monkeypatch)
    session = chat._new_session()

    terug, events = _run("clarification_choice", {"choice": "  " + "y" * 11 + " \n" * 500}, session)

    assert terug is None and gevraagd == []
    assert session.get("clarify_keuzes", []) == []
    assert len(events) == 1 and events[0]["type"] == "error"
    assert "11 tekens" in events[0]["message"]


def test_een_lege_verduidelijkingskeuze_blijft_stil(monkeypatch):
    gevraagd = _zonder_agent(monkeypatch)
    session = chat._new_session()

    terug, events = _run("clarification_choice", {"choice": "  \n"}, session)

    assert terug is None and events == [] and gevraagd == []
    assert session.get("clarify_keuzes", []) == []


def test_invoer_die_geen_tekst_is_telt_als_leeg(monkeypatch):
    """Een zelfgebouwde client met een getal of null verbreekt de verbinding niet."""
    gevraagd = _zonder_agent(monkeypatch)
    vorige = _KlaarTaak()

    for action, sleutel in (("message", "content"), ("clarification_choice", "choice")):
        for waarde in (123, None, ["x" * 50], {"a": 1}):
            terug, events = _run(action, {sleutel: waarde}, chat._new_session(), vorige)
            assert terug is vorige and events == []
    assert gevraagd == []


def test_de_geschiedenis_kent_geen_lengtegrens_per_bericht(monkeypatch):
    """Oude gesprekken heropenen breekt nooit: de grens geldt alleen voor nieuwe invoer."""
    monkeypatch.setattr(chat, "MAX_MESSAGE_CHARS", 10)
    lang = "z" * 50

    berichten = chat._parse_history([{"role": "user", "content": lang}, {"role": "assistant", "content": lang}])

    assert berichten == [{"role": "user", "content": lang}, {"role": "assistant", "content": lang}]


def test_de_geschiedenis_heeft_een_totale_tekencap(monkeypatch):
    """#500 (S15): 40 beurten van willekeurige grootte bereiken het model niet meer.

    Boven HISTORY_MAX_CHARS vallen de oudste beurten af, zoals bij MAX_HISTORY.
    """
    monkeypatch.setattr(chat, "HISTORY_MAX_CHARS", 100)
    beurten = [{"role": "user", "content": f"vraag {i} " + "x" * 40} for i in range(40)]

    berichten = chat._parse_history(beurten)

    assert sum(len(m["content"]) for m in berichten) <= 100
    # De jongste beurten blijven staan, de oudste vallen af.
    assert berichten[-1]["content"].startswith("vraag 39")


def test_een_enkel_bericht_groter_dan_de_cap_wordt_afgekapt(monkeypatch):
    """Zelfs één monsterbeurt (1 miljoen tekens) opent nog, afgekapt in plaats van geweigerd."""
    monkeypatch.setattr(chat, "HISTORY_MAX_CHARS", 100)

    berichten = chat._parse_history([{"role": "assistant", "content": "y" * 1_000_000}])

    assert len(berichten) == 1
    assert len(berichten[0]["content"]) == 100


def test_een_heropend_lang_gesprek_houdt_zijn_eerste_vraag(monkeypatch):
    """#789: heropenen kort in zoals het live gesprek (agent/history.trim), niet door de oudste te laten vallen.

    De eerste vraag is het onderwerp van rapport en dashboard; een lang heropend gesprek raakte die kwijt.
    """
    monkeypatch.setattr(history, "MAX_HISTORY", 6)
    beurten = [{"role": r, "content": f"{r} {i}"} for i in range(6) for r in ("user", "assistant")]

    berichten = chat._parse_history(beurten)

    assert berichten[0] == {"role": "user", "content": "user 0"}
    assert berichten == [beurten[0], *beurten[-5:]]
    assert berichten == history.trim(beurten)[0]


def test_een_gewoon_gesprek_blijft_volledig_openen():
    beurten = [{"role": r, "content": f"beurt {i}"} for i, r in enumerate(["user", "assistant"] * 10)]
    assert chat._parse_history(beurten) == beurten


def test_na_het_afvallen_begint_de_geschiedenis_met_een_gebruikersbeurt(monkeypatch):
    """Providers geven een 400 op een historie die met een assistent-beurt begint."""
    monkeypatch.setattr(chat, "HISTORY_MAX_CHARS", 30)
    beurten = [
        {"role": "user", "content": "u" * 10},
        {"role": "assistant", "content": "a" * 10},
        {"role": "user", "content": "v" * 10},
        {"role": "assistant", "content": "b" * 10},
    ]

    berichten = chat._parse_history(beurten)

    # De cap houdt a, v en b over; het antwoord a zonder bijbehorende vraag valt ook af.
    assert berichten == beurten[2:]


def test_zonder_gebruikersbeurt_binnen_de_cap_blijft_de_historie_leeg(monkeypatch):
    monkeypatch.setattr(chat, "HISTORY_MAX_CHARS", 10)
    beurten = [{"role": "user", "content": "u" * 10}, {"role": "assistant", "content": "a" * 10}]

    assert chat._parse_history(beurten) == []


def test_een_historie_zonder_afgevallen_beurten_blijft_ongewijzigd_ook_met_assistent_eerst():
    beurten = [{"role": "assistant", "content": "welkom"}, {"role": "user", "content": "hoi"}]

    assert chat._parse_history(beurten) == beurten


def test_een_cap_van_nul_geeft_geen_lege_beurt(monkeypatch):
    monkeypatch.setattr(chat, "HISTORY_MAX_CHARS", 0)

    assert chat._parse_history([{"role": "user", "content": "hallo"}]) == []


def test_afkappen_tot_alleen_witruimte_geeft_geen_lege_beurt(monkeypatch):
    monkeypatch.setattr(chat, "HISTORY_MAX_CHARS", 3)

    assert chat._parse_history([{"role": "user", "content": "   hallo"}]) == []


@pytest.mark.parametrize(
    "omgeving",
    [{"HISTORY_MAX_CHARS": "0"}, {"HISTORY_MAX_CHARS": "-5"}, {"MAX_HISTORY": "0"}],
)
def test_de_tekencap_in_de_config_is_minimaal_een(monkeypatch, omgeving):
    for naam, waarde in omgeving.items():
        monkeypatch.setenv(naam, waarde)
    try:
        importlib.reload(config)
        assert config.HISTORY_MAX_CHARS >= 1
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_een_historie_precies_op_de_cap_blijft_volledig(monkeypatch):
    """Grens: een som van precies HISTORY_MAX_CHARS tekens valt niet af."""
    monkeypatch.setattr(chat, "HISTORY_MAX_CHARS", 30)
    beurten = [{"role": r, "content": "x" * 10} for r in ("user", "assistant", "user")]

    assert chat._parse_history(beurten) == beurten


def test_een_teken_boven_de_cap_laat_de_oudste_beurten_vallen(monkeypatch):
    monkeypatch.setattr(chat, "HISTORY_MAX_CHARS", 30)
    beurten = [{"role": r, "content": "x" * 10} for r in ("user", "assistant", "user", "assistant")]
    beurten[-1]["content"] = "x" * 11

    # 11 + 10 + 10 = 31 > 30: het antwoord op plek 1 past niet meer, de beurt ervoor ook niet.
    assert chat._parse_history(beurten) == beurten[2:]


# #750: de onderzoeksvraag die de gebruiker vóór het genereren bevestigde, gaat mee naar het rapport.
def _rapport_zonder_model(monkeypatch, maximum: int = 4000) -> list[dict]:
    gevraagd: list[dict] = []

    async def opnemen(session, emit, model, author=None, onderzoeksvraag=None):
        gevraagd.append({"author": author, "onderzoeksvraag": onderzoeksvraag})

    monkeypatch.setattr(chat, "MAX_MESSAGE_CHARS", maximum)
    monkeypatch.setattr(chat, "_generate_report", opnemen)
    return gevraagd


def test_generate_report_geeft_de_bevestigde_onderzoeksvraag_gestript_door(monkeypatch):
    gevraagd = _rapport_zonder_model(monkeypatch)

    terug, events = _run_tot_einde(
        "generate_report",
        {"author": "Anne", "onderzoeksvraag": "  Hoe ontwikkelt de wo-instroom zich?\n"},
        chat._new_session(),
    )

    assert isinstance(terug, asyncio.Task) and events == []
    assert gevraagd == [{"author": "Anne", "onderzoeksvraag": "Hoe ontwikkelt de wo-instroom zich?"}]


@pytest.mark.parametrize("msg", [{}, {"onderzoeksvraag": "   "}, {"onderzoeksvraag": ["geen tekst"]}])
def test_generate_report_zonder_onderzoeksvraag_houdt_het_onderwerp_van_het_gesprek(monkeypatch, msg):
    gevraagd = _rapport_zonder_model(monkeypatch)

    _run_tot_einde("generate_report", msg, chat._new_session())

    assert gevraagd == [{"author": None, "onderzoeksvraag": None}]


def test_een_te_lange_onderzoeksvraag_wordt_geweigerd_zonder_rapport(monkeypatch):
    gevraagd = _rapport_zonder_model(monkeypatch, maximum=10)
    vorige = _KlaarTaak()

    terug, events = _run("generate_report", {"onderzoeksvraag": "x" * 11}, chat._new_session(), vorige)

    assert terug is vorige and gevraagd == []
    assert len(events) == 1 and events[0]["type"] == "error" and events[0]["modelafhankelijk"] is False


# ─── Restpunten chatserver (#790) ────────────────────────────────────────────


def test_zonder_sleutel_krijgt_de_gebruiker_geen_beheerdersinstructie(ws_client, monkeypatch, caplog):
    """Een eindgebruiker heeft geen `.env` (#712): de melding zegt wat er speelt, de sleutelnamen staan in het log."""
    from core import config as core_config
    from core.errors import MODEL_ZONDER_SLEUTEL

    monkeypatch.setattr(core_config, "get_all_api_key_env_vars", lambda: ["ANTHROPIC_API_KEY"])
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(chat, "MODEL", "anthropic/claude-sonnet-5-5")
    with caplog.at_level(logging.WARNING), ws_client.websocket_connect("/api/chat") as ws:
        eerste = json.loads(ws.receive_text())

    assert eerste == {"type": "system_message", "message": MODEL_ZONDER_SLEUTEL}
    assert not any(w in MODEL_ZONDER_SLEUTEL for w in (".env", "omgevingsvariabele", "API_KEY", "herstart", "secret"))
    assert "ANTHROPIC_API_KEY" in caplog.text


def test_met_sleutel_volgt_geen_melding_over_de_sleutel(ws_client, monkeypatch):
    from core import config as core_config

    monkeypatch.setattr(core_config, "get_all_api_key_env_vars", lambda: ["ANTHROPIC_API_KEY"])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-sleutel")
    monkeypatch.setattr(chat, "MODEL", "anthropic/claude-sonnet-5-5")
    with ws_client.websocket_connect("/api/chat") as ws:
        ws.send_text(json.dumps({"action": "ping"}))
        assert json.loads(ws.receive_text()) == {"type": "pong"}


def test_een_figuur_gaat_alleen_bij_de_beurt():
    """De lijst van alle figuren van een verbinding werd nooit gelezen en groeide buiten het store-budget."""
    import plotly.graph_objects as go

    run = importlib.import_module("agent.run")  # `agent.run` is ook een functie in agent/__init__
    session = chat._new_session()
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(run._handle_figure("create_plot", go.Figure(), session, emit))

    assert "figures" not in session
    assert len(session["turn_figures"]) == 1
    assert [e["type"] for e in events] == ["figure"]


def test_de_server_zet_geen_eigen_sigterm_handler():
    """uvicorn installeert zijn eigen handlers; een sys.exit in een eigen handler brak de nette afsluiting af (#675).

    In een eigen proces: wat een import van server aan handlers zet, blijft hier anders hangen of is al gezet.
    """
    import subprocess
    import sys
    from pathlib import Path

    code = "import signal, server; print(signal.getsignal(signal.SIGTERM) is signal.SIG_DFL)"
    uit = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert uit.returncode == 0, uit.stderr[-2000:]
    assert uit.stdout.strip().splitlines()[-1] == "True"
