"""Exporteer al mijn gegevens (#645, deel 1 van #485): alles onder het eigen account, niets van een ander.

Twee accounts in CHAT_USERS, elk met gesprekken, werkboeken, feedback van alle soorten, datarecepten, tokengebruik en
een bewaard SRAM-profiel (#1209).
De export van Anna bevat precies haar rijen; geen tekst die alleen van Bert is, staat erin. Tokens worden
direct gemaakt, niet via de login: de login-limiter telt over de hele testrun mee. Zonder login (iedereen is `gast`)
is er geen eigen account en geen export (#1118).
"""

import json
import logging
import re
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from core.pseudoniem import pseudoniem
from core.tokenbudget import _sleutel
from persistence import db, export

_SOORTEN = [
    "conversations",
    "workbooks",
    "feedback",
    "algemene_feedback",
    "data_recipes",
    "beurtbewijs",
    "tokengebruik",
    "oidc_gebruiker",
]
_EXPORT = "/api/mijn-gegevens/export"


@pytest.fixture
def client(app_client):
    return app_client(users="anna:wachtwoord-a,bert:wachtwoord-b,leeg:wachtwoord-c", herlaad=("core.auth",))


def _als(client: TestClient, gebruiker: str) -> TestClient:
    from core import auth

    client.headers["Authorization"] = f"Bearer {auth.make_token(gebruiker)}"
    return client


def _gesprek(tekst: str) -> list[dict]:
    return [
        {"role": "user", "content": f"Vraag {tekst}"},
        {"role": "assistant", "content": f"Antwoord {tekst}", "tools": []},
    ]


def _vul(gebruiker: str, uniek: str) -> None:
    """Twee gesprekken, twee werkboeken (een rapport met HTML) en van elke andere soort een rij."""
    db.upsert_conversation(gebruiker, f"{gebruiker}-c1", f"Gesprek {uniek}", 1_700_000_000, _gesprek(uniek))
    db.upsert_conversation(gebruiker, f"{gebruiker}-c2", "Tweede", 1_700_000_100, _gesprek(f"{uniek}-2"))
    db.upsert_workbook(
        gebruiker,
        f"{gebruiker}-w1",
        f"Rapport {uniek}",
        "",
        messages=_gesprek(uniek),
        figures=[{"data": [], "layout": {"title": uniek}}],
        html_content=f"<html><body>{uniek}-html</body></html>",
        created_at="2026-10-14T10:00:00Z",
    )
    db.upsert_workbook(
        gebruiker,
        f"{gebruiker}-w2",
        "Dashboard",
        "",
        dashboard_spec={"titel": f"spec-{uniek}"},
        created_at="2026-10-15T10:00:00Z",
    )
    db.add_feedback(
        gebruiker, f"{gebruiker}-w1", "report", f"Rapport {uniek}", {"nuttig": f"4-{uniek}"}, f"Instelling {uniek}"
    )
    db.add_algemene_feedback(gebruiker, "idee", f"algemeen-{uniek}", "/chat")
    db.save_recipes(gebruiker, f"{gebruiker}-c1", {f"key-{uniek}": {"laad": ["query_data", {"id": uniek}]}})
    db.save_beurtbewijs(
        gebruiker,
        f"{gebruiker}-c1",
        {
            f"hash-{uniek}": {
                "lineage": {f"key-{uniek}": {"name": "query_data", "arguments": {"id": uniek}}},
                "rekenbewijs": [{"tool": "compute_kpi", "argumenten": {"id": uniek}, "resultaat": f"res-{uniek}"}],
                "bronnen": {f"key-{uniek}": [{"bron": "duo", "dataset": "p01hoinges", "regel": f"DUO · {uniek}"}]},
                "figuren": [
                    {
                        "id": f"fig-{uniek}",
                        "tool": "create_plot",
                        "arguments": {"data_key": f"key-{uniek}", "title": f"Titel {uniek}"},
                        "titel": f"Titel {uniek}",
                        "keys": [f"key-{uniek}"],
                    }
                ],
                "created_at": "2026-11-03T10:00:00+00:00",
            }
        },
    )
    # Het verbruik van het model staat onder een pseudoniem, niet onder de naam (#1112); de export en het verwijderen
    # vinden het via dezelfde sleutel (#1074).
    db.tokengebruik_boek(_sleutel(gebruiker), "2026-11-02", 1234)
    # Het SRAM-profiel staat onder een pseudoniem van de naam (#984); de export en het verwijderen vinden het (#1209).
    _bewaar_profiel(gebruiker, _profiel(gebruiker, uniek))


