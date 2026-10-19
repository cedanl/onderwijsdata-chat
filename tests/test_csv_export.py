"""CSV van de tabel achter een antwoord, voor Excel (#269).

De export is de tabel die query_data of run_analysis in de store legde, niet de
tabel die het model in zijn antwoord overschreef: in code, met puntkomma en
decimale komma zoals Nederlandse Excel ze verwacht.
"""

import asyncio
import csv
import importlib
import io
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from agent import loop as loop_module
from agent import recepten
from tools import (
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_MAAT,
    TOOL_GET_RIO_DATA,
    TOOL_QUERY_DATA,
    TOOL_RUN_ANALYSIS,
    csv_export,
    duo,
    store,
)
from tools.csv_export import bestandsnaam, export_key, geen_export_reden, naar_csv
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


def test_afgekapte_data_zegt_in_gebruikerstaal_dat_het_bestand_onvolledig_is():
    """De export zegt wat er afgekapt is en wat dat betekent, zonder de aanwijzing voor de tool (BEV-08)."""
    _bron(volledig=False)
    regels = _regels(naar_csv("duo:p01hoinges:0"))
    assert f"# {csv_export.ONVOLLEDIG_EXPORT}" in regels
    assert not any(store.ONVOLLEDIG in r for r in regels)
    kop = "\n".join(r for r in regels if r.startswith("#")).lower()
    assert "onvolledig" in kop and "eerste deel" in kop and "totalen" in kop
    for intern in ("serverfilter", "bij het laden", "pagina", "query_data", "get_cbs_data", "get_duo_data", "tool"):
        assert intern not in kop


def test_complete_data_heeft_geen_onvolledig_regel():
    _bron()
    assert not any(csv_export.ONVOLLEDIG_EXPORT in r for r in _regels(naar_csv("duo:p01hoinges:0")))


def test_onderdrukte_cellen_staan_erbij():
    df = pd.DataFrame({"AANTAL": [-1, 5]})
    _bron(df=df)
    regels = _regels(naar_csv("duo:p01hoinges:0"))
    assert any(r.startswith("# 1 cellen met DUO-sentinel -1 in 'AANTAL'") for r in regels)


_FORMULES = ["=SUM(A1)", "+1+2", "-cmd", "@SUM(A1)"]


@pytest.mark.parametrize("tekst", _FORMULES)
def test_formule_in_cel_en_kolomnaam_krijgt_een_apostrof(tekst):
    """Excel voert tekst die met = + - of @ begint uit als formule (#483)."""
    _bron(df=pd.DataFrame({tekst: [tekst]}))
    assert _regels(naar_csv("duo:p01hoinges:0"))[-2:] == [f"'{tekst}", f"'{tekst}"]


def _rijen(uit: str | None) -> list[list[str]]:
    """De rijen zoals een CSV-lezer ze ziet, zonder de '#'-regels: een CR buiten quotes eindigt een rij."""
    assert uit is not None
    rijen = csv.reader(io.StringIO(uit, newline=""), delimiter=";")
    return [rij for rij in rijen if not (rij and rij[0].startswith("#"))]


@pytest.mark.parametrize("tekst", ["\tcmd", "\r=1+1"])
def test_tab_of_cr_vooraan_in_cel_en_kolomnaam_krijgt_een_apostrof(tekst):
    """OWASP noemt ook een tab en een CR vooraan in een cel (#607)."""
    _bron(df=pd.DataFrame({tekst: [tekst]}))
    assert _rijen(naar_csv("duo:p01hoinges:0")) == [[f"'{tekst}"], [f"'{tekst}"]]


def test_cr_vooraan_splitst_geen_rij():
    _bron(df=pd.DataFrame({"A": ["\r=1+1", "x"], "B": ["y", "\rcmd"]}))
    assert _rijen(naar_csv("duo:p01hoinges:0")) == [["A", "B"], ["'\r=1+1", "y"], ["x", "'\rcmd"]]


