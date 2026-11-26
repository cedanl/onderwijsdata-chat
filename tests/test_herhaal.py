"""Herhaal deze analyse (#1240): de CBS-tabellen achter een eigen antwoord opnieuw, naast de stand van toen.

De bron is nagebootst (zoals in test_herlaad.py): een eerste lading voor het antwoord, daarna een tweede stand van CBS
met hetzelfde of een ander getal en een andere `Modified`. Geen model: litellm mag niet worden aangeroepen.
"""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from agent import beurtbewijs, herhaling, recepten
from agent.session_data import record_data_key
from core import tokenbudget
from core.rate_limit import RateLimiter
from routes import chat
from routes import herhaal as herhaal_route
from tools import brondiff, store
from tools.analysis import run_analysis
from tools.catalog import bron_titel
from tools.cbs import get_cbs_data
from tools.duo import get_duo_data
from tools.query import query_data
from tools.schemas import TOOL_GET_CBS_DATA, TOOL_GET_DUO_DATA, TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS

pytestmark = pytest.mark.usefixtures("zonder_scopegrens")

_CBS_DEFS = {
    "Onderwijssoort": {"type": "Dimension"},
    "Perioden": {"type": "TimeDimension"},
    "Ingeschrevenen_1": {"type": "Topic", "title": "Ingeschrevenen"},
}
_TOEN = [
    {"Onderwijssoort": "A025294", "Perioden": "2024SJ00", "Ingeschrevenen_1": 378490},
    {"Onderwijssoort": "A025294", "Perioden": "2025SJ00", "Ingeschrevenen_1": 367960},
]
_NU = [
    {"Onderwijssoort": "A025294", "Perioden": "2024SJ00", "Ingeschrevenen_1": 378490},
    {"Onderwijssoort": "A025294", "Perioden": "2025SJ00", "Ingeschrevenen_1": 369120},
]
_TOEN_GEWIJZIGD = "2026-04-14T02:00:00"
_NU_GEWIJZIGD = "2026-06-15T02:00:00"
_ARGS = {"dataset_id": "85423NED"}
_TEKST = "Er stonden 367.960 studenten ingeschreven in 2025."


def _cbs_get(modified: str):
    def get(dataset_id, endpoint, **params):
        if endpoint == "TableInfos":
            return [{"Description": "", "Modified": modified}]
        return []

    return get


@contextmanager
def _cbs(rows=None, modified=_TOEN_GEWIJZIGD, data=None):
    with (
        patch("tools.cbs.data", data or MagicMock(return_value=[dict(r) for r in rows or _TOEN])),
        patch("tools.cbs.definitions", return_value=_CBS_DEFS),
        patch("tools.cbs.get", side_effect=_cbs_get(modified)),
    ):
        yield


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    db.init_db()
    return db


@pytest.fixture
def client(database, monkeypatch):
    from core import auth

    monkeypatch.setattr(auth, "AUTH_ENABLED", True)
    # Elke test een eigen, ruime limiet: de berichtlimiet van de chat telt per proces.
    monkeypatch.setattr(chat, "_berichtlimiter", RateLimiter(max_attempts=100, window_seconds=60))
    import server

    return TestClient(server.app)


@pytest.fixture(autouse=True)
def geen_model(monkeypatch):
    """Herhalen roept nooit een model aan (#1240, criterium 4)."""
    import litellm

    aanroepen = MagicMock(side_effect=AssertionError("litellm aangeroepen"))
    monkeypatch.setattr(litellm, "completion", aanroepen)
    monkeypatch.setattr(litellm, "acompletion", aanroepen)
    return aanroepen


def _als(username: str) -> dict:
    from core import auth

    return {"Authorization": f"Bearer {auth.make_token(username)}"}


def _stap(session: dict, name: str, args: dict, result: str | None = None) -> str:
    if result is None:
        result = {TOOL_GET_CBS_DATA: get_cbs_data, TOOL_GET_DUO_DATA: get_duo_data, TOOL_QUERY_DATA: query_data}[name](
            **args
        )
    record_data_key(session, result, {"name": name, "arguments": args})
    return json.loads(result)["data_key"]


def _antwoord(session: dict, tekst: str = _TEKST) -> str:
    """De beurt is af: haar bewijs staat klaar onder de hash van de tekst, zoals na message_end."""
    beurtbewijs.zet_klaar(session, tekst)
    return beurtbewijs.tekst_hash(tekst)


def _herhaal(client, h: str, username: str = "alice", conv_id: str = "c1"):
    return client.post(f"/api/conversations/{conv_id}/antwoorden/{h}/herhaal", headers=_als(username))