def _profiel(gebruiker: str, uniek: str) -> dict:
    return {"name": f"Naam {uniek}", "email": f"{gebruiker}@example.org", "org": f"Org {uniek}", "institution": uniek}


def _bewaar_profiel(gebruiker: str, profiel: dict) -> None:
    """Zoals de login het bewaart (routes/auth.py), zonder de route zelf."""
    import routes.auth

    routes.auth._store_oidc_user(gebruiker, profiel)


def _oidc_sleutel(gebruiker: str) -> str:
    """De sleutel van de rij, onafhankelijk van de code onder test afgeleid: domein `oidc_gebruiker` (#984)."""
    return pseudoniem("oidc_gebruiker", gebruiker)


def _export(client: TestClient, gebruiker: str) -> tuple[dict, str]:
    response = _als(client, gebruiker).get(_EXPORT)
    assert response.status_code == 200
    return json.loads(response.text), response.text


# ── Toegang en vorm ──────────────────────────────────────────────────────────


def test_zonder_sessie_401(client):
    assert client.get(_EXPORT).status_code == 401
    client.headers["Authorization"] = "Bearer ongeldig"
    assert client.get(_EXPORT).status_code == 401


def test_de_export_is_geldige_json_met_alle_soorten(client):
    _vul("anna", "ANNA-UNIEK")
    data, _ = _export(client, "anna")
    assert list(data) == ["schema_version", "exported_at", "username", *_SOORTEN]
    assert data["schema_version"] == 1
    assert data["username"] == "anna"
    assert datetime.fromisoformat(data["exported_at"]).utcoffset() == timedelta(0)
    assert all(isinstance(data[soort], list) for soort in _SOORTEN)


def test_bijlage_met_datum_json_en_nooit_in_een_cache(client):
    response = _als(client, "leeg").get(_EXPORT)
    vandaag = datetime.now(UTC).strftime("%Y-%m-%d")
    assert response.headers["content-disposition"] == f'attachment; filename="openedudata-mijn-gegevens-{vandaag}.json"'
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store"
    assert json.loads(response.text)["exported_at"].startswith(vandaag)


def test_een_gebruiker_zonder_gegevens_krijgt_acht_lege_lijsten(client):
    _vul("anna", "ANNA-UNIEK")
    data, _ = _export(client, "leeg")
    assert data["username"] == "leeg"
    assert [data[soort] for soort in _SOORTEN] == [[]] * 8


def test_zonder_login_404_zoals_bij_verwijderen(app_client):
    """#1118: zonder login is iedereen de gedeelde `gast`; diens export zou het werk van alle bezoekers bevatten."""
    from routes.mijn_gegevens import GEEN_EIGEN_ACCOUNT

    client = app_client(herlaad=("core.auth",))
    from core import auth

    assert not auth.AUTH_ENABLED
    _vul(auth.FALLBACK_USER, "GAST-UNIEK")

    response = client.get(_EXPORT)

    assert response.status_code == 404
    assert response.json() == {"detail": GEEN_EIGEN_ACCOUNT}
    assert "GAST-UNIEK" not in response.text
    verwijderd = client.request("DELETE", "/api/mijn-gegevens", json={"bevestig": "verwijder"})
    assert verwijderd.status_code == 404
    assert verwijderd.json() == response.json()


# ── Inhoud en isolatie ───────────────────────────────────────────────────────


def test_alleen_de_eigen_rijen_per_soort(client):
    _vul("anna", "ANNA-UNIEK")
    _vul("bert", "BERT-UNIEK")
    data, body = _export(client, "anna")

    assert [c["id"] for c in data["conversations"]] == ["anna-c2", "anna-c1"]
    assert [w["id"] for w in data["workbooks"]] == ["anna-w2", "anna-w1"]
    assert [f["workbook_id"] for f in data["feedback"]] == ["anna-w1"]
    assert [f["tekst"] for f in data["algemene_feedback"]] == ["algemeen-ANNA-UNIEK"]
    assert [(r["conv_id"], r["data_key"]) for r in data["data_recipes"]] == [("anna-c1", "key-ANNA-UNIEK")]
    assert [(r["conv_id"], r["tekst_hash"]) for r in data["beurtbewijs"]] == [("anna-c1", "hash-ANNA-UNIEK")]
    assert data["tokengebruik"] == [{"dag": "2026-11-02", "eenheden": 1234}]
    assert [r["gegevens"] for r in data["oidc_gebruiker"]] == [_profiel("anna", "ANNA-UNIEK")]
    assert "BERT" not in body
    assert "bert" not in body


