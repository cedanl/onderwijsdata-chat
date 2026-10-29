"""Een data-key overleeft een herstart: zijn recept staat in de database, de data komt terug uit de bron (#472).

De store leeft in het geheugen. store.clear() plus recepten.wis() is hier de herstart: weg
is alles wat het proces wist, over blijft wat de database bewaarde.
"""

import asyncio
import json
import os
import sqlite3
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from agent import recepten
from agent.dashboard import herstel_data
from agent.session_data import herstel_data_keys, record_data_key
from routes import chat
from tools import herlaad, store
from tools.analysis import run_analysis
from tools.cbs import get_cbs_data
from tools.duo import get_duo_data
from tools.query import query_data
from tools.rio import get_rio_data
from tools.schemas import TOOL_GET_CBS_DATA, TOOL_GET_DUO_DATA, TOOL_GET_RIO_DATA, TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS

pytestmark = pytest.mark.usefixtures("zonder_scopegrens")

_CBS_DEFS = {
    "Onderwijssoort": {"type": "Dimension"},
    "Perioden": {"type": "TimeDimension"},
    "Ingeschrevenen_1": {"type": "Topic"},
}
_CBS_ROWS = [
    {"Onderwijssoort": "A025294", "Perioden": "2024SJ00", "Ingeschrevenen_1": 378490},
    {"Onderwijssoort": "A025294", "Perioden": "2025SJ00", "Ingeschrevenen_1": 367960},
]
_DUO_DF = pd.DataFrame(
    {"STUDIEJAAR": [2024, 2024, 2025], "OPLEIDINGSVORM": ["VT", "DT", "VT"], "AANTAL": [27135, -1, 26370]}
)
_RIO_ROWS = [{"code": "30TX", "naam": "Aeres"}, {"code": "25DW", "naam": "HU"}]


def _cbs_get(dataset_id, endpoint, **params):
    return [{"Description": "De cijfers zijn afgerond op tientallen."}] if endpoint == "TableInfos" else []


@contextmanager
def _bronnen(cbs_data=None):
    """Alle drie de bronnen, nagebootst; `cbs_data` vervangt de CBS-aanroep (een fout, een teller)."""
    with (
        patch("tools.cbs.data", cbs_data or MagicMock(return_value=_CBS_ROWS)),
        patch("tools.cbs.definitions", return_value=_CBS_DEFS),
        patch("tools.cbs.get", side_effect=_cbs_get),
        patch("tools.duo._duo.load", side_effect=lambda *_: _DUO_DF.copy()),
        patch("tools.duo_meta.teldefinitie", return_value="natuurlijke personen"),
        patch("tools.rio.fetch", return_value=_RIO_ROWS),
        patch("tools.herlaad.catalogus_laatste_update", return_value="2026-04-14"),
    ):
        yield


_LADERS = {TOOL_GET_CBS_DATA: get_cbs_data, TOOL_GET_DUO_DATA: get_duo_data, TOOL_GET_RIO_DATA: get_rio_data}
_ROOTS = {
    "cbs": (TOOL_GET_CBS_DATA, {"dataset_id": "85423NED"}),
    "duo": (TOOL_GET_DUO_DATA, {"dataset_id": "p01hoinges", "resource": 0}),
    "rio": (TOOL_GET_RIO_DATA, {"resource": "erkenningen"}),
}


def _stap(session: dict, name: str, args: dict, result: str | None = None) -> str:
    """Eén toolstap zoals de chat hem doet: de tool, en daarna record_data_key met de aanroep."""
    if result is None:
        result = query_data(**args) if name == TOOL_QUERY_DATA else _LADERS[name](**args)
    record_data_key(session, result, {"name": name, "arguments": args})
    return json.loads(result)["data_key"]


def _analyse(**args) -> str:
    uitkomst = run_analysis(**args)
    assert isinstance(uitkomst, str), "een tabel, geen figuur"
    return uitkomst


def _opslaan(username: str, conv_id: str, *keys: str) -> None:
    """Wat PUT /api/conversations doet: het gesprek met zijn exporteerbare tabellen."""
    recepten.bewaar(username, conv_id, [{"role": "assistant", "tools": [{"exportKey": k} for k in keys]}])


def _herstart() -> None:
    store.clear()
    recepten.wis()


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    db.init_db()
    return db


