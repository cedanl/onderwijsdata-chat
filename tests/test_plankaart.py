"""De plankaart vóór een vraag over meer bronnen, alleen met "Geavanceerd" (#1268).

Met het nepmodel (agent/nepmodel.py) door de websocket-handlers van routes/chat.py, zoals tests/test_ws_acties.py: de
zoekactie draait echt (de catalogus), de laders zijn nagebootst en tellen elke aanroep. Zo is te zien dat de kaart vóór
het eerste laden komt, dat "Klopt, ga door" precies het plan laadt en dat "Pas aan" niets laadt.
"""

import asyncio
import json

import pandas as pd
import pytest

import tools
from agent import nepmodel, plankaart
from agent.loop import ToolCall
from agent.run import tools_for
from core import geavanceerd
from routes import chat
from tools import SCHEMAS, store
from tools.canoniek import aanroep
from tools.store import KeyMeta

NEP = "mock/default"
KOPPELVRAAG = "Koppel de mbo-studenten en de ingeschrevenen in het ho per schooljaar"
EEN_BRON = "Hoeveel mbo-studenten zijn er landelijk?"
_MAAT_KEY = "cbs:85354NED:nep"
_DUO_KEY = "duo:p01hoinges:nep"


@pytest.fixture
def laders(monkeypatch):
    """Elke laadtool nagebootst; de lijst houdt elke aanroep bij, in volgorde, als (tool, argumenten)."""
    aanroepen: list[tuple[str, dict]] = []
    monkeypatch.setattr(tools.cbs, "definitions", lambda *a, **k: {})

    def get_maat(**args):
        aanroepen.append(("get_maat", args))
        rijen = [{"Perioden": "2023SJ00", "Perioden_label": "2023/'24", "MboStudenten_1": 512100}]
        store.put(_MAAT_KEY, pd.DataFrame(rijen), KeyMeta(bron="cbs", dataset="85354NED"))
        return json.dumps(
            {
                "data_key": _MAAT_KEY,
                "maat": args.get("maat"),
                "teldefinitie": "mbo-studenten landelijk",
                "periodekolom": "Perioden",
                "waardekolom": "MboStudenten_1",
                "rijen": rijen,
            }
        )

    def get_duo_data(**args):
        aanroepen.append(("get_duo_data", args))
        store.put(
            _DUO_KEY, pd.DataFrame({"STUDIEJAAR": [2023], "AANTAL": [1]}), KeyMeta(bron="duo", dataset="p01hoinges")
        )
        return json.dumps({"data_key": _DUO_KEY, "kolommen": ["STUDIEJAAR", "AANTAL"]})

    def andere_lader(naam):
        def lader(**args):
            aanroepen.append((naam, args))
            return json.dumps({"status": "error", "melding": "nagebootst"})

        return lader

    for naam in plankaart.LAADSTAPPEN:
        monkeypatch.setitem(tools._HANDLERS, naam, andere_lader(naam))
    monkeypatch.setitem(tools._HANDLERS, "get_maat", get_maat)
    monkeypatch.setitem(tools._HANDLERS, "get_duo_data", get_duo_data)
    return aanroepen


@pytest.fixture
def chat_met_nepmodel(monkeypatch, zonder_scopekaart):
    """De handlers zonder berichtlimiet en tokenbudget, met het nepmodel als model van elke vraag, en als gast."""

    async def binnen(session, emit):
        return True

    monkeypatch.setattr(chat, "_binnen_limiet", binnen)
    monkeypatch.setattr(chat, "_model", lambda session: NEP)
    monkeypatch.setattr(chat, "AUTH_ENABLED", False)


def _actie(actie: str, msg: dict, session: dict) -> list[dict]:
    """Eén websocket-actie met de lopende taak erachter afgewacht; de events die de client kreeg."""
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    async def scenario():
        taak = await chat.ACTIES[actie]({"action": actie, **msg}, session, emit, None)
        if taak is not None:
            await taak

    asyncio.run(scenario())
    return events