def test_tokengebruik_per_dag_op_volgorde_zonder_de_sleutel(client):
    """#1074: het verbruik per dag hoort bij het account; de sleutel (een pseudoniem, #1112) gaat niet mee."""
    for dag, eenheden in (("2026-11-05", 50), ("2026-10-30", 7), ("2026-11-01", 300)):
        db.tokengebruik_boek(_sleutel("anna"), dag, eenheden)
    db.tokengebruik_boek(_sleutel("anna"), "2026-11-01", 20)
    db.tokengebruik_boek(_sleutel("bert"), "2026-11-03", 999)

    data, body = _export(client, "anna")

    assert data["tokengebruik"] == [
        {"dag": "2026-10-30", "eenheden": 7},
        {"dag": "2026-11-01", "eenheden": 320},
        {"dag": "2026-11-05", "eenheden": 50},
    ]
    for geheim in (_sleutel("anna"), _sleutel("bert"), "999", "2026-11-03"):
        assert geheim not in body


def test_het_sram_profiel_van_het_account_zonder_de_sleutel(client):
    """#1209: het SRAM-profiel (naam, e-mail, organisatie, instelling) staat sinds #984 in `oidc_gebruikers` en hoort bij
    het account (AVG art. 15): één rij met de ontlede `gegevens` en `expires_at`, zonder het pseudoniem. Een ander
    account ziet er niets van; een nieuwe sleutel achteraan, dus `schema_version` blijft 1."""
    voor = int(time.time())
    _bewaar_profiel("anna", _profiel("anna", "ANNA-UNIEK"))
    _bewaar_profiel("bert", _profiel("bert", "BERT-UNIEK"))

    data, body = _export(client, "anna")

    assert data["schema_version"] == 1
    assert list(data)[-1] == "oidc_gebruiker"
    assert list(export.SOORTEN)[-1] == "oidc_gebruiker"
    [rij] = data["oidc_gebruiker"]
    assert set(rij) == {"gegevens", "expires_at"}
    assert rij["gegevens"] == _profiel("anna", "ANNA-UNIEK")
    assert isinstance(rij["expires_at"], int) and rij["expires_at"] > voor
    for geheim in (_oidc_sleutel("anna"), _oidc_sleutel("bert"), "sleutel", "BERT", "bert"):
        assert geheim not in body

    data_bert, body_bert = _export(client, "bert")
    assert [r["gegevens"] for r in data_bert["oidc_gebruiker"]] == [_profiel("bert", "BERT-UNIEK")]
    assert "ANNA" not in body_bert


def test_zonder_of_met_een_verlopen_sram_profiel_een_lege_lijst(client):
    """Geen rij: `[]`. Een verlopen rij leest de app niet meer (routes/auth.py), dus de export toont haar ook niet."""
    data, _ = _export(client, "anna")
    assert data["oidc_gebruiker"] == []

    with db._connection() as conn:
        db._execute(
            conn,
            "INSERT INTO oidc_gebruikers (sleutel, gegevens, expires_at, gebruikt) VALUES (?, ?, ?, ?)",
            (_oidc_sleutel("anna"), json.dumps({"name": "VERLOPEN"}), int(time.time()) - 1, 0),
        )
        conn.commit()

    data, body = _export(client, "anna")
    assert data["oidc_gebruiker"] == []
    assert "VERLOPEN" not in body


def test_json_kolommen_zijn_ontleed(client):
    _vul("anna", "ANNA-UNIEK")
    data, _ = _export(client, "anna")

    assert data["conversations"][1]["messages"] == _gesprek("ANNA-UNIEK")
    rapport = next(w for w in data["workbooks"] if w["id"] == "anna-w1")
    assert rapport["html_content"] == "<html><body>ANNA-UNIEK-html</body></html>"
    assert rapport["messages"] == _gesprek("ANNA-UNIEK")
    assert rapport["figures"] == [{"data": [], "layout": {"title": "ANNA-UNIEK"}}]
    assert rapport["dashboard_spec"] is None
    dashboard = next(w for w in data["workbooks"] if w["id"] == "anna-w2")
    assert dashboard["dashboard_spec"] == {"titel": "spec-ANNA-UNIEK"}
    assert dashboard["messages"] is None
    assert dashboard["figures"] is None
    assert dashboard["html_content"] is None
    assert data["feedback"][0]["answers"] == {"nuttig": "4-ANNA-UNIEK"}
    assert data["feedback"][0]["instelling"] == "Instelling ANNA-UNIEK"
    assert data["data_recipes"][0]["recipe"] == {"laad": ["query_data", {"id": "ANNA-UNIEK"}]}
    bewijs = data["beurtbewijs"][0]
    assert bewijs["lineage"] == {"key-ANNA-UNIEK": {"name": "query_data", "arguments": {"id": "ANNA-UNIEK"}}}
    assert bewijs["rekenbewijs"][0]["resultaat"] == "res-ANNA-UNIEK"
    # Sinds #1044 zonder `kaarten`: een kaart uit het gesprek staat als figuur in `figuren`.
    assert set(bewijs) == {"conv_id", "tekst_hash", "lineage", "rekenbewijs", "bronnen", "figuren", "created_at"}
    # De bronregels voor een vervolgantwoord na heropenen (#987), als JSON en niet als tekst.
    assert bewijs["bronnen"] == {
        "key-ANNA-UNIEK": [{"bron": "duo", "dataset": "p01hoinges", "regel": "DUO · ANNA-UNIEK"}]
    }
    # De stappen achter de figuren (#993), als JSON en niet als tekst.
    assert bewijs["figuren"][0]["id"] == "fig-ANNA-UNIEK" and bewijs["figuren"][0]["keys"] == ["key-ANNA-UNIEK"]
    assert "controle" not in bewijs
    assert bewijs["created_at"] == "2026-11-03T10:00:00+00:00"