@pytest.fixture
def client(database, monkeypatch):
    """De app met inloggen aan, zonder modules te herladen: niets blijft achter voor de volgende test."""
    from core import auth

    monkeypatch.setattr(auth, "AUTH_ENABLED", True)
    import server

    return TestClient(server.app)


def _als(username: str) -> dict:
    from core import auth

    return {"Authorization": f"Bearer {auth.make_token(username)}"}


def _csv(client, key: str, username: str = "alice"):
    return client.get("/api/data/csv", params={"key": key}, headers=_als(username))


_NOTITIE = "# let op: opnieuw opgehaald op "


def _zonder_notitie(csv: str) -> str:
    """De CSV zonder BOM en zonder de regel die zegt dat de data opnieuw is opgehaald."""
    return "".join(r for r in csv.lstrip("\ufeff").splitlines(keepends=True) if not r.startswith(_NOTITIE))


# ── Root-keys per bron ──────────────────────────────────────────────────────


@pytest.mark.parametrize("bron", ["cbs", "duo", "rio"])
def test_root_key_geeft_na_een_herstart_dezelfde_csv(client, bron):
    session = {"username": "alice"}
    with _bronnen():
        key = _stap(session, *_ROOTS[bron])
        _opslaan("alice", "c1", key)
        eerst = _csv(client, key)
        _herstart()
        daarna = _csv(client, key)

    assert eerst.status_code == 200 and daarna.status_code == 200
    assert _zonder_notitie(daarna.text) == _zonder_notitie(eerst.text)
    assert "X-Data-Herladen" not in eerst.headers and _NOTITIE not in eerst.text
    assert "de bron kan intussen zijn gewijzigd" in daarna.headers["X-Data-Herladen"]
    # De CSV zelf zegt het ook, bovenaan: wie het bestand opent, ziet het.
    assert daarna.text.lstrip("\ufeff").startswith(_NOTITIE)


@pytest.mark.parametrize("bron", ["cbs", "duo", "rio"])
def test_herladen_meta_is_gelijk_aan_het_origineel(database, bron):
    with _bronnen():
        key = _stap({"username": "alice"}, *_ROOTS[bron])
        origineel = store.meta(key)
        cellen = store.get(key).isna().sum().sum()
        _opslaan("alice", "c1", key)
        _herstart()
        uitkomst = recepten.terughalen("alice", key)

    assert uitkomst is not None and uitkomst.gelukt and uitkomst.herladen
    nieuw = store.meta(key)
    assert nieuw is not None and origineel is not None
    assert nieuw == origineel
    assert (nieuw.volledig, nieuw.schooljaren, nieuw.laad, nieuw.afronding) == (
        origineel.volledig,
        origineel.schooljaren,
        origineel.laad,
        origineel.afronding,
    )
    # Sentinelmaskering in store.put: -1 is weer leeg, zoals de eerste keer.
    assert store.get(key).isna().sum().sum() == cellen


def test_cbs_afronding_en_laatste_update_komen_mee(client):
    with _bronnen():
        key = _stap({"username": "alice"}, *_ROOTS["cbs"])
        _opslaan("alice", "c1", key)
        _herstart()
        resp = _csv(client, key)

    known = store.meta(key)
    assert known is not None and known.afronding == 10
    assert "afronding: " in resp.text
    assert "CBS-tabel laatst bijgewerkt op 2026-04-14" in resp.headers["X-Data-Herladen"]


# ── Afgeleide keys ──────────────────────────────────────────────────────────


def test_een_selectie_met_query_data_komt_terug_na_haar_bron(client):
    session = {"username": "alice"}
    with _bronnen():
        bron = _stap(session, *_ROOTS["duo"])
        selectie = _stap(session, TOOL_QUERY_DATA, {"data_key": bron, "filters": {"STUDIEJAAR": 2025}})
        _opslaan("alice", "c1", selectie)
        eerst = _csv(client, selectie)
        _herstart()
        daarna = _csv(client, selectie)

    assert selectie != bron
    assert daarna.status_code == 200
    assert _zonder_notitie(daarna.text) == _zonder_notitie(eerst.text)
    assert store.get(bron) is not None, "de bron komt eerst terug"
    assert "X-Data-Herladen" in daarna.headers