def _soort(events: list[dict], soort: str) -> list[dict]:
    return [e for e in events if e["type"] == soort]


def _laadstappen(aanroepen: list[tuple[str, dict]]) -> list[str]:
    return [aanroep(naam, args) for naam, args in aanroepen]


def _plan_keys() -> list[str]:
    return [aanroep(s["tool"], s["argumenten"]) for s in nepmodel.PLAN["stappen"]]


def _kaart(session: dict) -> list[dict]:
    """Een koppelvraag met Geavanceerd aan, tot de kaart: de events."""
    return _actie("message", {"content": KOPPELVRAAG, "geavanceerd": True}, session)


# ── Criterium 1: zonder Geavanceerd geen kaart, dezelfde stroom ──────────────


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_zonder_geavanceerd_krijgt_een_koppelvraag_geen_kaart_en_dezelfde_stroom(laders):
    """Gast zonder browserkeuze: dezelfde toolset en dezelfde events als een sessie die de plankaart niet kent."""
    session = chat._new_session()
    zonder = _actie("message", {"content": KOPPELVRAAG}, session)

    assert session[plankaart.AAN] is False
    assert tools_for(session) is SCHEMAS
    assert _soort(zonder, "plan") == []
    assert [n for n, _ in laders] == ["get_maat"]
    assert nepmodel.KOP in _soort(zonder, "message_end")[-1]["content"]

    # De stroom van vóór #1268: dezelfde vraag op een sessie zonder de sleutel `plankaart`.
    laders.clear()
    oud = chat._new_session()
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(chat._process_message(KOPPELVRAAG, oud, emit, NEP))
    assert plankaart.AAN not in oud
    assert [e["type"] for e in events] == [e["type"] for e in zonder]
    assert [n for n, _ in laders] == ["get_maat"]


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_met_login_en_geavanceerd_uit_geen_kaart_ook_als_de_client_het_vraagt(laders, monkeypatch):
    monkeypatch.setattr(chat, "AUTH_ENABLED", True)
    monkeypatch.setattr(geavanceerd, "lees", lambda gebruiker: False)
    session = chat._new_session(username="anna")

    events = _kaart(session)

    assert session[plankaart.AAN] is False
    assert _soort(events, "plan") == []
    assert [n for n, _ in laders] == ["get_maat"]


# ── Criterium 2: met Geavanceerd stopt de beurt vóór het eerste laden ────────


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_met_geavanceerd_stopt_een_koppelvraag_voor_het_eerste_laden(laders):
    session = chat._new_session()

    events = _kaart(session)

    [kaart] = _soort(events, "plan")
    assert laders == []  # nog geen enkele data-aanroep
    assert [e["name"] for e in _soort(events, "tool_start")] == ["search_catalog"]
    assert _soort(events, "message_end") == []
    assert kaart["vraag"] == KOPPELVRAAG
    assert kaart["sleutel"] == "schooljaar"
    assert kaart["duur"] == "ongeveer een minuut"
    maat, duo = kaart["bronnen"]
    assert maat["dataset"] == "85354NED" and maat["titel"].startswith("Mbo; studenten")
    assert maat["versie"].startswith("versie van ")
    assert "jaren: alle beschikbare jaren" in maat["selectie"] and "vorm: alle" in maat["selectie"]
    assert duo["dataset"] == "p01hoinges" and duo["titel"].startswith("Ingeschrevenen hoger onderwijs")
    assert duo["versie"] and duo["selectie"] == ["bestand: het standaardbestand"]
    # De beurt is geen antwoord: niets in `turns`, en het plan wacht in de sessie.
    assert session["turns"] == []
    assert session[plankaart.OPEN]["id"] == kaart["id"]
    assert session["messages"][-1] == {
        "role": "tool",
        "tool_call_id": session[plankaart.OPEN]["tool_call_id"],
        "content": plankaart.OPEN_MELDING,
    }
    assert session["messages"][-2]["content"] == kaart["tekst"]


