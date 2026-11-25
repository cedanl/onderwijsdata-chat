"""Isolatie tussen accounts (#488, privacy H2; de zes controles van #1235): wat Anna opslaat, ziet, wijzigt of
exporteert Bert niet.

De testomgeving had één gedeeld account, dus dit was nooit getoetst. Hier twee accounts in CHAT_USERS
en elke API die per gebruiker opslaat: gesprekken, werkboeken (met het rapport), rapportfeedback, het Word-document,
de CSV-export en "mijn gegevens". Een vreemde key of een vreemd gesprek krijgt dezelfde 404 als een onbestaand: de API
bevestigt niet dat het bestaat. Zonder, met een ongeldig of met een ingetrokken token: 401 op elk van die eindpunten.
Dezelfde controles tegen een draaiende app: `scripts/isolatietest.py` (docs/test-environment.md).
"""

import base64
import json
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from agent import recepten
from core.rate_limit import RateLimiter
from tests.rapport_docx_hulp import RAPPORT_HTML
from tools import fouten, store
from tools.store import KeyMeta


@pytest.fixture
def client(app_client, monkeypatch):
    c = app_client(users="anna:wachtwoord-a,bert:wachtwoord-b", herlaad=("core.auth",), init_db=False)
    # Verse limieten: hun teller leeft in de module en telt anders over de hele testrun mee.
    from routes import feedback, rapport_docx

    monkeypatch.setattr(rapport_docx, "_limiter", RateLimiter(max_attempts=30, window_seconds=60))
    monkeypatch.setattr(feedback, "_limiter", RateLimiter(max_attempts=3, window_seconds=600))
    # Feedback aan, wat een eerdere test ook achterliet: routes.feedback leest ENABLE_FEEDBACK bij het importeren, en
    # tests/test_feedback.py herlaadt hem met "false" (dan geeft elk /api/feedback-eindpunt 404, ook voor Anna).
    monkeypatch.setattr(feedback, "FEEDBACK_ENABLED", True)
    store.clear()
    yield c
    store.clear()


def _als(client: TestClient, gebruiker: str) -> None:
    """Ingelogd zonder /api/auth/login: de login-limiter telt over de hele testrun mee."""
    from core import auth

    client.headers["Authorization"] = f"Bearer {auth.make_token(gebruiker)}"


_GESPREK = {
    "title": "Studenten HU 2024",
    "timestamp": 1_700_000_000,
    "messages": [
        {"role": "user", "content": "Hoeveel studenten heeft de HU?"},
        {"role": "assistant", "content": "De HU had 36.206 studenten.", "tools": []},
    ],
}
_WERKBOEK = {"title": "Rapport HU", "description": "", "createdAt": "2026-10-14T10:00:00Z"}


def test_gesprekken_zijn_alleen_voor_de_eigenaar(client):
    _als(client, "anna")
    assert client.put("/api/conversations/c1", json=_GESPREK).status_code == 200

    _als(client, "bert")
    assert client.get("/api/conversations").json() == []
    assert client.get("/api/conversations", params={"q": "HU"}).json() == []
    assert client.get("/api/conversations/c1").status_code == 404
    assert client.patch("/api/conversations/c1", json={"title": "van Bert"}).status_code == 404
    assert client.delete("/api/conversations/c1").status_code == 200  # raakt alleen een eigen gesprek

    _als(client, "anna")
    assert [c["id"] for c in client.get("/api/conversations").json()] == ["c1"]
    assert client.get("/api/conversations/c1").json()["title"] == "Studenten HU 2024"


def test_werkboeken_zijn_alleen_voor_de_eigenaar(client):
    _als(client, "anna")
    assert client.put("/api/workbooks/w1", json=_WERKBOEK).status_code == 200

    _als(client, "bert")
    assert client.get("/api/workbooks").json() == []
    assert client.get("/api/workbooks/w1").status_code == 404
    assert client.delete("/api/workbooks/w1").status_code == 200

    _als(client, "anna")
    assert [w["id"] for w in client.get("/api/workbooks").json()] == ["w1"]


