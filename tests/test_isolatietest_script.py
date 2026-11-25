"""scripts/isolatietest.py (#1235): de isolatietest tegen een draaiende app, hier op de app in dit proces.

Zo toetst pytest het script zelf: alle controles slagen op de echte routes, een lek valt op, en een URL buiten lokaal
en de testomgeving weigert hij vóór het eerste verzoek (het netwerk is in de tests dicht, tests/netwerkblok.py).
"""

import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from agent import recepten
from core.rate_limit import RateLimiter
from scripts import isolatietest
from tools import store
from tools.store import KeyMeta

_KEY = "duo:p01hoinges:2"


@pytest.fixture
def client(app_client, monkeypatch):
    c = app_client(users="anna:wachtwoord-a,bert:wachtwoord-b", herlaad=("core.auth",), init_db=False)
    from routes import feedback, rapport_docx

    monkeypatch.setattr(rapport_docx, "_limiter", RateLimiter(max_attempts=30, window_seconds=60))
    monkeypatch.setattr(feedback, "_limiter", RateLimiter(max_attempts=3, window_seconds=600))
    # Feedback aan, wat een eerdere test ook achterliet (tests/test_feedback.py herlaadt routes.feedback met "false").
    monkeypatch.setattr(feedback, "FEEDBACK_ENABLED", True)
    return c


def _vraag(client: TestClient):
    def vraag(methode: str, pad: str, token: str | None, body: object):
        kop = {"Authorization": f"Bearer {token}"} if token else {}
        return client.request(methode, pad, headers=kop, json=body)

    return vraag


def _token(gebruiker: str, *, eerder: int = 0) -> str:
    from core import auth

    return auth.make_token(gebruiker, start=int(time.time()) - eerder)


def _data_van_anna() -> None:
    store.put(
        _KEY,
        pd.DataFrame({"STUDIEJAAR": [2024], "AANTAL": [7731]}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=2),
    )
    recepten.onthoud("anna", _KEY, {"laad": ["get_duo_data", {"dataset_id": "p01hoinges", "resource": 2}]})


def test_alle_controles_slagen_op_de_app(client):
    _data_van_anna()
    uitslag = isolatietest.voer_uit(
        _vraag(client),
        _token("anna"),
        _token("bert"),
        data_key=_KEY,
        token_a_uit=_token("anna", eerder=60),
        verwijder_a=True,
        run="pytest",
    )

    assert uitslag.fouten == []
    gedaan = {wat.split(" ")[0] for wat in uitslag.geslaagd}
    assert {"1/2", "2", "3", "4", "5", "6"} <= gedaan


def test_het_script_ruimt_zijn_testgegevens_op(client):
    anna, bert = _token("anna"), _token("bert")
    uitslag = isolatietest.voer_uit(_vraag(client), anna, bert, run="opruimen")

    assert uitslag.fouten == []
    for token in (anna, bert):
        kop = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/conversations", headers=kop).json() == []
        assert client.get("/api/workbooks", headers=kop).json() == []


def test_een_lek_valt_op(client, monkeypatch):
    """Geeft de API het gesprek van een ander, dan meldt het script een fout in plaats van 'in orde'."""
    from persistence import db

    echt = db.get_conversation
    monkeypatch.setattr(db, "get_conversation", lambda username, conv_id: echt("anna", conv_id))

    uitslag = isolatietest.voer_uit(_vraag(client), _token("anna"), _token("bert"), run="lek")

    assert any(wat.startswith("1/2 gesprek lezen") for wat in uitslag.fouten)


@pytest.mark.parametrize(
    "url",
    [
        "https://onderwijsdata-chat.sdp.surf.nl",
        "https://onderwijsdata-chat.production.sdp.surf.nl",
        "https://onderwijsdata-chat.playground.sdp.surf.nl",
        "https://onderwijsdata-chat.test.sdp.surf.nl.example.org",
        "http://onderwijsdata-chat.test.sdp.surf.nl",
        "ftp://localhost",
        "",
    ],
)
def test_alleen_lokaal_of_de_testomgeving(url):
    with pytest.raises(isolatietest.Geweigerd):
        isolatietest.controleer_url(url)


@pytest.mark.parametrize(
    ("url", "basis"),
    [
        ("https://onderwijsdata-chat.test.sdp.surf.nl/", "https://onderwijsdata-chat.test.sdp.surf.nl"),
        ("http://localhost:5190", "http://localhost:5190"),
        ("http://127.0.0.1:8000/chat", "http://127.0.0.1:8000"),
    ],
)
def test_lokaal_en_de_testomgeving_mogen(url, basis):
    assert isolatietest.controleer_url(url) == basis


def test_twee_eigen_accounts_en_geen_gedeeld_account():
    assert isolatietest.controleer_tokens(_token("anna"), _token("bert")) == ("anna", "bert")
    for a, b in (("anna", "anna"), ("demo", "bert"), ("anna", "gast")):
        with pytest.raises(isolatietest.Geweigerd):
            isolatietest.controleer_tokens(_token(a), _token(b))
    with pytest.raises(isolatietest.Geweigerd):
        isolatietest.controleer_tokens("onzin", _token("bert"))


def test_main_weigert_productie_zonder_een_verzoek(monkeypatch, capsys):
    monkeypatch.setenv("ISOLATIE_URL", "https://onderwijsdata-chat.sdp.surf.nl")
    monkeypatch.setenv("ISOLATIE_TOKEN_A", _token("anna"))
    monkeypatch.setenv("ISOLATIE_TOKEN_B", _token("bert"))

    assert isolatietest.main([]) == 2
    assert "nooit op productie" in capsys.readouterr().err