def _cbs_antwoord() -> tuple[str, str]:
    session = {"username": "alice"}
    with _cbs():
        key = _stap(session, TOOL_GET_CBS_DATA, _ARGS)
    return key, _antwoord(session)


# ── De vergelijking zelf ─────────────────────────────────────────────────────


def _df(rows):
    import pandas as pd

    return pd.DataFrame(rows)


def test_gelijke_tabel_en_versie_is_ongewijzigd():
    verschil = brondiff.vergelijk(_df(_TOEN), _df(_TOEN), ["Onderwijssoort", "Perioden"])
    stand = brondiff.Stand("2026-04-14", "abc")

    assert verschil == brondiff.Verschil()
    assert brondiff.status(stand, stand, verschil) == brondiff.ONGEWIJZIGD
    assert brondiff.samenvatting(stand, stand, verschil) == (
        "Ongewijzigd: dezelfde cijfers en dezelfde bronversie (bijgewerkt op 14-04-2026)."
    )


def test_een_ander_getal_noemt_de_oude_en_de_nieuwe_waarde_met_rij_en_kolom():
    verschil = brondiff.vergelijk(
        _df(_TOEN), _df(_NU), ["Onderwijssoort", "Perioden"], {"Ingeschrevenen_1": "Ingeschrevenen"}
    )

    assert verschil.cellen == 1
    assert verschil.eerste == brondiff.Celverschil("A025294, 2025SJ00", "Ingeschrevenen", 367960, 369120)
    tekst = brondiff.samenvatting(brondiff.Stand("2026-04-14", "aaa"), brondiff.Stand("2026-06-15", "bbb"), verschil)
    assert tekst.startswith("Bron bijgewerkt op 15-06-2026; cijfer verschilt: 367.960 → 369.120 ")
    assert "versie van 14-04-2026 → 15-06-2026" in tekst


def test_een_nieuwe_versie_met_dezelfde_cijfers_zegt_dat_de_cijfers_gelijk_zijn():
    verschil = brondiff.vergelijk(_df(_TOEN), _df(_TOEN), ["Onderwijssoort", "Perioden"])
    tekst = brondiff.samenvatting(brondiff.Stand("2026-04-14", "aaa"), brondiff.Stand("2026-06-15", "aaa"), verschil)

    assert brondiff.status(brondiff.Stand("2026-04-14", "aaa"), brondiff.Stand("2026-06-15", "aaa"), verschil) == (
        brondiff.BIJGEWERKT
    )
    assert tekst == (
        "Bron bijgewerkt op 15-06-2026; dezelfde cijfers in deze tabel; versie van 14-04-2026 → 15-06-2026."
    )


def test_een_nieuwe_periode_telt_als_rij_erbij():
    erbij = [*_TOEN, {"Onderwijssoort": "A025294", "Perioden": "2026SJ00", "Ingeschrevenen_1": 1}]
    verschil = brondiff.vergelijk(_df(_TOEN), _df(erbij), ["Onderwijssoort", "Perioden"])

    assert (verschil.cellen, verschil.rijen_erbij, verschil.rijen_weg) == (0, 1, 0)


@pytest.mark.parametrize("woord", ["fout", "onjuist", "foutief", "verkeerd", "klopt niet", "incorrect"])
def test_de_teksten_zeggen_nooit_dat_het_eerdere_antwoord_niet_klopte(woord):
    """Criterium 7 en besluit #1236: de bron veranderde, het antwoord rustte op de stand van toen."""
    teksten = [
        waarde
        for module in (brondiff, herhaling, herhaal_route)
        for naam, waarde in vars(module).items()
        if naam.isupper() and isinstance(waarde, str)
    ]
    assert len(teksten) > 10
    assert not [t for t in teksten if woord in t.lower()]


# ── Het eindpunt ─────────────────────────────────────────────────────────────


def test_ongewijzigde_brondata_geeft_ongewijzigd(client):
    key, h = _cbs_antwoord()
    with _cbs():
        resp = _herhaal(client, h)

    assert resp.status_code == 200
    body = resp.json()
    assert body["bron"] == "cbs" and body["overgeslagen"] == []
    [tabel] = body["tabellen"]
    assert tabel["status"] == "ongewijzigd"
    assert tabel["dataset"] == "85423NED" and tabel["titel"] == bron_titel("85423NED")
    assert tabel["toen"] == tabel["nu"]
    assert tabel["nu"]["bijgewerkt_op"] == "2026-04-14" and len(tabel["nu"]["hash"]) == 12
    assert tabel["verschil"] == {"cellen": 0, "eerste": None, "rijen_erbij": 0, "rijen_weg": 0}
    assert tabel["samenvatting"].startswith("Ongewijzigd")
    assert key not in json.dumps(body)  # geen interne key (#1063)