def test_rapportfeedback_alleen_op_een_eigen_werkboek(client):
    feedback = {"workbook_id": "w1", "report_type": "report", "report_title": "Rapport HU", "answers": {"nuttig": "4"}}
    _als(client, "anna")
    assert client.put("/api/workbooks/w1", json=_WERKBOEK).status_code == 200

    _als(client, "bert")
    assert client.post("/api/feedback", json=feedback).status_code == 404
    assert client.get("/api/feedback/given").json() == []

    _als(client, "anna")
    assert client.post("/api/feedback", json=feedback).status_code == 200
    assert client.get("/api/feedback/given").json() == ["w1"]

    _als(client, "bert")
    assert client.get("/api/feedback/given").json() == []


def test_csv_export_alleen_met_een_eigen_recept(client):
    key = "duo:p01hoinges:0"
    store.put(
        key,
        pd.DataFrame({"STUDIEJAAR": [2024], "AANTAL": [36206]}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=0),
    )
    recepten.onthoud("anna", key, {"laad": ["get_duo_data", {"dataset_id": "p01hoinges", "resource": 0}]})

    _als(client, "bert")
    assert client.get("/api/data/csv", params={"key": key}).status_code == 404

    _als(client, "anna")
    export = client.get("/api/data/csv", params={"key": key})
    assert export.status_code == 200
    assert "STUDIEJAAR;AANTAL" in export.text


# ── De zes controles van #1235 ───────────────────────────────────────────────
# Elk account laat overal een eigen merkteken achter: in titel, tekst, rapport en feedback. Komt dat van Anna ergens bij
# Bert terug, dan lekt er iets.

_ANNA_MERK = "Anna-geheim-7731"
_BERT_MERK = "Bert-eigen-4419"
_ANNA_KEY = "duo:p01hoinges:2"
_BERT_KEY = "duo:p01hoinges:3"
_BEVESTIGD = {"bevestig": "verwijder"}


def _laad(gebruiker: str, key: str, resource: int) -> None:
    """Data in de gedeelde store met het recept van deze gebruiker, zoals een lader in de chat dat doet."""
    store.put(
        key,
        pd.DataFrame({"STUDIEJAAR": [2024], "AANTAL": [7000 + resource]}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=resource),
    )
    recepten.onthoud(gebruiker, key, {"laad": ["get_duo_data", {"dataset_id": "p01hoinges", "resource": resource}]})


def _gesprek_met_data(merk: str, key: str) -> dict:
    return {
        "title": f"Studenten {merk}",
        "timestamp": 1_700_000_000,
        "messages": [
            {"role": "user", "content": f"Hoeveel studenten? {merk}"},
            {
                "role": "assistant",
                "content": f"Zoveel studenten ({merk}).",
                "tools": [{"name": "get_duo_data", "dataKey": key, "exportKey": key}],
            },
        ],
    }


def _feedback(wb_id: str, merk: str) -> dict:
    return {"workbook_id": wb_id, "report_type": "report", "report_title": merk, "answers": {"nuttig": "4"}}


def _vul(client: TestClient, gebruiker: str, merk: str, key: str, resource: int) -> None:
    """Een gesprek op eigen geladen data, een rapport (werkboek met HTML) en feedback daarop, onder `gebruiker`."""
    _laad(gebruiker, key, resource)
    _als(client, gebruiker)
    assert client.put(f"/api/conversations/{gebruiker}-c1", json=_gesprek_met_data(merk, key)).status_code == 200
    rapport = {
        "title": f"Rapport {merk}",
        "description": merk,
        "htmlContent": RAPPORT_HTML.replace("</body>", f"<p>{merk}</p></body>"),
        "createdAt": "2026-11-25T10:00:00Z",
    }
    assert client.put(f"/api/workbooks/{gebruiker}-w1", json=rapport).status_code == 200
    assert client.post("/api/feedback", json=_feedback(f"{gebruiker}-w1", merk)).status_code == 200


def _vul_anna(client: TestClient) -> None:
    _vul(client, "anna", _ANNA_MERK, _ANNA_KEY, 2)