def test_elke_selectie_op_een_herladen_bron_draagt_de_melding(client):
    """Twee tabellen op één DUO-load: ook de tweede download zegt dat de bron opnieuw is opgehaald."""
    session = {"username": "alice"}
    with _bronnen():
        bron = _stap(session, *_ROOTS["duo"])
        a = _stap(session, TOOL_QUERY_DATA, {"data_key": bron, "filters": {"STUDIEJAAR": 2025}})
        b = _stap(session, TOOL_QUERY_DATA, {"data_key": bron, "filters": {"STUDIEJAAR": 2024}})
        _opslaan("alice", "c1", a, b)
        _herstart()
        eerst_a, dan_b, nog_eens_a = _csv(client, a), _csv(client, b), _csv(client, a)

    for resp in (eerst_a, dan_b, nog_eens_a):
        assert resp.status_code == 200
        assert "de bron kan intussen zijn gewijzigd" in resp.headers["X-Data-Herladen"]
        assert resp.text.lstrip("\ufeff").startswith(_NOTITIE)


def test_een_selectie_op_een_bron_die_een_ander_live_laadde_draagt_de_melding(client):
    """Na de herstart laadt bob de bron live, zonder markering; alice' selectie wordt erop herbouwd."""
    with _bronnen():
        alice = {"username": "alice"}
        bron = _stap(alice, *_ROOTS["duo"])
        b = _stap(alice, TOOL_QUERY_DATA, {"data_key": bron, "filters": {"STUDIEJAAR": 2024}})
        _opslaan("alice", "c1", b)
        _herstart()
        _stap({"username": "bob"}, *_ROOTS["duo"])
        assert store.get(b) is None and herlaad.notitie("alice", bron) is None and herlaad.notitie("bob", bron) is None
        resp = _csv(client, b)

    assert resp.status_code == 200
    assert "de bron kan intussen zijn gewijzigd" in resp.headers["X-Data-Herladen"]
    assert resp.text.lstrip("\ufeff").startswith(_NOTITIE)


def test_een_tabel_die_een_ander_live_opnieuw_maakte_draagt_de_melding(client):
    """Alice' tabel staat er al, maar bob maakte haar ná de herstart: niet de data van haar antwoord."""
    with _bronnen():
        alice = {"username": "alice"}
        bron = _stap(alice, *_ROOTS["duo"])
        b = _stap(alice, TOOL_QUERY_DATA, {"data_key": bron, "filters": {"STUDIEJAAR": 2024}})
        _opslaan("alice", "c1", b)
        _herstart()
        bob = {"username": "bob"}
        _stap(bob, TOOL_QUERY_DATA, {"data_key": _stap(bob, *_ROOTS["duo"]), "filters": {"STUDIEJAAR": 2024}})
        assert store.get(b) is not None and herlaad.notitie("bob", b) is None
        resp = _csv(client, b)

    assert resp.status_code == 200
    assert "de bron kan intussen zijn gewijzigd" in resp.headers["X-Data-Herladen"]
    assert resp.text.lstrip("\ufeff").startswith(_NOTITIE)


def test_een_live_antwoord_op_herladen_data_draagt_geen_melding(client):
    """Bob vraagt live op een bron die alice' recept net terugzette: zijn antwoord rust op precies die data."""
    with _bronnen():
        alice = {"username": "alice"}
        bron = _stap(alice, *_ROOTS["duo"])
        a = _stap(alice, TOOL_QUERY_DATA, {"data_key": bron, "filters": {"STUDIEJAAR": 2025}})
        _opslaan("alice", "c1", a)
        _herstart()
        assert "X-Data-Herladen" in _csv(client, a).headers
        assert herlaad.notitie("alice", bron) is not None, "de bron is herladen"

        bob = {"username": "bob"}
        assert _stap(bob, *_ROOTS["duo"]) == bron, "uit de cache, zonder nieuwe put"
        c = _stap(bob, TOOL_QUERY_DATA, {"data_key": bron, "filters": {"OPLEIDINGSVORM": "VT"}})
        bob_c, bob_bron = _csv(client, c, "bob"), _csv(client, bron, "bob")
        bob["data_keys"] = [bron, c]
        bob_rapport = herstel_data_keys(bob, "bob")
        alice_a, alice_bron = _csv(client, a), _csv(client, bron)

    for resp in (bob_c, bob_bron):
        assert resp.status_code == 200
        assert "X-Data-Herladen" not in resp.headers and _NOTITIE not in resp.text
    assert bob_rapport.notitie is None
    # Voor alice blijft het herladen data, ook de bron die bob intussen live gebruikte.
    for resp in (alice_a, alice_bron):
        assert "de bron kan intussen zijn gewijzigd" in resp.headers["X-Data-Herladen"]