def test_een_beurt_zonder_toolstap_zegt_waarom_ze_leeg_is(client):
    """#1217: een rij met vier lege verzamelingen blijft in de export (AVG), met `reden_leeg` als uitleg."""
    _vul("anna", "ANNA-UNIEK")
    leeg = {"lineage": {}, "rekenbewijs": [], "bronnen": {}, "figuren": [], "created_at": "2026-11-04T10:00:00+00:00"}
    db.save_beurtbewijs(
        "anna",
        "anna-c2",
        {
            "hash-leeg": leeg,
            # None wordt `null` in de database; ook dat telt als leeg.
            "hash-null": {**leeg, "lineage": None, "rekenbewijs": None, "created_at": "2026-11-05T10:00:00+00:00"},
            # Een rij met alleen een bronregel heeft wel inhoud.
            "hash-bron": {**leeg, "bronnen": {"k": [{"regel": "DUO"}]}, "created_at": "2026-11-06T10:00:00+00:00"},
        },
    )
    # Een lege tekst in een kolom (oude of handmatig gewijzigde rij) telt ook als leeg.
    db.save_beurtbewijs("anna", "anna-c2", {"hash-tekst": {**leeg, "created_at": "2026-11-07T10:00:00+00:00"}})
    with db._connection() as conn:
        db._execute(conn, "UPDATE beurtbewijs SET lineage = '' WHERE tekst_hash = ?", ("hash-tekst",))
        conn.commit()

    data, _ = _export(client, "anna")

    rijen = {r["tekst_hash"]: r for r in data["beurtbewijs"]}
    assert list(rijen) == ["hash-ANNA-UNIEK", "hash-leeg", "hash-null", "hash-bron", "hash-tekst"]
    for tekst_hash in ("hash-leeg", "hash-null", "hash-tekst"):
        assert rijen[tekst_hash]["reden_leeg"] == "geen toolstap in deze beurt"
    assert rijen["hash-leeg"] == {
        "conv_id": "anna-c2",
        "tekst_hash": "hash-leeg",
        "lineage": {},
        "rekenbewijs": [],
        "bronnen": {},
        "figuren": [],
        "created_at": "2026-11-04T10:00:00+00:00",
        "reden_leeg": "geen toolstap in deze beurt",
    }
    assert rijen["hash-null"]["lineage"] is None and rijen["hash-null"]["rekenbewijs"] is None
    for tekst_hash in ("hash-ANNA-UNIEK", "hash-bron"):
        assert "reden_leeg" not in rijen[tekst_hash]
    assert rijen["hash-bron"]["bronnen"] == {"k": [{"regel": "DUO"}]}
    assert data["schema_version"] == 1


def test_de_enige_regelovergang_is_het_laatste_teken(client):
    """De frontend bewaart alleen een bestand dat op een regelovergang eindigt: dat is het eindteken."""
    db.upsert_conversation("anna", "c1", "Twee\nregels", 1_700_000_000, _gesprek("een\nmeer"))
    db.add_algemene_feedback("anna", "idee", "regel een\nregel twee", "/chat")
    _, body = _export(client, "anna")
    assert body.endswith("}\n")
    assert body.count("\n") == 1


def test_niet_ascii_blijft_leesbaar(client):
    db.upsert_conversation("anna", "c1", "Café", 1_700_000_000, _gesprek("één"))
    _, body = _export(client, "anna")
    assert "Café" in body
    assert "één" in body