def _vul_bert(client: TestClient) -> None:
    _vul(client, "bert", _BERT_MERK, _BERT_KEY, 3)


def _export(client: TestClient) -> dict:
    response = client.get("/api/mijn-gegevens/export")
    assert response.status_code == 200
    return json.loads(response.text)


# Controle 1 en 2: een vreemd id is voor Bert een onbekend id, tot op de letter van de 404.
_OP_ID = {
    "gesprek lezen": ("anna-c1", lambda i: ("GET", f"/api/conversations/{i}", None)),
    "gesprek hernoemen": ("anna-c1", lambda i: ("PATCH", f"/api/conversations/{i}", {"title": "van Bert"})),
    "rapport lezen": ("anna-w1", lambda i: ("GET", f"/api/workbooks/{i}", None)),
    "Word-document": ("anna-w1", lambda i: ("POST", f"/api/workbooks/{i}/docx", None)),
    "rapportfeedback": ("anna-w1", lambda i: ("POST", "/api/feedback", _feedback(i, "van Bert"))),
    "CSV-export": (_ANNA_KEY, lambda i: ("GET", f"/api/data/csv?key={i}", None)),
}


@pytest.mark.parametrize("soort", list(_OP_ID))
def test_iets_van_anna_is_voor_bert_niet_te_onderscheiden_van_iets_onbekends(client, soort):
    vreemd_id, verzoek = _OP_ID[soort]
    _vul_anna(client)

    _als(client, "bert")
    methode, pad, body = verzoek(vreemd_id)
    vreemd = client.request(methode, pad, json=body)
    methode, pad, body = verzoek("duo:bestaat-niet:0" if soort == "CSV-export" else "bestaat-niet")
    onbekend = client.request(methode, pad, json=body)
    assert vreemd.status_code == 404  # niet 403: dat zou bevestigen dat het bestaat
    assert vreemd.json() == onbekend.json()
    assert onbekend.status_code == 404

    # Anna zelf komt er wel bij: de 404 komt van het account, niet van een kapot verzoek.
    _als(client, "anna")
    methode, pad, body = verzoek(vreemd_id)
    assert client.request(methode, pad, json=body).status_code == 200


def test_het_rapport_van_anna_lekt_niet_via_het_word_document(client):
    _vul_anna(client)
    _als(client, "anna")
    eigen = client.post("/api/workbooks/anna-w1/docx")
    assert eigen.status_code == 200 and eigen.content.startswith(b"PK")  # een docx is een zip

    _als(client, "bert")
    vreemd = client.post("/api/workbooks/anna-w1/docx")
    assert vreemd.status_code == 404
    assert _ANNA_MERK.encode() not in vreemd.content


# Controle 3: een key van Anna in een eigen gesprek van Bert geeft hem geen toegang tot haar geladen data.
def test_een_key_van_anna_in_een_gesprek_van_bert_geeft_geen_csv(client):
    _vul_anna(client)

    _als(client, "bert")
    assert client.put("/api/conversations/bert-c2", json=_gesprek_met_data(_BERT_MERK, _ANNA_KEY)).status_code == 200
    vreemd = client.get("/api/data/csv", params={"key": _ANNA_KEY})
    onbekend = client.get("/api/data/csv", params={"key": "duo:bestaat-niet:0"})
    assert vreemd.status_code == 404
    assert vreemd.json() == onbekend.json()
    # Het opslaan nam geen recept van Anna over: haar recept is alleen van haar.
    assert recepten.voor("bert", _ANNA_KEY) is None
    assert recepten.keys_van_gesprek("bert", "bert-c2") == []
    assert _export(client)["data_recipes"] == []

    _als(client, "anna")
    assert client.get("/api/data/csv", params={"key": _ANNA_KEY}).status_code == 200


def _wacht_op(ws, soort: str) -> dict:
    """Het eerste event van `soort`; wat ervoor komt (zoals de melding zonder modelsleutel) slaat hij over."""
    for _ in range(10):
        event = json.loads(ws.receive_text())
        if event.get("type") == soort:
            return event
    raise AssertionError(f"geen {soort}-event binnen tien frames")