def test_een_laadstap_in_dezelfde_ronde_als_het_plan_loopt_niet():
    session = {plankaart.AAN: True}
    plan = ToolCall("p", plankaart.TOOL_PLAN, "{}", nepmodel.PLAN)
    laad = ToolCall("l", "get_maat", "{}", {"maat": "mbo_studenten_landelijk"})

    assert (melding := plankaart.weigering(laad, [plan, laad], session, plankaart.Stand()))
    assert melding.startswith("Geweigerd")
    assert plankaart.weigering(laad, [laad], session, plankaart.Stand()) is None


def test_na_een_laadstap_in_deze_run_komt_er_geen_kaart_meer():
    """De kaart komt vóór het eerste laden; laadde het model al, dan gaat het door zonder kaart."""
    call = ToolCall("p", plankaart.TOOL_PLAN, "{}", nepmodel.PLAN)

    assert plankaart.afgekeurd(call, {plankaart.AAN: True}, plankaart.Stand()) is None
    melding = plankaart.afgekeurd(call, {plankaart.AAN: True}, plankaart.Stand(geladen=True))
    assert melding and "vóór het eerste laden" in melding


# ── Criterium 3: de kaarttekst komt uit code ─────────────────────────────────


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_een_modelsamenvatting_komt_niet_op_de_kaart(laders, monkeypatch):
    samenvatting = "Ik koppel straks alles aan alles, vertrouw me maar"
    monkeypatch.setattr(
        nepmodel, "PLAN", {**nepmodel.PLAN, "samenvatting": samenvatting, "sleutel": ["schooljaar", samenvatting]}
    )

    [kaart] = _soort(_kaart(chat._new_session()), "plan")

    assert samenvatting not in json.dumps(kaart, ensure_ascii=False)
    assert kaart["sleutel"] == "schooljaar"


def test_de_kaart_noemt_de_selectie_in_woorden_uit_de_argumenten():
    args = {
        "stappen": [
            {
                "tool": "get_cbs_data",
                "argumenten": {
                    "dataset_id": "85423NED",
                    "selectie": {
                        "dimensies": {"Geslacht": "T001038"},
                        "periode": ["2023SJ00", "2024SJ00"],
                        "sector": "hbo",
                    },
                },
            },
            {
                "tool": "get_maat",
                "argumenten": {"maat": "mbo_studenten_instelling", "instelling": "ROC Midden Nederland", "vorm": "bol"},
            },
        ],
        "sleutel": "brin",
    }
    stappen = [("get_cbs_dimension", json.dumps({"T001038": "Totaal mannen en vrouwen"}))]

    kaart = plankaart.maak(ToolCall("p", plankaart.TOOL_PLAN, "{}", args), "vraag", stappen)["kaart"]

    cbs, maat = kaart["bronnen"]
    assert cbs["selectie"] == ["jaren: 2023/24 en 2024/25", "sector: hbo", "Geslacht: Totaal mannen en vrouwen"]
    assert "instelling: ROC Midden Nederland" in maat["selectie"] and "vorm: bol" in maat["selectie"]
    assert kaart["sleutel"] == "brin"


