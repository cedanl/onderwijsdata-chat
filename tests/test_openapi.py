"""Het OpenAPI-schema beschrijft de API zoals ze is (#1188).

Het schema is wat een gegenereerde client en de API-documentatie lezen; een afwijking daarin is een client die elk
antwoord verkeerd leest. De app komt uit de fabriek met de documentatie aan en een tijdelijke frontend, zodat ook de
catch-all van de SPA in het schema had kunnen komen.
"""

import pytest
from fastapi.testclient import TestClient

from core.foutmeldingen import ONGELDIGE_INVOER
from routes.rapport_docx import DOCX_TYPE


def _frontend(dist, html="<html></html>"):
    """Een minimale gebouwde frontend: de SPA-route en /assets hangen eraan."""
    (dist / "index.html").write_text(html)
    (dist / "assets").mkdir()
    return dist


@pytest.fixture(scope="module")
def schema(tmp_path_factory):
    from server import create_app

    dist = _frontend(tmp_path_factory.mktemp("dist"))
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


def test_de_422_van_het_schema_is_wat_de_api_geeft():
    # Het inlogeindpunt is openbaar: geen authenticatie die een andere test in dezelfde run aan of uit zette.
    from server import create_app

    resp = TestClient(create_app(api_docs=True)).post("/api/auth/login", json={"username": {"a": 1}})

    assert resp.status_code == 422
    assert resp.json() == {"detail": ONGELDIGE_INVOER}


def test_de_foutmelding_in_het_schema_is_een_voorbeeld_van_de_echte_tekst(schema):
    fout = schema["components"]["schemas"]["Foutmelding"]

    assert fout["properties"]["detail"]["examples"] == [ONGELDIGE_INVOER]
    assert fout["required"] == ["detail"]


# ── Bestanden (#1159) ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "pad, methode, media_type",
    [
        ("/api/data/csv", "get", "text/csv"),
        ("/api/workbooks/{wb_id}/docx", "post", DOCX_TYPE),
        ("/api/mijn-gegevens/export", "get", "application/json"),
    ],
)
def test_een_bestandseindpunt_noemt_zijn_echte_mediatype_als_bijlage(schema, pad, methode, media_type):
    antwoord = schema["paths"][pad][methode]["responses"]["200"]

    assert list(antwoord["content"]) == [media_type]
    assert antwoord["content"][media_type]["schema"] == {"type": "string", "format": "binary"}
    assert "Content-Disposition" in antwoord["headers"]


# ── Geen SPA-route (#1160) ───────────────────────────────────────────────────


def test_de_spa_catch_all_staat_niet_in_het_schema(schema):
    assert not [pad for pad in schema["paths"] if "full_path" in pad]
    assert "Serve Spa" not in str(schema)


def test_de_spa_geeft_nog_index_html_op_een_onbekend_pad(tmp_path):
    from server import create_app

    dist = _frontend(tmp_path, "<html>shell</html>")
    resp = TestClient(create_app(api_docs=True, frontend_dist=dist)).get("/ergens/anders")

    assert resp.status_code == 200
    assert resp.text == "<html>shell</html>"