def test_een_nieuwe_laadstap_haalt_de_markering_weg(client):
    """Laadt een vraag de data daarna zelf opnieuw, dan is het weer data van een antwoord."""
    with _bronnen():
        key = _stap({"username": "alice"}, *_ROOTS["rio"])
        _opslaan("alice", "c1", key)
        _herstart()
        assert "X-Data-Herladen" in _csv(client, key).headers
        store.clear()
        _stap({"username": "alice"}, *_ROOTS["rio"])
        resp = _csv(client, key)

    assert resp.status_code == 200
    assert "X-Data-Herladen" not in resp.headers and _NOTITIE not in resp.text


def test_een_eigen_berekening_noemt_de_stap_en_de_key(client):
    session = {"username": "alice"}
    with _bronnen():
        bron = _stap(session, *_ROOTS["duo"])
        args = {"code": "result = df.head(2).to_dict(orient='records')", "data_key": bron}
        analyse = _stap(session, TOOL_RUN_ANALYSIS, args, _analyse(**args))
        _opslaan("alice", "c1", analyse)
        _herstart()
        resp = _csv(client, analyse)

    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert "eigen berekening (run_analysis)" in detail
    assert analyse in detail
    assert detail != "Deze data is niet meer beschikbaar. Stel de vraag opnieuw om haar op te halen."


def test_een_selectie_op_een_eigen_berekening_noemt_die_berekening(client):
    session = {"username": "alice"}
    with _bronnen():
        bron = _stap(session, *_ROOTS["duo"])
        args = {"code": "result = df.to_dict(orient='records')", "data_key": bron}
        analyse = _stap(session, TOOL_RUN_ANALYSIS, args, _analyse(**args))
        selectie = _stap(session, TOOL_QUERY_DATA, {"data_key": analyse, "filters": {"STUDIEJAAR": 2025}})
        _opslaan("alice", "c1", selectie)
        _herstart()
        resp = _csv(client, selectie)

    assert resp.status_code == 404
    assert "eigen berekening (run_analysis)" in resp.json()["detail"]
    assert analyse in resp.json()["detail"]


def test_er_wordt_geen_script_bewaard(client):
    session = {"username": "alice"}
    with _bronnen():
        bron = _stap(session, *_ROOTS["duo"])
        args = {"code": "result = df.head(1).to_dict(orient='records')  # GEHEIM_SCRIPT", "data_key": bron}
        analyse = _stap(session, TOOL_RUN_ANALYSIS, args, _analyse(**args))
        _opslaan("alice", "c1", analyse)

    conn = sqlite3.connect(os.environ["DATABASE_PATH"])
    rijen = conn.execute("SELECT data_key, recipe FROM data_recipes").fetchall()
    conn.close()
    assert {k for k, _ in rijen} == {bron, analyse}
    for _, recept in rijen:
        assert "GEHEIM_SCRIPT" not in recept
        assert "code" not in json.loads(recept)
    assert json.loads(dict(rijen)[analyse]) == {
        "afgeleid_van": bron,
        "stap": "eigen berekening (run_analysis)",
        "herlaadbaar": False,
    }


# ── Grenzen ─────────────────────────────────────────────────────────────────


def test_niemand_haalt_data_terug_via_het_recept_van_een_ander(client):
    with _bronnen():
        key = _stap({"username": "alice"}, *_ROOTS["rio"])
        _opslaan("alice", "c1", key)
        _herstart()
        bob = _csv(client, key, "bob")
        assert store.get(key) is None, "bob zette niets terug"
        alice = _csv(client, key, "alice")

    assert bob.status_code == 404
    assert bob.json()["detail"] == "Deze data is niet meer beschikbaar. Stel de vraag opnieuw om haar op te halen."
    assert alice.status_code == 200


def test_een_bronfout_bij_herladen_noemt_de_bron_en_is_geen_500(client):
    with _bronnen():
        key = _stap({"username": "alice"}, *_ROOTS["cbs"])
        _opslaan("alice", "c1", key)
        _herstart()
    verzoek = httpx.Request("GET", "https://opendata.cbs.nl")
    fout = httpx.HTTPStatusError("503", request=verzoek, response=httpx.Response(503, request=verzoek))
    with _bronnen(cbs_data=MagicMock(side_effect=fout)):
        resp = _csv(client, key)

    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert "CBS" in detail and key in detail
    assert "HTTP 503" in detail