# ── Criterium 4: "Klopt, ga door" voert precies het plan uit ─────────────────


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_klopt_ga_door_laadt_precies_het_getoonde_plan(laders):
    session = chat._new_session()
    [kaart] = _soort(_kaart(session), "plan")
    getoond = [s["key"] for s in session[plankaart.OPEN]["stappen"]]

    events = _actie("plan_bevestigen", {"id": kaart["id"], "geavanceerd": True}, session)

    uitgevoerd = [
        aanroep(c["name"], json.loads(c["arguments"]))
        for c in session["turns"][-1]["tool_calls"]
        if c["name"] in plankaart.LAADSTAPPEN
    ]
    assert uitgevoerd == getoond == _plan_keys()
    assert _laadstappen(laders)[: len(getoond)] == getoond
    assert _soort(events, "plan") == []
    slot = _soort(events, "message_end")[-1]
    assert nepmodel.KOP in slot["content"] and "512.100" in slot["content"]
    # De beurt is die van de oorspronkelijke vraag, zonder nieuw gebruikersbericht.
    assert session["turns"][-1]["question"] == KOPPELVRAAG
    assert [m["content"] for m in session["messages"] if m["role"] == "user"] == [KOPPELVRAAG]
    assert plankaart.OPEN not in session and plankaart.BEVESTIGD not in session


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_een_laadaanroep_buiten_het_plan_wordt_in_code_geweigerd(laders, monkeypatch):
    echt = nepmodel.keuze
    buiten = {"dataset_id": "mbo-studenten-per-instelling"}

    gezien: list[dict] = []

    def keuze(model, messages, tools_, tool_choice=None):
        stap = echt(model, messages, tools_, tool_choice)
        gezien.extend(m for m in messages if m.get("tool_call_id") == "nep-buiten" and m not in gezien)
        al = bool(gezien) or any(tc.get("id") == "nep-buiten" for m in messages for tc in m.get("tool_calls") or [])
        if (
            "tekst" in stap
            and any(m.get("role") == "tool" and m.get("tool_call_id") == "plan-1" for m in messages)
            and not al
        ):
            return {"tool": "get_duo_data", "argumenten": buiten, "id": "nep-buiten"}
        return stap

    monkeypatch.setattr(nepmodel, "keuze", keuze)
    monkeypatch.setattr(nepmodel, "stroom", _stroom_met_id(nepmodel.stroom))
    session = chat._new_session()
    [kaart] = _soort(_kaart(session), "plan")

    _actie("plan_bevestigen", {"id": kaart["id"], "geavanceerd": True}, session)

    assert ("get_duo_data", buiten) not in laders
    assert _laadstappen(laders) == _plan_keys()
    [geweigerd] = gezien  # de melding gaat terug naar het model, in plaats van een resultaat
    assert geweigerd["content"].startswith("Geweigerd: deze `get_duo_data`-aanroep staat niet in het plan")


def _stroom_met_id(stroom):
    """De stroom van het nepmodel, met het id dat een nagebootste keuze meegeeft (anders telt het nepmodel er een)."""

    async def met_id(model, messages, tools_, tool_choice=None):
        stap = nepmodel.keuze(model, messages, tools_, tool_choice)
        async for stuk in stroom(model, messages, tools_, tool_choice):
            for keuze in stuk.choices or []:
                for tc in keuze.delta.tool_calls or []:
                    tc.id = stap.get("id", tc.id)
            yield stuk

    return met_id


def test_de_guard_laat_alleen_de_stappen_van_het_bevestigde_plan_door():
    stappen = plankaart.stappen(nepmodel.PLAN)
    session = {plankaart.AAN: True, plankaart.BEVESTIGD: {"stappen": stappen}}
    zelfde = ToolCall("a", "get_maat", "{}", {"maat": "mbo_studenten_landelijk"})
    andere_jaren = ToolCall("b", "get_maat", "{}", {"maat": "mbo_studenten_landelijk", "schooljaren": ["2024/25"]})
    geen_lader = ToolCall("c", "query_data", "{}", {"data_key": _MAAT_KEY})

    assert plankaart.weigering(zelfde, [zelfde], session, plankaart.Stand()) is None
    assert plankaart.weigering(geen_lader, [geen_lader], session, plankaart.Stand()) is None
    melding = plankaart.weigering(andere_jaren, [andere_jaren], session, plankaart.Stand())
    assert melding and "niet in het plan" in melding


