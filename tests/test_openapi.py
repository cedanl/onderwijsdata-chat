"""Het OpenAPI-schema beschrijft de API zoals ze is (#1188).

Het schema is wat een gegenereerde client en de API-documentatie lezen; een afwijking daarin is een client die elk
antwoord verkeerd leest. De app komt uit de fabriek met de documentatie aan en een tijdelijke frontend, zodat ook de
catch-all van de SPA in het schema had kunnen komen.
"""

import pytest
from fastapi.testclient import TestClient

from core.foutmeldingen import ONGELDIGE_INVOER


@pytest.fixture(scope="module")
def schema(tmp_path_factory):
    from server import create_app

    dist = tmp_path_factory.mktemp("dist")
    (dist / "index.html").write_text("<html></html>")
    (dist / "assets").mkdir()
    return create_app(api_docs=True, frontend_dist=dist).openapi()


def _operaties(schema):
    for pad, methoden in schema["paths"].items():
        for methode, operatie in methoden.items():
            yield pad, methode, operatie


# ── Versie (#1157) ───────────────────────────────────────────────────────────


def test_de_schemaversie_is_de_versie_van_version(schema):
    from server import app

    assert schema["info"]["version"] == TestClient(app).get("/version").json()["version"]
    assert schema["info"]["version"] != "0.1.0"


def test_er_is_een_bron_voor_de_appversie(monkeypatch):
    from config import Config
    from core.appversie import app_versie

    monkeypatch.setattr(Config, "APP_VERSION", "9.8.7")
    assert app_versie() == "9.8.7"
    monkeypatch.setattr(Config, "APP_VERSION", None)
    assert app_versie().count(".") == 2


def test_het_schema_noemt_de_release_uit_het_chart(monkeypatch):
    from config import Config
    from server import create_app

    monkeypatch.setattr(Config, "APP_VERSION", "2.1.0")
    assert create_app(api_docs=True).openapi()["info"]["version"] == "2.1.0"


# ── Foutvorm (#1158) ─────────────────────────────────────────────────────────


def test_elke_422_is_een_detailstring(schema):
    gevonden = [(pad, methode) for pad, methode, op in _operaties(schema) if "422" in op["responses"]]
    assert gevonden  # de test loopt echt langs operaties met invoer

    for pad, methode in gevonden:
        inhoud = schema["paths"][pad][methode]["responses"]["422"]["content"]["application/json"]
        fout = schema["components"]["schemas"][inhoud["schema"]["$ref"].rsplit("/", 1)[1]]
        assert fout["properties"]["detail"]["type"] == "string", (pad, methode)


def test_de_validatieschemas_van_fastapi_zijn_weg(schema):
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    assert "ValidationError" not in schema["components"]["schemas"]
    assert "HTTPValidationError" not in str(schema["paths"])


def test_de_422_van_het_schema_is_wat_de_api_geeft(schema):
    from server import create_app

    resp = TestClient(create_app(api_docs=True)).put("/api/conversations/x", json={"title": {"a": 1}})

    assert resp.status_code == 422
    assert resp.json() == {"detail": ONGELDIGE_INVOER}


def test_de_foutmelding_in_het_schema_is_een_voorbeeld_van_de_echte_tekst(schema):
    fout = schema["components"]["schemas"]["Foutmelding"]

    assert fout["properties"]["detail"]["examples"] == [ONGELDIGE_INVOER]
    assert fout["required"] == ["detail"]