def test_een_dataset_buiten_de_scope_wordt_niet_herladen(client):
    with _bronnen():
        key = _stap({"username": "alice"}, *_ROOTS["cbs"])
        _opslaan("alice", "c1", key)
        _herstart()
    tellen = MagicMock(return_value=_CBS_ROWS)
    with _bronnen(cbs_data=tellen), patch("tools.cbs.scope_blokkade", return_value="Dataset buiten de scope."):
        resp = _csv(client, key)

    assert resp.status_code == 502
    assert "CBS" in resp.json()["detail"] and "buiten de scope" in resp.json()["detail"]
    tellen.assert_not_called()


def test_een_selectie_die_query_data_niet_meer_aanneemt_is_een_melding_geen_500():
    store.put("rio:t", pd.DataFrame({"a": [1]}), store.KeyMeta(bron="rio", dataset="t"))
    recept = {"afgeleid_van": "rio:t", "tool": TOOL_QUERY_DATA, "args": {"filters": "onzin"}, "stap": "s"}

    uitkomst = herlaad.herlaad("rio:t:zz", recept)

    assert not uitkomst.gelukt
    assert "Stap 's' gaf key rio:t:zz niet opnieuw" in uitkomst.melding


def test_alleen_tools_uit_de_lijst_worden_aangeroepen():
    uitkomst = herlaad.herlaad("x:1", {"laad": ["run_analysis", {"code": "import os"}]})
    assert not uitkomst.gelukt
    assert "geen bekende laadstap" in uitkomst.melding


def test_een_key_die_er_nog_is_wordt_niet_opnieuw_opgehaald():
    store.put("rio:erkenningen", pd.DataFrame({"a": [1]}))
    uitkomst = herlaad.herlaad("rio:erkenningen", {"laad": [TOOL_GET_RIO_DATA, {"resource": "erkenningen"}]})
    assert uitkomst.gelukt and not uitkomst.herladen


def test_tools_die_geen_data_maken_leveren_geen_recept():
    store.put("rio:erkenningen", pd.DataFrame({"a": [1]}), store.KeyMeta(bron="rio", dataset="erkenningen"))
    assert herlaad.recept("rio:erkenningen", {"name": "compute_kpi", "arguments": {}}) is None


# ── Een heropend gesprek ────────────────────────────────────────────────────


def _heropen(username: str, conv_id: str | None) -> tuple[dict, list[dict]]:
    """Wat de frontend doet bij het openen van een opgeslagen gesprek: history met het gesprek-id."""
    session = chat._new_session(username)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    msg = {"action": "history", "messages": [{"role": "user", "content": "Hoeveel?"}], "conv_id": conv_id}

    async def openen():
        await chat.ACTIES["history"](msg, session, emit, None)

    asyncio.run(openen())
    return session, events


def test_tool_end_meldt_de_key_van_een_lader_voor_het_recept(monkeypatch):
    """#551: de frontend bewaart tools[].dataKey; de server zet hem in het tool_end-event."""
    from agent import loop as loop_module

    result = json.dumps({"data_key": "duo:p01hoinges:0", "preview": [{"N": 1}]})
    monkeypatch.setattr(loop_module, "dispatch", lambda name, args: (result, None))
    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    args = {"dataset_id": "p01hoinges", "resource": 0}
    call = loop_module.ToolCall(id="t1", name=TOOL_GET_DUO_DATA, arguments=json.dumps(args), args=args)
    asyncio.run(loop_module._execute_tool(call, emit))

    end = next(e for e in events if e["type"] == "tool_end")
    assert end["data_key"] == "duo:p01hoinges:0" and "export_key" not in end


def test_een_gesprek_zonder_exporteerbare_tabel_kent_bij_heropenen_toch_zijn_data(database):
    """#551 (UX F04): een lader plus een KPI legt geen selectie in de store; het recept van de lader is
    genoeg om het gesprek bij heropenen zijn data terug te geven, zonder eerst een nieuwe vraag."""
    with _bronnen():
        session = {"username": "alice"}
        bron = _stap(session, *_ROOTS["duo"])
        # Wat PUT /api/conversations doet met tools[].dataKey van de lader en een KPI zonder key.
        recepten.bewaar(
            "alice",
            "c1",
            [{"role": "assistant", "tools": [{"name": TOOL_GET_DUO_DATA, "dataKey": bron}, {"name": "compute_kpi"}]}],
        )
        _herstart()

        heropend, events = _heropen("alice", "c1")
        assert heropend["data_keys"] == [bron]
        assert events == [{"type": "history_data", "data_keys": 1}]

        herstel = herstel_data_keys(heropend, "alice")

    assert not herstel.onherstelbaar
    assert store.get(bron) is not None