def test_gewijzigde_bron_geeft_oud_en_nieuw_per_tabel_en_laat_de_store_staan(client):
    key, h = _cbs_antwoord()
    toen = store.get(key).copy()
    with _cbs(rows=_NU, modified=_NU_GEWIJZIGD):
        resp = _herhaal(client, h)

    assert resp.status_code == 200
    [tabel] = resp.json()["tabellen"]
    assert tabel["status"] == "bijgewerkt"
    assert tabel["toen"]["bijgewerkt_op"] == "2026-04-14" and tabel["nu"]["bijgewerkt_op"] == "2026-06-15"
    assert tabel["toen"]["hash"] != tabel["nu"]["hash"]
    assert tabel["verschil"]["cellen"] == 1
    assert tabel["verschil"]["eerste"]["toen"] == 367960 and tabel["verschil"]["eerste"]["nu"] == 369120
    assert tabel["samenvatting"].startswith("Bron bijgewerkt op 15-06-2026; cijfer verschilt: 367.960 → 369.120")
    assert "versie van 14-04-2026 → 15-06-2026" in tabel["samenvatting"]
    # Een tak, geen vervanging: het eerdere antwoord en wie op die data rust, houden de stand van toen.
    assert store.get(key).equals(toen)
    meta = store.meta(key)
    assert meta is not None and meta.bijgewerkt_op == "2026-04-14"


def test_een_selectie_herhaalt_de_tabel_waar_ze_op_rust(client):
    session = {"username": "alice"}
    with _cbs():
        bron = _stap(session, TOOL_GET_CBS_DATA, _ARGS)
        _antwoord(session, "eerste antwoord")
        _stap(session, TOOL_QUERY_DATA, {"data_key": bron, "filters": {"Perioden": "2025SJ00"}})
    h = _antwoord(session)
    with _cbs(rows=_NU, modified=_NU_GEWIJZIGD):
        resp = _herhaal(client, h)

    [tabel] = resp.json()["tabellen"]
    assert tabel["status"] == "bijgewerkt" and tabel["dataset"] == "85423NED"


def test_zonder_de_stand_van_toen_alleen_de_stand_van_nu(client):
    _, h = _cbs_antwoord()
    store.clear()  # een herstart: de store is leeg, het recept en het bewijs zijn er nog
    with _cbs(rows=_NU, modified=_NU_GEWIJZIGD):
        resp = _herhaal(client, h)

    [tabel] = resp.json()["tabellen"]
    assert tabel["status"] == "niet_te_vergelijken"
    assert tabel["toen"] is None and tabel["verschil"] is None
    assert tabel["nu"]["bijgewerkt_op"] == "2026-06-15"
    assert "15-06-2026" in tabel["samenvatting"]


def test_data_die_na_het_antwoord_opnieuw_is_opgehaald_is_niet_de_stand_van_toen(client):
    _, h = _cbs_antwoord()
    rij = beurtbewijs._klaar["alice", h]
    rij["created_at"] = "2020-01-01T00:00:00+00:00"  # het antwoord was af lang vóór deze lading
    with _cbs():
        [tabel] = _herhaal(client, h).json()["tabellen"]

    assert tabel["status"] == "niet_te_vergelijken"


def test_een_bewaard_gesprek_geeft_de_rij_uit_de_database(client, database):
    _, h = _cbs_antwoord()
    beurtbewijs.bewaar("alice", "c1", [{"role": "assistant", "content": _TEKST}])
    beurtbewijs.wis()  # alleen de database heeft de rij nog
    with _cbs():
        resp = _herhaal(client, h, conv_id="c1")

    assert resp.json()["tabellen"][0]["status"] == "ongewijzigd"


def test_een_ander_account_krijgt_hetzelfde_404_als_een_onbekend_antwoord(client):
    _, h = _cbs_antwoord()
    with _cbs():
        van_bob = _herhaal(client, h, username="bob")
        onbekend = _herhaal(client, "0" * 64)

    assert van_bob.status_code == onbekend.status_code == 404
    assert van_bob.json() == onbekend.json() == {"detail": herhaal_route.NIET_GEVONDEN}


def test_een_ongeldige_hash_wordt_niet_opgezocht(client):
    assert _herhaal(client, "niet-een-hash").status_code == 422


def test_over_het_budget_de_bestaande_melding(client, monkeypatch):
    _, h = _cbs_antwoord()
    monkeypatch.setattr(tokenbudget, "TOKENBUDGET_DAG", 10)
    monkeypatch.setattr(tokenbudget, "gebruik", lambda gebruiker: (11, 11))
    data = MagicMock(return_value=_TOEN)
    with _cbs(data=data):
        resp = _herhaal(client, h)

    assert resp.status_code == 402
    assert resp.json()["detail"] == tokenbudget.MELDING_DAG == tokenbudget.over_budget("alice")
    data.assert_not_called()  # geen aanroep naar de bron