def test_getallen_en_getaltekst_blijven_zoals_ze_zijn():
    # Een CBS-key: onder een DUO-key maskeert store.put de int -1 al als sentinel.
    df = pd.DataFrame({"A": [-1], "B": [-0.5], "C": [1234.5], "D": ["-1"], "E": ["-0,5"], "F": ["1.234"]})
    store.put("cbs:85525NED:0", df, KeyMeta(bron="cbs", dataset="85525NED"))
    assert _regels(naar_csv("cbs:85525NED:0"))[-1] == "-1;-0,5;1234,5;-1;-0,5;1.234"


def test_formule_met_puntkomma_krijgt_eerst_de_apostrof_dan_quotes():
    _bron(df=pd.DataFrame({"A": ["=a;b"], "B": ['=a"b'], "C": [None]}))
    assert _regels(naar_csv("duo:p01hoinges:0"))[-1] == '"\'=a;b";"\'=a""b";'


def test_onbekende_key_heeft_geen_csv():
    assert naar_csv("duo:bestaat:niet") is None


# ── Bestandsnaam: <titel>_<dataset-id>.csv, als de grafiek-CSV (#533) ─────────


def test_bestandsnaam_is_catalogustitel_plus_dataset_id():
    _bron()
    assert bestandsnaam("duo:p01hoinges:0") == (
        "Ingeschrevenen_hoger_onderwijs_in_het_domein_hoger_onderwijs_p01hoinges.csv"
    )


def test_bestandsnaam_zonder_catalogustitel_is_alleen_het_id():
    _bron("duo:eigen-set:0")
    assert bestandsnaam("duo:eigen-set:0") == "eigen_set.csv"


def test_bestandsnaam_zonder_meta_valt_terug_op_data():
    store.put("los", _DF)
    assert bestandsnaam("los") == "data.csv"


def test_bestandsnaam_maakt_titel_veilig_zoals_figure_csv_filename(monkeypatch):
    """Accenten weg, de rest een underscore, titel hoogstens 80 tekens: geen quotes of CR/LF in de header."""
    monkeypatch.setattr(csv_export.catalog, "bron_titel", lambda _id: 'Één "café";\r\nX-Kop: ja, 2024/25 ')
    _bron()
    assert bestandsnaam("duo:p01hoinges:0") == "Een_cafe_X_Kop_ja_2024_25_p01hoinges.csv"

    monkeypatch.setattr(csv_export.catalog, "bron_titel", lambda _id: "a " * 100)
    naam = bestandsnaam("duo:p01hoinges:0")
    assert naam.endswith("a_p01hoinges.csv")
    assert len(naam.removesuffix("_p01hoinges.csv")) <= 80


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


def test_get_maat_met_rijen_levert_de_key():
    """Een telvraag loopt sinds #188 via get_maat; zonder key geen CSV-knop (#538)."""
    result = json.dumps({"data_key": "duo:p01hoinges:3:ab:cd", "rijen": [{"STUDIEJAAR": 2022, "AANTAL": 1}]})
    assert export_key(TOOL_GET_MAAT, result) == "duo:p01hoinges:3:ab:cd"
    assert export_key(TOOL_GET_MAAT, "Onbekende instelling: Hogeschool Nergens.") is None


def test_andere_tools_leveren_niets():
    assert export_key("compute_kpi", json.dumps({"data_key": "duo:x:0", "rijen": [{"a": 1}]})) is None


# ── Een lader waarvan het resultaat alle rijen toonde (#605) ─────────────────

_TWEE_SCHOOLJAREN = [
    {"Perioden": "2021SJ00", "MboStudenten_1": 248930},
    {"Perioden": "2024SJ00", "MboStudenten_1": 230450},
]


def test_lader_die_alle_rijen_toonde_levert_de_key():
    """ "Hoeveel vrouwelijke mbo-studenten in 2021/22 en 2024/25?" liep via get_cbs_data met een filter op twee
    schooljaren en verder niets: die selectie van twee rijen is de tabel achter het antwoord (#605)."""
    result = json.dumps(
        {"data_key": "cbs:85354NED:c7a8bce6", "totaal_rijen": 2, "preview": _TWEE_SCHOOLJAREN, "kolommen": []}
    )
    assert export_key(TOOL_GET_CBS_DATA, result) == "cbs:85354NED:c7a8bce6"
    rio = json.dumps(
        {"data_key": "rio:erk:0", "opgehaalde_rijen": 2, "meer_beschikbaar": False, "preview": _TWEE_SCHOOLJAREN}
    )
    assert export_key(TOOL_GET_RIO_DATA, rio) == "rio:erk:0"