def test_een_heropend_gesprek_kent_zijn_data_weer_en_herlaadt_haar_voor_een_rapport(database):
    with _bronnen():
        session = {"username": "alice"}
        bron = _stap(session, *_ROOTS["duo"])
        selectie = _stap(session, TOOL_QUERY_DATA, {"data_key": bron, "filters": {"STUDIEJAAR": 2025}})
        _opslaan("alice", "c1", selectie)
        _herstart()

        heropend, events = _heropen("alice", "c1")
        assert heropend["data_keys"] == [bron, selectie], "ouders eerst"
        assert events == [{"type": "history_data", "data_keys": 2}]
        assert store.get(selectie) is None, "lui: nog niets opgehaald"

        herstel = herstel_data_keys(heropend, "alice")

    assert not herstel.onherstelbaar
    assert store.get(selectie) is not None and store.get(bron) is not None
    assert herstel.notitie is not None and "de bron kan intussen zijn gewijzigd" in herstel.notitie


def _rapport(session: dict) -> list[dict]:
    """De stap vóór een rapport (agent.report): de data terug, met de melding als toast."""
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(herstel_data(session, emit))
    return events


@pytest.mark.parametrize("wie_eerst", ["alice", "bob"])
def test_het_rapport_meldt_ook_data_die_een_eerder_verzoek_al_herlaadde(client, wie_eerst):
    """Een download (van alice zelf of van bob) zette de key al terug; alice' rapport zegt het toch."""
    with _bronnen():
        for gebruiker in ("alice", "bob"):
            key = _stap({"username": gebruiker}, *_ROOTS["cbs"])
            _opslaan(gebruiker, "c1", key)
        _herstart()
        assert _csv(client, key, wie_eerst).status_code == 200
        heropend, _ = _heropen("alice", "c1")
        assert heropend["data_keys"] == [key] and store.get(key) is not None

        herstel = herstel_data_keys(heropend, "alice")
        events = _rapport(heropend)

    assert herstel.onherstelbaar == {}
    assert herstel.notitie is not None and "de bron kan intussen zijn gewijzigd" in herstel.notitie
    [toast] = events
    assert toast["type"] == "toast" and toast["message"] == herstel.notitie


def test_het_rapport_meldt_data_die_een_ander_live_laadde(database):
    with _bronnen():
        key = _stap({"username": "alice"}, *_ROOTS["rio"])
        _opslaan("alice", "c1", key)
        _herstart()
        _stap({"username": "bob"}, *_ROOTS["rio"])
        heropend, _ = _heropen("alice", "c1")
        events = _rapport(heropend)

    [toast] = events
    assert "opnieuw opgehaald op" in toast["message"] and "de bron kan intussen zijn gewijzigd" in toast["message"]


def test_het_rapport_van_een_live_gesprek_meldt_niets(database):
    with _bronnen():
        session = {"username": "alice"}
        key = _stap(session, *_ROOTS["rio"])
        _opslaan("alice", "c1", key)
        assert _rapport(session) == []


def test_een_heropend_gesprek_neemt_geen_data_van_een_ander(database):
    with _bronnen():
        key = _stap({"username": "alice"}, *_ROOTS["rio"])
        _opslaan("alice", "c1", key)

    heropend, events = _heropen("bob", "c1")

    assert heropend["data_keys"] == []
    assert events == [{"type": "history_data", "data_keys": 0}]


def test_history_zonder_gesprek_id_blijft_zoals_het_was(database):
    heropend, events = _heropen("alice", None)
    assert heropend["data_keys"] == [] and events == []


def test_een_ouder_die_al_terug_is_als_bron_van_een_selectie_telt_niet_als_weg(database):
    with _bronnen():
        session = {"username": "alice"}
        bron = _stap(session, *_ROOTS["duo"])
        selectie = _stap(session, TOOL_QUERY_DATA, {"data_key": bron, "filters": {"STUDIEJAAR": 2025}})
        _opslaan("alice", "c1", selectie)
        _herstart()
        herstel = herstel_data_keys({"username": "alice", "data_keys": [selectie, bron]}, "alice")

    assert herstel.onherstelbaar == {}
    assert store.get(bron) is not None and store.get(selectie) is not None