def test_over_de_berichtlimiet_de_bestaande_melding(client, monkeypatch):
    """Herhalen telt als bericht: dezelfde limiet als de chat."""
    _, h = _cbs_antwoord()
    monkeypatch.setattr(chat, "_berichtlimiter", RateLimiter(max_attempts=1, window_seconds=60))
    with _cbs():
        eerst = _herhaal(client, h)
        daarna = _herhaal(client, h)

    assert eerst.status_code == 200
    assert daarna.status_code == 429
    wacht = int(daarna.headers["Retry-After"])
    assert daarna.json()["detail"] == chat._LIMIET_MELDING.format(wacht=wacht)


def test_er_wordt_geen_model_aangeroepen(client, geen_model):
    _, h = _cbs_antwoord()
    with _cbs(rows=_NU, modified=_NU_GEWIJZIGD):
        assert _herhaal(client, h).status_code == 200

    geen_model.assert_not_called()


def test_een_bronfout_is_een_korte_melding_geen_500(client):
    key, h = _cbs_antwoord()
    verzoek = httpx.Request("GET", "https://opendata.cbs.nl")
    fout = httpx.HTTPStatusError("503", request=verzoek, response=httpx.Response(503, request=verzoek))
    with _cbs(data=MagicMock(side_effect=fout)):
        resp = _herhaal(client, h)

    assert resp.status_code == 200
    [tabel] = resp.json()["tabellen"]
    assert tabel["status"] == "mislukt"
    assert "CBS" in tabel["melding"] and f"'{bron_titel('85423NED')}'" in tabel["melding"]
    assert key not in tabel["melding"]
    assert store.get(key) is not None  # de data van het antwoord blijft


def test_een_scopeweigering_is_de_melding_van_het_herladen(client):
    from tools import catalog

    key = "cbs:99999NED:0"
    recepten.onthoud("alice", key, {"laad": [TOOL_GET_CBS_DATA, {"dataset_id": "99999NED"}]})
    beurtbewijs._klaar["alice", h := beurtbewijs.tekst_hash(_TEKST)] = {
        "lineage": {key: {"name": TOOL_GET_CBS_DATA, "arguments": {"dataset_id": "99999NED"}}},
        "rekenbewijs": [],
        "bronnen": {},
        "figuren": [],
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    with (
        patch.multiple(catalog, _cbs_alles=lambda: [], _cbs=lambda: []),
        patch("tools.cbs.scope_blokkade", side_effect=catalog.scope_blokkade),
    ):
        resp = _herhaal(client, h)

    assert resp.status_code == 200
    [tabel] = resp.json()["tabellen"]
    assert tabel["status"] == "mislukt"
    assert tabel["melding"] == "Deze dataset staat niet meer in de catalogus."


def test_een_antwoord_zonder_cbs_tabel_herhaalt_niets_en_zegt_waarom(client):
    import pandas as pd

    session = {"username": "alice"}
    duo = pd.DataFrame({"STUDIEJAAR": [2024, 2025], "AANTAL": [10, 12]})
    with (
        patch("tools.duo._duo.load", side_effect=lambda *_: duo.copy()),
        patch("tools.duo_meta.teldefinitie", return_value="natuurlijke personen"),
    ):
        _stap(session, TOOL_GET_DUO_DATA, {"dataset_id": "p01hoinges", "resource": 0})
    h = _antwoord(session)
    data = MagicMock(return_value=_TOEN)
    with _cbs(data=data):
        body = _herhaal(client, h).json()

    assert body["tabellen"] == []
    assert body["melding"] == herhaling.GEEN_TABEL
    assert body["overgeslagen"] == [herhaling.ANDERE_BRONNEN]
    data.assert_not_called()


def test_een_eigen_berekening_wordt_niet_herhaald_maar_haar_tabel_wel(client):
    session = {"username": "alice"}
    with _cbs():
        bron = _stap(session, TOOL_GET_CBS_DATA, _ARGS)
        code = f"df = store_get('{bron}')\nresult = df.head(1)"
        uitkomst = run_analysis(code=code, data_key=bron)
        assert isinstance(uitkomst, str)
        record_data_key(session, uitkomst, {"name": TOOL_RUN_ANALYSIS, "arguments": {"code": code, "data_key": bron}})
    h = _antwoord(session)
    with _cbs():
        body = _herhaal(client, h).json()

    assert [t["status"] for t in body["tabellen"]] == ["ongewijzigd"]
    [stap] = body["overgeslagen"]
    assert "wordt niet automatisch opnieuw uitgevoerd" in stap and bron not in stap