@pytest.fixture
def chat_met_login(monkeypatch):
    """routes.chat leest AUTH_ENABLED bij het importeren; de herladen core.auth verandert hem niet."""
    import routes.chat

    monkeypatch.setattr(routes.chat, "AUTH_ENABLED", True)


def test_bert_heropent_zijn_gesprek_met_een_key_van_anna_zonder_haar_data(client, chat_met_login):
    """Heropenen in de chat zet de data-keys van de sessie (rapport en tools lezen die): alleen keys met een eigen
    recept, dus geen enkele van Anna."""
    from core import auth

    _vul_anna(client)
    _als(client, "bert")
    gesprek = _gesprek_met_data(_BERT_MERK, _ANNA_KEY)
    assert client.put("/api/conversations/bert-c2", json=gesprek).status_code == 200

    with client.websocket_connect("/api/chat", subprotocols=["bearer", auth.make_token("bert")]) as ws:
        ws.send_text(json.dumps({"action": "history", "conv_id": "bert-c2", "messages": gesprek["messages"]}))
        assert _wacht_op(ws, "history_data") == {"type": "history_data", "data_keys": 0}


def test_een_chattool_in_het_gesprek_van_bert_noemt_de_keys_van_anna_niet(client):
    _vul_anna(client)
    assert store.get(_ANNA_KEY) is not None  # haar data staat in de gedeelde store

    # Het gesprek van Bert, zoals de chatroute het per verbinding zet: zonder eigen data.
    with store.gesprek(lambda: []):
        assert store.eigen_keys() == []
        melding = fouten.onbekende_key("duo:bestaat-niet:0")
    assert _ANNA_KEY not in melding


# Controle 4: wat Bert ziet en exporteert bevat niets van Anna.
def test_lijsten_en_export_van_bert_bevatten_niets_van_anna(client):
    _vul_anna(client)
    _vul_bert(client)

    _als(client, "bert")
    sporen = (_ANNA_MERK, "anna-c1", "anna-w1", _ANNA_KEY, "anna")
    for pad in (
        "/api/conversations",
        f"/api/conversations?q={_ANNA_MERK}",
        "/api/workbooks",
        "/api/feedback/given",
        "/api/mijn-gegevens/export",
    ):
        response = client.get(pad)
        assert response.status_code == 200, pad
        assert [s for s in sporen if s in response.text] == [], pad

    export = _export(client)
    assert export["username"] == "bert"
    assert _BERT_MERK in json.dumps(export)  # de export is niet leeg: Bert's eigen werk staat erin
    assert [c["id"] for c in export["conversations"]] == ["bert-c1"]
    assert client.get("/api/feedback/given").json() == ["bert-w1"]


# Controle 5: "verwijder al mijn gegevens" van Anna laat Bert ongemoeid.
def _momentopname(client: TestClient) -> dict:
    """Alles wat Bert ziet, zonder een werkboek te openen: openen verzet de bewaartermijn (#485)."""
    export = _export(client)
    export.pop("exported_at")
    return {
        "gesprekken": client.get("/api/conversations").json(),
        "gesprek": client.get("/api/conversations/bert-c1").json(),
        "werkboeken": client.get("/api/workbooks").json(),
        "feedback": client.get("/api/feedback/given").json(),
        "export": export,
    }


def test_verwijderen_door_anna_laat_de_gegevens_van_bert_staan(client):
    _vul_anna(client)
    _vul_bert(client)
    _als(client, "bert")
    voor = _momentopname(client)
    assert voor["gesprekken"] and voor["werkboeken"] and voor["feedback"]

    _als(client, "anna")
    verwijderd = client.request("DELETE", "/api/mijn-gegevens", json=_BEVESTIGD)
    assert verwijderd.status_code == 200
    assert verwijderd.json()["verwijderd"]["conversations"] == 1
    assert client.get("/api/conversations").status_code == 401  # haar tokens zijn ingetrokken (#786)

    _als(client, "bert")
    assert _momentopname(client) == voor
    assert client.get("/api/data/csv", params={"key": _BERT_KEY}).status_code == 200


