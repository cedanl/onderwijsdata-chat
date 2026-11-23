"""POST /api/workbooks/{id}/docx (#1038): een eigen bewaard rapport als Word-document, met grafieken uit de browser."""

import tempfile
from io import BytesIO

import pytest
from docx import Document

from core.rate_limit import RateLimiter
from tests.rapport_docx_hulp import RAPPORT_HTML, png

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture(autouse=True)
def verse_limiet(monkeypatch):
    from routes import rapport_docx

    monkeypatch.setattr(rapport_docx, "_limiter", RateLimiter(max_attempts=30, window_seconds=60))


@pytest.fixture
def client(app_client):
    return app_client(users="anna:wachtwoord-a,bert:wachtwoord-b", herlaad=("core.auth",), init_db=True)


def _als(client, gebruiker: str) -> None:
    """Ingelogd zonder /api/auth/login: de login-limiter telt over de hele testrun mee."""
    from core import auth

    client.headers["Authorization"] = f"Bearer {auth.make_token(gebruiker)}"


def _bewaar(client, wb_id: str = "r1", html: str = RAPPORT_HTML, title: str = "Instroom hbo") -> None:
    body = {"title": title, "description": "", "htmlContent": html, "createdAt": "2026-11-18T10:00:00Z"}
    assert client.put(f"/api/workbooks/{wb_id}", json=body).status_code == 200


def _grafieken(*delen: tuple[str, bytes]) -> list:
    return [(naam, (f"{naam}.png", data, "image/png")) for naam, data in delen]


def test_de_route_bestaat(client):
    from server import app

    assert "post" in app.openapi()["paths"]["/api/workbooks/{wb_id}/docx"]


def test_een_lange_titel_met_accent_geeft_een_korte_naam_zoals_in_de_browser(client):
    """#1124, #1125: dezelfde regel als workbookFilename: accent weg, emoji één streepje, hoogstens 120 tekens."""
    _als(client, "anna")
    titel = "🎓 Commerciële opleidingen in het hoger onderwijs " * 7
    _bewaar(client, title=titel)
    response = client.post("/api/workbooks/r1/docx", files=_grafieken(("grafiek-0", png())))
    assert response.status_code == 200
    naam = response.headers["content-disposition"].split('filename="')[1].removesuffix('"')
    assert naam.startswith("Commerciele_opleidingen_in_het_hoger_onderwijs_Commerciele_")
    assert "__" not in naam
    assert len(naam.encode()) < 255
    assert len(naam.removesuffix(".docx")) <= 120


def test_een_eigen_rapport_als_word_document(client):
    _als(client, "anna")
    _bewaar(client)
    response = client.post("/api/workbooks/r1/docx", files=_grafieken(("grafiek-0", png())))
    assert response.status_code == 200
    assert response.headers["content-type"] == DOCX_TYPE
    assert response.headers["content-disposition"] == 'attachment; filename="Instroom_hbo.docx"'
    doc = Document(BytesIO(response.content))
    assert doc.paragraphs[0].text == "Instroom hbo in Utrecht {{ 7*7 }}"
    assert len(doc.inline_shapes) == 1
    assert len(doc.tables) == 1


def test_zonder_grafieken_ook(client):
    _als(client, "anna")
    _bewaar(client)
    response = client.post("/api/workbooks/r1/docx")
    assert response.status_code == 200
    doc = Document(BytesIO(response.content))
    assert len(doc.inline_shapes) == 0
    assert sum(p.text == "Grafiek niet beschikbaar" for p in doc.paragraphs) == 3


def test_een_rapport_met_een_lange_titel(client):
    titel = "Hoeveel studenten stromen in " + "x" * 300
    _als(client, "anna")
    _bewaar(client, html=RAPPORT_HTML.replace("Instroom hbo in Utrecht {{ 7*7 }}</h1>", f"{titel}</h1>"))
    response = client.post("/api/workbooks/r1/docx")
    assert response.status_code == 200
    assert Document(BytesIO(response.content)).paragraphs[0].text == titel


def test_een_rapport_van_een_ander_is_niet_gevonden(client):
    _als(client, "anna")
    _bewaar(client)
    _als(client, "bert")
    vreemd = client.post("/api/workbooks/r1/docx")
    onbekend = client.post("/api/workbooks/bestaat-niet/docx")
    assert vreemd.status_code == onbekend.status_code == 404
    assert vreemd.json() == onbekend.json() == {"detail": "Werkboek niet gevonden"}


def test_zonder_inloggen_geen_document(client):
    _als(client, "anna")
    _bewaar(client)
    del client.headers["Authorization"]
    assert client.post("/api/workbooks/r1/docx").status_code == 401


def test_een_werkboek_zonder_rapport(client):
    _als(client, "anna")
    _bewaar(client, html="<p>geen rapport</p>")
    response = client.post("/api/workbooks/r1/docx")
    assert response.status_code == 422
    assert response.json() == {"detail": "Dit werkboek heeft geen rapport om als Word-document te downloaden."}


@pytest.mark.parametrize(
    ("delen", "status"),
    [
        ((("grafiek-0", b"GIF89a" + b"\x00" * 40),), 400),
        ((("grafiek-9", png()),), 400),
        ((("grafiek-0", png(extra=2 * 1024 * 1024)),), 413),
    ],
)
def test_een_ongeldige_grafiek_wordt_geweigerd(client, delen, status):
    _als(client, "anna")
    _bewaar(client)
    assert client.post("/api/workbooks/r1/docx", files=_grafieken(*delen)).status_code == status


def test_tekst_uit_het_verzoek_telt_niet(client):
    """Het lichaam bevat alleen grafieken: een tekstveld (een andere titel) wordt geweigerd, niet gebruikt."""
    _als(client, "anna")
    _bewaar(client)
    response = client.post(
        "/api/workbooks/r1/docx", data={"titel": "Iets anders"}, files=_grafieken(("grafiek-0", png()))
    )
    assert response.status_code == 400
    response = client.post("/api/workbooks/r1/docx", json={"titel": "Iets anders"})
    assert response.status_code == 400


def test_de_upload_komt_niet_op_schijf(client, monkeypatch):
    """Een grafiek boven 1 MiB: Starlettes formulierlezer zou hem in een tijdelijk bestand zetten."""
    _als(client, "anna")
    _bewaar(client)

    def geen_bestand(*args, **kwargs):
        raise AssertionError("de upload ging naar schijf")

    monkeypatch.setattr(tempfile, "SpooledTemporaryFile", geen_bestand)
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", geen_bestand)
    monkeypatch.setattr(tempfile, "TemporaryFile", geen_bestand)
    groot = png(extra=1536 * 1024)
    response = client.post("/api/workbooks/r1/docx", files=_grafieken(("grafiek-0", groot)))
    assert response.status_code == 200
    assert len(Document(BytesIO(response.content)).inline_shapes) == 1


def test_te_vaak_achter_elkaar(client, monkeypatch):
    from routes import rapport_docx

    monkeypatch.setattr(rapport_docx, "_limiter", RateLimiter(max_attempts=1, window_seconds=60))
    _als(client, "anna")
    _bewaar(client)
    assert client.post("/api/workbooks/r1/docx").status_code == 200
    response = client.post("/api/workbooks/r1/docx")
    assert response.status_code == 429
    assert "Retry-After" in response.headers