# ── De vlag hoort bij de gebruiker, niet bij de gedeelde store (#788) ──


def test_de_vlag_van_de_een_verandert_niets_aan_de_ander(client):
    """Alice' data is herladen, bob vroeg haar live op: in elke volgorde houdt ieder zijn eigen melding."""
    with _bronnen():
        key = _stap({"username": "alice"}, *_ROOTS["rio"])
        _opslaan("alice", "c1", key)
        _herstart()
        assert "X-Data-Herladen" in _csv(client, key).headers
        bob = {"username": "bob", "data_keys": [key]}
        _stap(bob, *_ROOTS["rio"])
        rondes = [(_csv(client, key, "bob"), _csv(client, key, "alice")) for _ in range(2)]
        bob_rapport = herstel_data_keys(bob, "bob")

    for van_bob, van_alice in rondes:
        assert "X-Data-Herladen" not in van_bob.headers and _NOTITIE not in van_bob.text
        assert "de bron kan intussen zijn gewijzigd" in van_alice.headers["X-Data-Herladen"]
    assert bob_rapport.notitie is None


# ── Alleen data van vóór een herstart of uit een recept krijgt de melding (#762) ──


def test_een_ander_gesprek_verwijderen_maakt_live_data_niet_herladen(client):
    with _bronnen():
        session = {"username": "alice"}
        key = _stap(session, *_ROOTS["rio"])
        gesprek = {"title": "t", "timestamp": 1, "messages": [{"role": "assistant", "tools": [{"exportKey": key}]}]}
        for conv_id in ("c1", "c2"):
            assert client.put(f"/api/conversations/{conv_id}", json=gesprek, headers=_als("alice")).status_code == 200
        assert client.delete("/api/conversations/c1", headers=_als("alice")).status_code == 200

        session["data_keys"] = [key]
        herstel = herstel_data_keys(session, "alice")
        resp = _csv(client, key)

    assert herstel.notitie is None
    assert resp.status_code == 200 and "X-Data-Herladen" not in resp.headers


def test_een_live_key_die_uit_de_wachtrij_viel_krijgt_geen_melding(client, monkeypatch):
    monkeypatch.setattr(recepten, "_MAX_WACHTEND", 1)
    with _bronnen():
        session = {"username": "alice"}
        eerste = _stap(session, *_ROOTS["rio"])
        _opslaan("alice", "c1", eerste)
        _stap(session, *_ROOTS["cbs"])  # verdringt het recept van de eerste uit `_wachtend`
        assert ("alice", eerste) not in recepten._wachtend

        session["data_keys"] = [eerste]
        herstel = herstel_data_keys(session, "alice")
        resp = _csv(client, eerste)

    assert herstel.notitie is None
    assert resp.status_code == 200 and "X-Data-Herladen" not in resp.headers


def test_na_een_herstart_komt_de_melding_er_wel(database):
    with _bronnen():
        session = {"username": "alice"}
        key = _stap(session, *_ROOTS["rio"])
        _opslaan("alice", "c1", key)
        _herstart()
        _stap({"username": "bob"}, *_ROOTS["rio"])  # de data is er weer, maar niet van alice' antwoord

        herstel = herstel_data_keys({"username": "alice", "data_keys": [key]}, "alice")

    assert herstel.notitie is not None and "de bron kan intussen zijn gewijzigd" in herstel.notitie


def test_verwijder_al_mijn_gegevens_laat_niets_van_de_gebruiker_in_het_geheugen(database):
    with _bronnen():
        key = _stap({"username": "alice"}, *_ROOTS["rio"])
        _opslaan("alice", "c1", key)
        _herstart()
        herstel_data_keys({"username": "alice", "data_keys": [key]}, "alice")
        _stap({"username": "alice"}, *_ROOTS["cbs"])
        assert herlaad.herladen_op("alice", key) is not None

        recepten.vergeet_gebruiker("alice")

    assert not [s for s in recepten._wachtend if s[0] == "alice"]
    assert not [s for s in recepten._live if s[0] == "alice"]
    assert herlaad.herladen_op("alice", key) is None