# Controle 6: zonder, met een ongeldig of met een ingetrokken token: 401 op elk eindpunt hierboven.
_EINDPUNTEN = [
    ("GET", "/api/conversations", None),
    ("GET", "/api/conversations/anna-c1", None),
    ("PUT", "/api/conversations/anna-c1", _GESPREK),
    ("PATCH", "/api/conversations/anna-c1", {"title": "overgenomen"}),
    ("DELETE", "/api/conversations/anna-c1", None),
    ("GET", "/api/workbooks", None),
    ("GET", "/api/workbooks/anna-w1", None),
    ("PUT", "/api/workbooks/anna-w1", _WERKBOEK),
    ("DELETE", "/api/workbooks/anna-w1", None),
    ("POST", "/api/workbooks/anna-w1/docx", None),
    ("GET", f"/api/data/csv?key={_ANNA_KEY}", None),
    ("POST", "/api/feedback", _feedback("anna-w1", "overgenomen")),
    ("GET", "/api/feedback/given", None),
    ("GET", "/api/mijn-gegevens/export", None),
    ("DELETE", "/api/mijn-gegevens", _BEVESTIGD),
]


def _vervalst(token: str, gebruiker: str) -> str:
    """Het token met een andere gebruikersnaam in de payload en de oude handtekening."""
    payload, _, handtekening = token.rpartition(".")
    claims = base64.urlsafe_b64decode(payload + "==").decode()
    _, start, exp = claims.split("|")
    nieuw = base64.urlsafe_b64encode(f"{gebruiker}|{start}|{exp}".encode()).decode().rstrip("=")
    return f"{nieuw}.{handtekening}"


def _andere_handtekening(token: str) -> str:
    """Hetzelfde token met één ander teken in de handtekening."""
    return token[:-1] + ("0" if token[-1] != "0" else "1")


def _ingetrokken(client: TestClient) -> str:
    from core import auth

    # Een eigen sessiestart: een token van dezelfde seconde is byte voor byte gelijk aan dat van `_als("anna")` erna.
    token = auth.make_token("anna", start=int(time.time()) - 60)
    assert client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 204
    return token


_TOKENS = {
    "zonder token": lambda client: None,
    "onzin": lambda client: "onzin",
    "vervalste naam": lambda client: _vervalst(_token("bert"), "anna"),
    "vervalste handtekening": lambda client: _andere_handtekening(_token("anna")),
    "ingetrokken": _ingetrokken,
}


def _token(gebruiker: str) -> str:
    from core import auth

    return auth.make_token(gebruiker)


@pytest.mark.parametrize("soort", list(_TOKENS))
def test_elk_eindpunt_weigert_een_verzoek_zonder_geldig_token(client, soort):
    _vul_anna(client)
    client.headers.pop("Authorization", None)
    token = _TOKENS[soort](client)
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    statussen = {f"{m} {p}": client.request(m, p, json=body, headers=headers).status_code for m, p, body in _EINDPUNTEN}
    assert {verzoek: status for verzoek, status in statussen.items() if status != 401} == {}

    # Er is niets gelezen, gewijzigd of verwijderd: Anna's werk staat er nog precies zo.
    _als(client, "anna")
    assert client.get("/api/conversations/anna-c1").json()["title"] == f"Studenten {_ANNA_MERK}"
    assert client.get("/api/workbooks/anna-w1").json()["title"] == f"Rapport {_ANNA_MERK}"
    assert client.get("/api/data/csv", params={"key": _ANNA_KEY}).status_code == 200


@pytest.mark.parametrize("soort", list(_TOKENS))
def test_de_chat_weigert_een_verbinding_zonder_geldig_token(client, chat_met_login, soort):
    token = _TOKENS[soort](client)
    protocollen = ["bearer", token] if token else []
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect("/api/chat", subprotocols=protocollen) as ws,
    ):
        ws.receive_text()
    assert exc.value.code == 4001