@pytest.mark.parametrize(
    "result",
    [
        pytest.param({"totaal_rijen": 1200, "preview": _TWEE_SCHOOLJAREN}, id="meer rijen dan getoond"),
        pytest.param({"opgehaalde_rijen": 2, "volledig": False, "preview": _TWEE_SCHOOLJAREN}, id="afgekapt"),
        pytest.param(
            {"opgehaalde_rijen": 2, "meer_beschikbaar": True, "preview": _TWEE_SCHOOLJAREN}, id="rio: nog een pagina"
        ),
        pytest.param({"totaal_rijen": 0, "preview": []}, id="leeg"),
        pytest.param({"totaal_rijen": 2}, id="zonder preview"),
    ],
)
def test_lader_die_niet_alle_rijen_toonde_levert_niets(result):
    """Het hele bronbestand is niet de tabel in het antwoord: dan zijn de citaties de export (#544)."""
    assert export_key(TOOL_GET_DUO_DATA, json.dumps({"data_key": "duo:p:0", **result})) is None


def test_reden_zonder_tabel_key_is_een_keuze_van_de_code():
    groot = json.dumps({"data_key": "duo:p:0", "totaal_rijen": 1200, "preview": _TWEE_SCHOOLJAREN})
    assert (
        geen_export_reden([(TOOL_GET_DUO_DATA, groot), ("compute_kpi", "{}")]) == csv_export.BRON_GROTER_DAN_RESULTAAT
    )
    assert geen_export_reden([("search_catalog", "[]"), ("compute_kpi", "{}")]) == csv_export.GEEN_DATASTAP
    assert geen_export_reden([(TOOL_GET_DUO_DATA, "Bestand niet gevonden.")]) == csv_export.GEEN_DATASTAP


# Per tool die een tabel of getal oplevert: een tabel-key, of bewust niet en waarom (#544). De tools zonder
# key hebben geen tabel in de store die "de tabel achter het antwoord" is; hun getallen krijgen hun CSV via de
# citaties (frontend/src/citatieCsv.js), zodat de knop niet afhangt van welke tool het model koos.
_RIJEN = [{"STUDIEJAAR": 2023, "AANTAL": 36206}]
_PER_TOOL = [
    pytest.param(
        TOOL_QUERY_DATA, {"data_key": "duo:p:0:ab", "rijen": _RIJEN}, True, id="query_data: selectie in de store"
    ),
    pytest.param(TOOL_GET_MAAT, {"data_key": "duo:p:0:ab", "rijen": _RIJEN}, True, id="get_maat: selectie in de store"),
    pytest.param(
        TOOL_RUN_ANALYSIS, {"data_key": "analyse:1", "rijen": _RIJEN}, True, id="run_analysis: tabel uit de bron"
    ),
    pytest.param(
        TOOL_RUN_ANALYSIS, {"gelezen": ["duo:p:0"], "resultaat": 36206}, False, id="run_analysis: één getal, geen tabel"
    ),
    pytest.param(
        "get_duo_data",
        {"data_key": "duo:p:0", "totaal_rijen": 4200, "preview": _RIJEN},
        False,
        id="get_duo_data: het hele bronbestand",
    ),
    pytest.param(
        "get_cbs_data",
        {"data_key": "cbs:85423NED:x", "totaal_rijen": 160, "preview": _RIJEN},
        False,
        id="get_cbs_data: een selectie groter dan het resultaat",
    ),
    pytest.param(
        "get_cbs_data",
        {"data_key": "cbs:85423NED:x", "totaal_rijen": 1, "preview": _RIJEN},
        True,
        id="get_cbs_data: de hele selectie in het resultaat (#605)",
    ),
    pytest.param(
        "get_rio_data",
        {"data_key": "rio:erk:0", "opgehaalde_rijen": 500, "meer_beschikbaar": True, "preview": _RIJEN},
        False,
        id="get_rio_data: een afgekapte pagina",
    ),
    pytest.param(
        "compute_kpi",
        {"label": "Studenten 2023/24", "value": "36.206", "raw": 36206, "bron": {"data_key": "duo:p:0"}},
        False,
        id="compute_kpi: één getal over het bronbestand",
    ),
    pytest.param(
        "relatie", {"data_key": "duo:p:0", "sleutelkolommen": ["INSTELLINGSCODE"]}, False, id="relatie: geen tabel"
    ),
    pytest.param("dataset_profiel", {"data_key": "duo:p:0", "kolommen": []}, False, id="dataset_profiel: geen tabel"),
    pytest.param(
        "get_uwv_vacatures", {"regio": "Utrecht", "vacatures": 1200}, False, id="get_uwv_vacatures: niet in de store"
    ),
]


