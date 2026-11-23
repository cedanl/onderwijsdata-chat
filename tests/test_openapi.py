"""Het OpenAPI-schema beschrijft de API zoals ze is (#1188).

Het schema is wat een gegenereerde client en de API-documentatie lezen; een afwijking daarin is een client die elk
antwoord verkeerd leest. De app komt uit de fabriek met de documentatie aan en een tijdelijke frontend, zodat ook de
catch-all van de SPA in het schema had kunnen komen.
"""

import pytest
from fastapi.testclient import TestClient


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