# ── Criterium 5: de antwoordcontrole draait na bevestiging ongewijzigd ───────


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_een_fout_getal_wordt_ook_na_bevestiging_ingetrokken(laders, monkeypatch):
    echt = nepmodel.keuze

    def keuze(model, messages, tools_, tool_choice=None):
        stap = echt(model, messages, tools_, tool_choice)
        if "tekst" not in stap or not any(m.get("tool_call_id") == "plan-0" for m in messages):
            return stap
        correctie = str(messages[-1].get("content", "")).startswith("Controle van je antwoord")
        return {
            "tekst": f"{nepmodel.KOP} " + ("Geen aantal." if correctie else f"Er zijn {nepmodel.VERZONNEN} studenten.")
        }

    monkeypatch.setattr(nepmodel, "keuze", keuze)
    session = chat._new_session()
    [kaart] = _soort(_kaart(session), "plan")

    events = _actie("plan_bevestigen", {"id": kaart["id"], "geavanceerd": True}, session)

    ingetrokken = [e for e in _soort(events, "message_cancel") if e.get("reden")]
    assert ingetrokken
    slot = _soort(events, "message_end")[-1]
    assert nepmodel.VERZONNEN not in slot["content"] and "27135" not in slot["content"]


# ── Criterium 6: "Pas aan" verliest de vraag niet en laadt niets ─────────────


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_pas_aan_laadt_niets_en_houdt_de_vraag(laders):
    session = chat._new_session()
    [kaart] = _soort(_kaart(session), "plan")
    tool_call_id = session[plankaart.OPEN]["tool_call_id"]

    events = _actie("plan_aanpassen", {"id": kaart["id"]}, session)

    assert events == [] and laders == []
    assert plankaart.OPEN not in session
    assert session["messages"][0] == {"role": "user", "content": KOPPELVRAAG}
    resultaat = next(m for m in session["messages"] if m.get("tool_call_id") == tool_call_id)
    assert resultaat["content"] == plankaart.AANGEPAST_MELDING
    # Daarna is er niets meer te bevestigen.
    fout = _actie("plan_bevestigen", {"id": kaart["id"], "geavanceerd": True}, session)
    assert fout == [{"type": "error", "message": chat.PLAN_VERLOPEN, "modelafhankelijk": False}]
    assert laders == []


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_bevestigen_van_een_onbekend_plan_start_niets(laders):
    session = chat._new_session()
    _kaart(session)

    fout = _actie("plan_bevestigen", {"id": "bestaat-niet", "geavanceerd": True}, session)

    assert fout == [{"type": "error", "message": chat.PLAN_VERLOPEN, "modelafhankelijk": False}]
    assert laders == [] and plankaart.OPEN in session


# ── Criterium 7: één bron of een vaste maat krijgt geen kaart ────────────────


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_een_vraag_over_een_bron_krijgt_geen_kaart_ook_met_geavanceerd(laders):
    events = _actie("message", {"content": EEN_BRON, "geavanceerd": True}, chat._new_session())

    assert _soort(events, "plan") == []
    assert [n for n, _ in laders] == ["get_maat"]