@pytest.mark.parametrize(("tool", "result", "key"), _PER_TOOL)
def test_per_tool_een_tabel_key_of_bewust_niet(tool, result, key):
    assert (export_key(tool, json.dumps(result)) is not None) is key


# ── Meting per antwoord (#544) ───────────────────────────────────────────────


def test_elk_antwoord_logt_of_het_een_tabel_heeft_en_welke_stap_een_tabel_leverde(caplog):
    """Van buiten was niet te zien of de app de knop wegliet of de beurt geen tabel opleverde; het log zegt het nu."""
    import logging
    from unittest.mock import patch

    run_module = importlib.import_module("agent.run")
    kpi = json.dumps({"label": "2023/24", "value": "36.206", "raw": 36206, "bron": {"data_key": "duo:p:0"}})
    tabel = json.dumps({"data_key": "duo:p:0:ab", "rijen": [{"STUDIEJAAR": 2023, "AANTAL": 36206}]})
    antwoord = "| Jaar | Aantal |\n|---|---|\n| 2023/24 | 36.206 |"

    async def emit(_event):
        pass

    # Met toolaanroepen: zonder tools wordt een antwoord met een getal de vaste weigering, zonder tabel.
    def uitkomst(stappen):
        return loop_module.LoopResult(
            text=antwoord, steps=stappen, tool_calls=[{"name": t, "arguments": "{}"} for t, _ in stappen]
        )

    async def nep_loop(history, **kwargs):
        return uitkomst([("get_duo_data", "{}"), ("compute_kpi", kpi)])

    vraag = [{"role": "user", "content": "Hoeveel studenten per jaar?"}]
    with caplog.at_level(logging.INFO, logger="agent.run"), patch.object(run_module, "tool_loop", nep_loop):
        asyncio.run(run_module.run(vraag, session={}, emit=emit))
    assert (
        "EXPORT  tabel_in_antwoord=True  tabellen=0  tabelstap=-  tools=get_duo_data,compute_kpi  reden=geen_datastap"
        in caplog.text
    )

    groot = json.dumps({"data_key": "duo:p:0", "totaal_rijen": 4200, "preview": [{"STUDIEJAAR": 2023, "AANTAL": 1}]})

    async def nep_loop_grote_bron(history, **kwargs):
        return uitkomst([("get_duo_data", groot), ("compute_kpi", kpi)])

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="agent.run"), patch.object(run_module, "tool_loop", nep_loop_grote_bron):
        asyncio.run(run_module.run(vraag, session={}, emit=emit))
    assert "tabellen=0  tabelstap=-  tools=get_duo_data,compute_kpi  reden=bron_groter_dan_toolresultaat" in caplog.text

    async def nep_loop_met_tabel(history, **kwargs):
        return uitkomst([("get_duo_data", "{}"), (TOOL_QUERY_DATA, tabel)])

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="agent.run"), patch.object(run_module, "tool_loop", nep_loop_met_tabel):
        asyncio.run(run_module.run(vraag, session={}, emit=emit))
    assert (
        "EXPORT  tabel_in_antwoord=True  tabellen=1  tabelstap=query_data  tools=get_duo_data,query_data  reden=-"
        in caplog.text
    )


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


def _met_token(client):
    """Ingelogd zonder /api/auth/login: de login-limiter telt over de hele testrun mee."""
    from core import auth

    client.headers["Authorization"] = f"Bearer {auth.make_token('testuser')}"


def _eigen(key="duo:p01hoinges:0", username="testuser"):
    """De tabel in de store én het recept dat zegt dat een gesprek van deze gebruiker haar maakte (#13)."""
    _bron(key)
    recepten.onthoud(username, key, {"laad": ["get_duo_data", {"dataset_id": "p01hoinges", "resource": 0}]})


