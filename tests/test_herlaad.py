"""Een data-key overleeft een herstart: zijn recept staat in de database, de data komt terug uit de bron (#472).

De store leeft in het geheugen. store.clear() plus recepten.wis() is hier de herstart: weg
is alles wat het proces wist, over blijft wat de database bewaarde.
"""

import importlib
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
from agent.session_data import record_data_key
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
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CHAT_USERS", "alice:pw,bob:pw")
    monkeypatch.setenv("CHAT_SECRET", "test-secret-for-tests")
    from core import auth

    importlib.reload(auth)
    import server

    importlib.reload(server)
    return TestClient(server.app)


def _als(client, username: str) -> dict:
    from core import auth

    return {"Authorization": f"Bearer {auth.make_token(username)}"}


def _csv(client, key: str, username: str = "alice"):
    return client.get("/api/data/csv", params={"key": key}, headers=_als(client, username))


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
    assert daarna.text == eerst.text
    assert "X-Data-Herladen" not in eerst.headers
    assert "de bron kan intussen zijn gewijzigd" in daarna.headers["X-Data-Herladen"]


@pytest.mark.parametrize("bron", ["cbs", "duo", "rio"])
def test_herladen_meta_is_gelijk_aan_het_origineel(tmp_path, monkeypatch, bron):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    db.init_db()
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
    assert daarna.text == eerst.text
    assert store.get(bron) is not None, "de bron komt eerst terug"
    assert "X-Data-Herladen" in daarna.headers


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