@pytest.mark.parametrize(
    "plan",
    [
        {"stappen": [{"tool": "get_duo_data", "argumenten": {"dataset_id": "p01hoinges"}}]},
        {
            "stappen": [
                {"tool": "get_duo_data", "argumenten": {"dataset_id": "p01hoinges"}},
                {"tool": "get_duo_data", "argumenten": {"dataset_id": "p01hoinges", "resource": 1}},
            ]
        },
        {
            "stappen": [
                {"tool": "get_maat", "argumenten": {"maat": "mbo_studenten_landelijk"}},
                {"tool": "get_maat", "argumenten": {"maat": "deelnemers_ho_landelijk", "sector": "hbo"}},
            ]
        },
    ],
    ids=["een-stap", "een-bron", "vaste-maten"],
)
@pytest.mark.usefixtures("chat_met_nepmodel")
def test_een_plan_over_een_bron_of_vaste_maten_wordt_geen_kaart(laders, monkeypatch, plan):
    monkeypatch.setattr(nepmodel, "PLAN", plan)
    session = chat._new_session()

    events = _kaart(session)

    assert _soort(events, "plan") == []
    assert plankaart.OPEN not in session
    afgekeurd = next(m for m in session["turns"][-1]["tool_calls"] if m["name"] == plankaart.TOOL_PLAN)
    assert afgekeurd  # het model vroeg het, kreeg een melding en ging door
    assert _soort(events, "message_end")


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_een_bevestigd_plan_vraagt_geen_tweede_kaart_en_telt_niet_als_verduidelijking(laders, monkeypatch):
    aangeboden: list[set[str]] = []
    echt = nepmodel.keuze

    def keuze(model, messages, tools_, tool_choice=None):
        aangeboden.append({t["function"]["name"] for t in tools_ or []})
        return echt(model, messages, tools_, tool_choice)

    monkeypatch.setattr(nepmodel, "keuze", keuze)
    session = chat._new_session()
    _kaart(session)
    session["clarify_rondes"] = 2
    session["clarify_keuzes"] = ["2024/25"]
    kaart_id = session[plankaart.OPEN]["id"]
    aangeboden.clear()

    events = _actie("plan_bevestigen", {"id": kaart_id, "geavanceerd": True}, session)

    assert _soort(events, "plan") == []
    assert aangeboden and all(plankaart.TOOL_PLAN not in namen for namen in aangeboden)
    assert all("clarify_scope" in namen for namen in aangeboden)
    assert session["clarify_rondes"] == 2 and session["clarify_keuzes"] == ["2024/25"]


def test_na_drie_verduidelijkingen_kan_de_plankaart_nog_wel():
    """De plankaart is geen vierde verduidelijkingskaart: de limiet van clarify_scope blijft, het plan staat er los van."""
    namen = {t["function"]["name"] for t in tools_for({"clarify_rondes": 3, plankaart.AAN: True})}

    assert "clarify_scope" not in namen and plankaart.TOOL_PLAN in namen


# ── Criterium 8: de server beslist over Geavanceerd ──────────────────────────


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_met_login_leest_de_server_geavanceerd_bij_elk_verzoek_uit_de_database(laders, monkeypatch):
    monkeypatch.setattr(chat, "AUTH_ENABLED", True)
    stand = {"aan": True}
    gelezen: list[str] = []

    def lees(gebruiker):
        gelezen.append(gebruiker)
        return stand["aan"]

    monkeypatch.setattr(geavanceerd, "lees", lees)
    session = chat._new_session(username="anna")

    met = _actie("message", {"content": KOPPELVRAAG}, session)  # zonder vlag van de client: de database beslist
    stand["aan"] = False
    zonder = _actie("message", {"content": KOPPELVRAAG, "geavanceerd": True}, session)

    assert len(_soort(met, "plan")) == 1
    assert _soort(zonder, "plan") == []
    assert gelezen.count("anna") >= 2


@pytest.mark.usefixtures("chat_met_nepmodel")
def test_een_gast_krijgt_de_kaart_alleen_met_de_boolean_in_het_bericht(laders):
    session = chat._new_session()
    _actie("settings", {"settings": {"geavanceerd": True}}, session)

    in_settings = _actie("message", {"content": KOPPELVRAAG}, session)
    als_tekst = _actie("message", {"content": KOPPELVRAAG, "geavanceerd": "true"}, session)
    met_vlag = _actie("message", {"content": KOPPELVRAAG, "geavanceerd": True}, session)

    assert "geavanceerd" not in session["chat_settings"]
    assert _soort(in_settings, "plan") == [] and _soort(als_tekst, "plan") == []
    assert len(_soort(met_vlag, "plan")) == 1


def test_plan_bevestigen_is_een_run_actie():
    """Het token geldt opnieuw vóór de run van een bevestigd plan (#786), net als bij een vraag."""
    assert "plan_bevestigen" in chat.RUN_ACTIES and "plan_aanpassen" not in chat.RUN_ACTIES