def test_endpoint_geeft_de_csv_als_bijlage(client):
    _login(client)
    _eigen()
    resp = client.get("/api/data/csv", params={"key": "duo:p01hoinges:0"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert (
        'filename="Ingeschrevenen_hoger_onderwijs_in_het_domein_hoger_onderwijs_p01hoinges.csv"'
        in resp.headers["content-disposition"]
    )
    # Met BOM, anders leest Excel é als Ã©.
    assert resp.content.startswith("﻿".encode())
    assert "STUDIEJAAR;INSTELLINGSNAAM;AANDEEL" in resp.text


def test_endpoint_noemt_een_onbekende_dataset_naar_het_id(client):
    _met_token(client)
    _eigen("duo:eigen-set:0")
    resp = client.get("/api/data/csv", params={"key": "duo:eigen-set:0"})
    assert resp.status_code == 200
    assert resp.headers["content-disposition"] == 'attachment; filename="eigen_set.csv"'


def test_endpoint_maakt_een_titel_met_accenten_en_tekens_veilig(client, monkeypatch):
    _met_token(client)
    monkeypatch.setattr(csv_export.catalog, "bron_titel", lambda _id: 'Mbo; "studenten" é\r\nX: y')
    _eigen()
    resp = client.get("/api/data/csv", params={"key": "duo:p01hoinges:0"})
    assert resp.headers["content-disposition"] == 'attachment; filename="Mbo_studenten_e_X_y_p01hoinges.csv"'


def test_endpoint_exporteert_een_tabel_van_get_maat(client):
    """De key van get_maat is een selectie met een eigen recept (herlaad.recept kent de tool), dus de route
    kent haar net als een query_data-key (#538)."""
    _met_token(client)
    key = "duo:p01hoinges:3:ab12:cd34"
    _bron(key)
    recepten.onthoud(
        "testuser",
        key,
        {
            "afgeleid_van": "duo:p01hoinges:3",
            "tool": "get_maat",
            "args": {"maat": "ingeschreven_personen_ho", "instelling": "HU"},
            "stap": "selectie",
        },
    )
    resp = client.get("/api/data/csv", params={"key": key})
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].endswith('_p01hoinges.csv"')
    assert "STUDIEJAAR;INSTELLINGSNAAM;AANDEEL" in resp.text


def test_endpoint_meldt_verdwenen_data(client):
    _login(client)
    resp = client.get("/api/data/csv", params={"key": "duo:weg:0"})
    assert resp.status_code == 404
    assert "niet meer beschikbaar" in resp.json()["detail"]


def test_endpoint_vraagt_inlog(client):
    _eigen()
    assert client.get("/api/data/csv", params={"key": "duo:p01hoinges:0"}).status_code == 401


def test_endpoint_zonder_recept_houdt_de_melding_van_voor_de_recepten(client):
    """Een key zonder bewaard recept komt na een herstart niet terug, met dezelfde melding als vóór #472."""
    from core import auth

    client.headers["Authorization"] = f"Bearer {auth.make_token('testuser')}"
    _eigen()
    assert client.get("/api/data/csv", params={"key": "duo:p01hoinges:0"}).status_code == 200
    store.clear()
    recepten.wis()  # het recept stond alleen in het geheugen: na de herstart is er geen

    resp = client.get("/api/data/csv", params={"key": "duo:p01hoinges:0"})

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Deze data is niet meer beschikbaar. Stel de vraag opnieuw om haar op te halen."
    assert "X-Data-Herladen" not in resp.headers


def test_endpoint_geeft_geen_tabel_van_een_ander(client):
    """De store is gedeeld; de export niet: alleen een key uit een eigen gesprek (#13, audit 14 §5)."""
    _met_token(client)
    _eigen(username="iemand-anders")

    resp = client.get("/api/data/csv", params={"key": "duo:p01hoinges:0"})

    # Niet te onderscheiden van een key die er niet (meer) is: de melding bevestigt geen vreemde key.
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Deze data is niet meer beschikbaar. Stel de vraag opnieuw om haar op te halen."
