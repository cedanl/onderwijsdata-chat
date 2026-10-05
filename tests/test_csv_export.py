"""CSV van de tabel achter een antwoord, voor Excel (#269).

De export is de tabel die query_data of run_analysis in de store legde, niet de
tabel die het model in zijn antwoord overschreef: in code, met puntkomma en
decimale komma zoals Nederlandse Excel ze verwacht.
"""

import asyncio
import importlib
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from agent import loop as loop_module
from tools import TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS, duo, store
from tools.csv_export import export_key, naar_csv
from tools.query import query_data
from tools.store import KeyMeta

_DF = pd.DataFrame(
    {
        "STUDIEJAAR": [2022, 2023, 2023],
        "INSTELLINGSNAAM": ["HU", "HU", "Avans; Breda"],
        "AANDEEL": [0.125, 0.5, None],
    }
)


@pytest.fixture(autouse=True)
def _clean_store():
    store.clear()
    yield
    store.clear()


def _bron(key="duo:p01hoinges:0", df=_DF, **meta):
    store.put(key, df, KeyMeta(bron="duo", dataset=key.split(":")[1], resource=0, **meta))


def _regels(csv: str | None) -> list[str]:
    assert csv is not None
    return csv.splitlines()


def test_csv_heeft_puntkomma_decimale_komma_en_lege_cellen():
    _bron()
    regels = [r for r in _regels(naar_csv("duo:p01hoinges:0")) if not r.startswith("#")]
    assert regels == [
        "STUDIEJAAR;INSTELLINGSNAAM;AANDEEL",
        "2022;HU;0,125",
        "2023;HU;0,5",
        '2023;"Avans; Breda";',
    ]


def test_csv_begint_met_de_herkomst():
    _bron()
    key = json.loads(query_data("duo:p01hoinges:0", filters={"STUDIEJAAR": 2023}))["data_key"]
    regels = _regels(naar_csv(key))
    assert regels[0] == "# bron: DUO, dataset p01hoinges, resource 0"
    assert regels[1].startswith("# selectie: ")
    assert regels[2] == "STUDIEJAAR;INSTELLINGSNAAM;AANDEEL"


def test_hele_tellingen_zonder_punt_nul():
    """De -1-maskering maakt een telling float; 4147.0 hoort als 4147 in de CSV (#222)."""
    _bron(df=pd.DataFrame({"AANTAL": [4147.0, 12.0]}))
    assert _regels(naar_csv("duo:p01hoinges:0"))[-2:] == ["4147", "12"]


def test_prognose_op_hele_personen_met_noot():
    _bron("duo:studentprognoses-ho:0", pd.DataFrame({"AANTAL": [10.4, 11.6]}))
    regels = _regels(naar_csv("duo:studentprognoses-ho:0"))
    assert regels[-2:] == ["10", "12"]
    assert f"# {duo.PROGNOSE_NOOT}" in regels


def test_afgekapte_data_zegt_dat_erbij():
    _bron(volledig=False)
    assert f"# {store.ONVOLLEDIG}" in _regels(naar_csv("duo:p01hoinges:0"))


def test_onderdrukte_cellen_staan_erbij():
    df = pd.DataFrame({"AANTAL": [-1, 5]})
    _bron(df=df)
    regels = _regels(naar_csv("duo:p01hoinges:0"))
    assert any(r.startswith("# 1 cellen met DUO-sentinel -1 in 'AANTAL'") for r in regels)


def test_onbekende_key_heeft_geen_csv():
    assert naar_csv("duo:bestaat:niet") is None


# ── Welke stap een exporteerbare tabel opleverde ─────────────────────────────


def test_query_data_met_rijen_levert_de_key():
    _bron()
    result = query_data("duo:p01hoinges:0", filters={"STUDIEJAAR": 2023})
    assert export_key(TOOL_QUERY_DATA, result) == json.loads(result)["data_key"]


def test_lege_of_mislukte_stap_levert_niets():
    _bron()
    leeg = query_data("duo:p01hoinges:0", filters={"STUDIEJAAR": 1999})
    assert export_key(TOOL_QUERY_DATA, leeg) is None
    assert export_key(TOOL_QUERY_DATA, "Kolommen niet gevonden: ['X']") is None


def test_run_analysis_zonder_bron_levert_niets():
    """Een uitkomst die geen data las is geen tabel uit de bron (#201)."""
    result = json.dumps({"bron": None, "resultaat": {"data_key": "analyse:1", "rijen": [{"x": 1}]}})
    assert export_key(TOOL_RUN_ANALYSIS, result) is None


def test_andere_tools_leveren_niets():
    assert export_key("get_duo_data", json.dumps({"data_key": "duo:x:0", "rijen": [{"a": 1}]})) is None


def test_tool_end_event_draagt_de_exportkey(monkeypatch):
    result = json.dumps({"data_key": "duo:x:0:ab12", "totaal_rijen": 1, "rijen": [{"N": 1}]})
    monkeypatch.setattr(loop_module, "dispatch", lambda name, args: (result, None))
    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    args = {"data_key": "duo:x:0"}
    call = loop_module.ToolCall(id="t1", name=TOOL_QUERY_DATA, arguments=json.dumps(args), args=args)
    asyncio.run(loop_module._execute_tool(call, emit))

    end = next(e for e in events if e["type"] == "tool_end")
    assert end["export_key"] == "duo:x:0:ab12"


# ── Endpoint ─────────────────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CHAT_USERS", "testuser:testpass")
    monkeypatch.setenv("CHAT_SECRET", "test-secret-for-tests")
    from core import auth

    importlib.reload(auth)
    import server

    importlib.reload(server)
    return TestClient(server.app)


def _login(client):
    token = client.post("/api/auth/login", json={"username": "testuser", "password": "testpass"}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"


def test_endpoint_geeft_de_csv_als_bijlage(client):
    _login(client)
    _bron()
    resp = client.get("/api/data/csv", params={"key": "duo:p01hoinges:0"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="p01hoinges.csv"' in resp.headers["content-disposition"]
    # Met BOM, anders leest Excel é als Ã©.
    assert resp.content.startswith("﻿".encode())
    assert "STUDIEJAAR;INSTELLINGSNAAM;AANDEEL" in resp.text


def test_endpoint_meldt_verdwenen_data(client):
    _login(client)
    resp = client.get("/api/data/csv", params={"key": "duo:weg:0"})
    assert resp.status_code == 404
    assert "niet meer beschikbaar" in resp.json()["detail"]


def test_endpoint_vraagt_inlog(client):
    _bron()
    assert client.get("/api/data/csv", params={"key": "duo:p01hoinges:0"}).status_code == 401