def test_een_onleesbare_json_kolom_gaat_als_tekst_mee(client):
    db.upsert_conversation("anna", "c1", "Oud", 1_700_000_000, [])
    with db._connection() as conn:
        db._execute(conn, "UPDATE conversations SET messages = ? WHERE id = ?", ("{kapot", "c1"))
        conn.commit()
    data, _ = _export(client, "anna")
    assert data["conversations"][0]["messages"] == "{kapot"


def test_geen_tokens_of_hashes_in_de_export(client):
    from core import auth

    _vul("anna", "ANNA-UNIEK")
    ingetrokken = auth.make_token("anna")
    auth.revoke_token(ingetrokken)
    with db._connection() as conn:
        hashes = [r["token_hash"] for r in db._execute(conn, "SELECT token_hash FROM revoked_tokens").fetchall()]
    assert hashes

    response = _als(client, "anna").get(_EXPORT)
    token = client.headers["Authorization"].removeprefix("Bearer ")
    for geheim in [*hashes, ingetrokken, token]:
        assert geheim not in response.text
    assert "revoked" not in response.text


# ── Log en opbouw ────────────────────────────────────────────────────────────


def test_het_log_telt_alleen(client, caplog):
    _vul("anna", "ANNA-UNIEK")
    caplog.set_level(logging.INFO)
    _export(client, "anna")

    log = "\n".join(r.getMessage() for r in caplog.records)
    assert "conversations=2" in log
    assert "algemene_feedback=1" in log
    for tekst in ("Vraag ANNA-UNIEK", "Antwoord ANNA-UNIEK", "algemeen-ANNA-UNIEK", "anna"):
        assert tekst not in log


def test_de_stukken_vormen_samen_de_json(tmp_path, monkeypatch):
    """De generator alleen, zonder app: kop, dan per soort een lijst, met een vaste tijd."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    db.init_db()
    nu = datetime(2026, 10, 20, 9, 30, tzinfo=UTC)
    stukken = list(export.export_json_chunks("niemand-in-deze-db", nu))
    assert len(stukken) > 1
    data = json.loads("".join(stukken))
    assert data["exported_at"] == "2026-10-20T09:30:00+00:00"
    assert [data[soort] for soort in _SOORTEN] == [[]] * 8


def test_werkboeken_een_voor_een(client, monkeypatch):
    """Eerst de ids, daarna per werkboek één query, pas als het vorige al is geschreven (#633).

    Bij elk werkboek dat de generator oplevert, zijn er precies zoveel werkboeken uit de database
    gehaald als er al zijn geschreven: hij laadt er nooit vooruit, dus nooit alle HTML tegelijk.
    """
    groot = "x" * 200_000
    for i in range(5):
        db.upsert_workbook("anna", f"w{i}", f"R{i}", "", html_content=groot, created_at=f"2026-10-1{i}")

    opgehaald: list[str] = []
    echte_rij = export._rij

    def tel(sql, params):
        if "html_content" in sql:
            opgehaald.append(params[0])
        return echte_rij(sql, params)

    monkeypatch.setattr(export, "_rij", tel)
    geschreven = 0
    for stuk in export.export_json_chunks("anna"):
        if groot in stuk:
            geschreven += 1
            assert len(opgehaald) == geschreven
            assert len(stuk) < len(groot) + 1000
    assert geschreven == 5
    assert opgehaald == ["w4", "w3", "w2", "w1", "w0"]


def test_elke_query_filtert_op_de_gebruiker(monkeypatch):
    """Geen query zonder `username = ?`, en elke parameterlijst draagt de gebruikersnaam; `tokengebruik` en
    `oidc_gebruikers` kennen alleen het pseudoniem van de naam (#1112, #984) en filteren daarop."""
    queries: list[tuple[str, tuple]] = []

    def vang(sql, params):
        queries.append((sql, params))
        return []

    monkeypatch.setattr(export, "_rijen", vang)
    list(export.export_json_chunks("anna"))
    assert len(queries) == 8
    *op_naam, tokengebruik, oidc_gebruiker = queries
    for sql, params in op_naam:
        assert re.search(r"WHERE username = \?", sql)
        assert "anna" in params
    assert re.search(r"FROM tokengebruik WHERE sleutel = \?", tokengebruik[0])
    assert tokengebruik[1] == (_sleutel("anna"),)
    assert re.search(r"FROM oidc_gebruikers WHERE sleutel = \?", oidc_gebruiker[0])
    assert oidc_gebruiker[1][0] == _oidc_sleutel("anna")
