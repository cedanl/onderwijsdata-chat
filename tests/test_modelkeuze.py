"""De modelkeuze uit de chat is begrensd tot het aanbod van de gebruiker (#755).

De picker in de frontend toont alleen het aanbod, maar een eigen WebSocket-client kan elke naam meesturen.
De server geeft dan alleen een model door dat in het aanbod staat; anders valt hij terug op MODEL.
"""

import asyncio
import logging

import pytest

from core import config
from routes import chat

STANDAARD = "azure_ai/standaard"
DUUR = "azure_ai/duur"
EXTRA = "azure_ai/extra"
GEWOON_AANBOD = f"{STANDAARD},{EXTRA}"
USERNAME = "modelkeuze-test"


@pytest.fixture(autouse=True)
def _standaardmodel(monkeypatch):
    monkeypatch.setattr(config, "MODEL", STANDAARD)


def _aanbod(monkeypatch, globaal: str | None = GEWOON_AANBOD, per_gebruiker: dict[str, list[str]] | None = None):
    monkeypatch.setattr(config, "_AVAILABLE_MODELS_RAW", globaal)
    monkeypatch.setattr(config, "_USER_MODELS", per_gebruiker or {})


# ─── toegestaan_model ────────────────────────────────────────────────────────


def test_een_model_in_het_aanbod_blijft_ongewijzigd(monkeypatch):
    _aanbod(monkeypatch)

    assert config.toegestaan_model(USERNAME, EXTRA) == EXTRA


def test_een_model_buiten_het_aanbod_wordt_het_standaardmodel(monkeypatch):
    _aanbod(monkeypatch)

    assert config.toegestaan_model(USERNAME, DUUR) == STANDAARD


def test_het_eigen_aanbod_van_een_gebruiker_gaat_voor_het_globale(monkeypatch):
    _aanbod(monkeypatch, per_gebruiker={USERNAME: [DUUR]})

    assert config.toegestaan_model(USERNAME, DUUR) == DUUR
    assert config.toegestaan_model(USERNAME, EXTRA) == STANDAARD
    assert config.toegestaan_model("iemand-anders", DUUR) == STANDAARD


def test_zonder_aanbod_is_alleen_het_standaardmodel_toegestaan(monkeypatch):
    _aanbod(monkeypatch, globaal=None)

    assert config.toegestaan_model(USERNAME, DUUR) == STANDAARD
    assert config.toegestaan_model(USERNAME, STANDAARD) == STANDAARD


@pytest.mark.parametrize("gevraagd", [None, "", 5, ["azure_ai/extra"], {"model": EXTRA}])
def test_een_leeg_of_geen_tekst_model_wordt_het_standaardmodel(monkeypatch, gevraagd):
    _aanbod(monkeypatch)

    assert config.toegestaan_model(USERNAME, gevraagd) == STANDAARD


# ─── de handlers van de chat ─────────────────────────────────────────────────


def _sessie(gevraagd) -> dict:
    session = chat._new_session(username=USERNAME)
    session["chat_settings"] = {"model": gevraagd}
    return session


def _run_tot_einde(action: str, msg: dict, session: dict):
    async def emit(event):
        pass

    async def scenario():
        taak = await chat.ACTIES[action]({"action": action, **msg}, session, emit, None)
        if taak is not None:
            await taak

    asyncio.run(scenario())


@pytest.fixture
def modellen(monkeypatch) -> list[tuple[str, str | None]]:
    """Wat elke run als model zou krijgen, als (soort, model); de agent zelf draait niet."""
    gezien: list[tuple[str, str | None]] = []
    monkeypatch.setattr(chat, "DASHBOARDS_ENABLED", True)

    async def bericht(content, session, emit, model):
        gezien.append(("bericht", model))

    async def dashboard(session, emit, model):
        gezien.append(("dashboard", model))

    async def rapport(session, emit, model, **_):
        gezien.append(("rapport", model))

    async def ververs(recipe, figure_recipes, spec, session, emit, model, mode):
        gezien.append(("ververs", model))

    monkeypatch.setattr(chat, "_process_message", bericht)
    monkeypatch.setattr(chat, "_generate_dashboard", dashboard)
    monkeypatch.setattr(chat, "_generate_report", rapport)
    monkeypatch.setattr(chat, "_refresh_dashboard", ververs)
    return gezien


ACTIES = [
    ("bericht", "message", {"content": "hoeveel studenten?"}),
    ("dashboard", "generate_dashboard", {}),
    ("rapport", "generate_report", {}),
    ("ververs", "refresh_dashboard", {"recipe": [], "figure_recipes": []}),
]


@pytest.mark.parametrize(("soort", "actie", "msg"), ACTIES)
def test_een_niet_aangeboden_model_wordt_bij_elke_actie_het_standaardmodel(monkeypatch, modellen, soort, actie, msg):
    _aanbod(monkeypatch)

    _run_tot_einde(actie, msg, _sessie(DUUR))

    assert modellen == [(soort, STANDAARD)]


@pytest.mark.parametrize(("soort", "actie", "msg"), ACTIES)
def test_een_aangeboden_model_wordt_bij_elke_actie_gebruikt(monkeypatch, modellen, soort, actie, msg):
    _aanbod(monkeypatch)

    _run_tot_einde(actie, msg, _sessie(EXTRA))

    assert modellen == [(soort, EXTRA)]


def test_de_verduidelijkingsbeurt_erft_het_begrensde_model(monkeypatch, modellen):
    _aanbod(monkeypatch)
    session = _sessie(DUUR)

    _run_tot_einde("message", {"content": "hoeveel studenten?"}, session)
    _run_tot_einde("clarification_choice", {"choice": "2024/2025"}, session)

    assert modellen == [("bericht", STANDAARD), ("bericht", STANDAARD)]


def test_een_model_dat_geen_tekst_is_geeft_geen_fout(monkeypatch, modellen):
    _aanbod(monkeypatch)
    session = chat._new_session(username=USERNAME)
    session["chat_settings"] = ["geen", "dict"]

    _run_tot_einde("message", {"content": "hoeveel studenten?"}, session)

    assert modellen == [("bericht", STANDAARD)]


def test_een_geweigerde_modelnaam_staat_niet_letterlijk_in_het_log(monkeypatch, modellen, caplog):
    _aanbod(monkeypatch)
    geheim = "azure_ai/een-eigen-deployment"

    with caplog.at_level(logging.WARNING, logger=chat.logger.name):
        _run_tot_einde("message", {"content": "hoeveel studenten?"}, _sessie(geheim))

    regels = [r.getMessage() for r in caplog.records if "Modelkeuze buiten het aanbod" in r.getMessage()]
    assert len(regels) == 1
    assert geheim not in regels[0]
    assert "model_len=" in regels[0] and "model_hash=" in regels[0]
