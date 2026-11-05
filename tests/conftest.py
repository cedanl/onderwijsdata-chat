import importlib
import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent import beurtbewijs, recepten
from tests.netwerkblok import BLOK, melding
from tools import cbs, cbs_preflight, profiel, store


def pytest_configure(config):
    """Uitgaand netwerk dicht voor de hele run, ook tijdens het verzamelen (#915); zie tests/netwerkblok.py."""
    BLOK.installeer()


def pytest_unconfigure(config):
    BLOK.verwijder()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Vóór de fixtures van de test, ook die met scope module: alleen een test met marker `live` mag naar buiten."""
    BLOK.begin(open=item.get_closest_marker("live") is not None)


@pytest.fixture(autouse=True)
def netwerk_dicht():
    """Een test die naar buiten probeerde, faalt, ook als de code de weigering opving en terugviel (#915)."""
    yield
    if pogingen := BLOK.einde():
        pytest.fail(melding(pogingen), pytrace=False)


@pytest.fixture(autouse=True)
def clear_store():
    store.clear()
    recepten.wis()
    beurtbewijs.wis()
    profiel.vergeet()
    yield
    store.clear()
    recepten.wis()
    beurtbewijs.wis()
    profiel.vergeet()


@pytest.fixture(autouse=True)
def no_cbs_dimension_call(monkeypatch):
    """Unittests doen geen live CBS-dimensiecall (Perioden.Status); tests die hem nodig hebben patchen zelf."""
    monkeypatch.setattr(cbs, "get", lambda dataset_id, endpoint, **params: [])
    cbs._dimension_rows.cache_clear()
    cbs._tabelbeschrijving.cache_clear()


@pytest.fixture(autouse=True)
def geen_cbs_preflight(monkeypatch):
    """Unittests vragen het CBS-contract niet live om een oordeel (#370); tests van de preflight patchen zelf."""
    monkeypatch.setattr(
        cbs_preflight,
        "validate_selection",
        lambda dataset_id, eis, live=False: {"dataset_id": dataset_id, "status": "unknown", "checks": []},
    )


@pytest.fixture(autouse=True)
def bronretry_zonder_wachten(monkeypatch):
    """Een bronfout die de code opnieuw probeert (#867), wacht in de tests niet echt; het aantal pogingen blijft."""
    from tools import bronretry

    monkeypatch.setattr(bronretry, "STANDAARD", bronretry.Beleid(slaap=lambda s: None))


@pytest.fixture(autouse=True)
def geen_registerdownload(monkeypatch):
    """Unittests bouwen het instellingsregister niet uit live DUO op (#915): het staat leeg en vers klaar.

    Zonder dit downloadde de eerste test die een instellingsnaam toetste het register, en welke test dat was, hing af
    van de volgorde. `duo_fixtures` en de tests van het register zetten `_cache` op None en bouwen het dan zelf op.
    """
    from core import actualiteit
    from data import instellingen

    monkeypatch.setattr(instellingen, "_cache", [])
    monkeypatch.setattr(instellingen, "_alias_lookup", None)
    monkeypatch.setattr(instellingen, "_ADRES_CACHE", {})
    monkeypatch.setattr(instellingen, "_opgehaald_op", actualiteit.nu())


@pytest.fixture(autouse=True)
def geen_adresdownload(monkeypatch):
    """Unittests downloaden geen DUO-adresbestanden voor de instellingsprovincie (#453); tests die hem nodig hebben patchen zelf."""
    monkeypatch.setattr("tools.instellingsprovincie.get_adres_lookup", lambda: {})


@pytest.fixture(autouse=True)
def geen_fusieopvraging(monkeypatch):
    """Unittests vragen RIO niet om de voorgangers van een instelling in een DUO-reeks (#728): geen fusies.

    Elke meerjarige DUO-selectie per instelling vraagt ze op (`dekking.van`); `tests/test_fusies.py` patcht zelf."""
    from tools import fusies

    monkeypatch.setattr(fusies, "voorgangers", lambda code, sinds=None, peildatum=None: [])
    fusies._voorgangers.cache_clear()


@pytest.fixture(autouse=True)
def geen_locatieopvraging(monkeypatch):
    """Unittests laden het mbo-aanbod per locatie niet en vragen RIO niet om aanbieders (#744): geen locaties.

    Elk filter op de plaats, gemeente of provincie van een mbo-instelling zoekt ze op (`tools/regiolocaties.py`);
    `tests/test_regiolocaties.py` patcht zelf."""
    from tools import regiolocaties

    monkeypatch.setattr(
        regiolocaties, "_laad_aanbod", lambda: pd.DataFrame(columns=["ONDERWIJSAANBIEDERID", "PLAATSNAAM"])
    )
    monkeypatch.setattr(regiolocaties, "onderwijsaanbieders", lambda brin, peildatum=None: [])
    regiolocaties.wis_caches()


@pytest.fixture
def duo_fixtures(monkeypatch):
    """`duo.load` leest de bevroren DUO-bestanden van `scripts/duo_testfixtures.py`, niet onderwijsdata.duo.nl (#766).

    Voor de instellingenregister- en dashboardtests: de pytest-job blokkeert elke MR en mag niet omvallen
    op een storing bij DUO. Een bestand zonder fixture faalt met de naam erbij, zodat het script hem krijgt.
    """
    from onderwijsbronnen import duo

    import data.dashboard
    import data.instellingen
    from scripts.duo_testfixtures import MAP, bestandsnaam

    tekst = json.loads((MAP / "tekstkolommen.json").read_text())

    def load(dataset_id: str, resource: int = 0, **kwargs) -> pd.DataFrame:
        naam = bestandsnaam(dataset_id, resource)
        if naam not in tekst:
            raise AssertionError(f"geen DUO-fixture {naam}: voeg hem toe in scripts/duo_testfixtures.py")
        return pd.read_csv(MAP / naam, dtype=dict.fromkeys(tekst[naam], str))

    def wis_caches():
        # Het register en de dashboardladers cachen in de module: anders blijft data van een andere test staan.
        data.instellingen._cache = data.instellingen._alias_lookup = data.instellingen._ADRES_CACHE = None
        for functie in vars(data.dashboard).values():
            if hasattr(functie, "cache_clear"):
                functie.cache_clear()

    monkeypatch.setattr(duo, "load", load)
    wis_caches()
    yield
    wis_caches()


_PROVINCIES = (
    "Drenthe", "Flevoland", "Friesland", "Gelderland", "Groningen", "Limburg", "Noord-Brabant", "Noord-Holland",
    "Overijssel", "Utrecht", "Zeeland", "Zuid-Holland",
)  # fmt: skip


@pytest.fixture
def arbeidsmarkt_fixtures(monkeypatch):
    """UWV en ROA zonder netwerk (#915), voor de vormtests van dashboards en chat.

    ROA is de bevroren snapshot van de gouden tests (`tests/fixtures/gouden/`). De gouden UWV-snapshot kent alleen
    Flevoland; hier krijgt elke provincie tien vacatures per beroepencluster uit de sectorindeling, zodat elke
    instelling clusters heeft. Die aantallen zijn niet echt: wie UWV-waarden toetst, gebruikt de fixture `gouden`.

    De fixture vervangt de laders van riodata, niet `_uwv` en `_roa`: zo melden die hun bestand voor het bronblok van
    de dashboards (#904), zoals buiten de tests.
    """
    from onderwijsbronnen import roa as riodata_roa
    from onderwijsbronnen import uwv as riodata_uwv

    from data import arbeidsmarkt
    from scripts import gouden_testfixtures as g

    clusters = sorted({c for lijst in arbeidsmarkt.SECTOR_CLUSTER_MAP.values() for c in lijst})
    uwv = pd.DataFrame(
        [
            {"PEILDATUM": "16-05-2023", "PROVINCIE": p, "GEMEENTE": p, "BEROEPENCLUSTER": c, "AANTAL": 10}
            for p in _PROVINCIES
            for c in clusters
        ]
    )
    roa = pd.read_csv(g.MAP / g.ROA, dtype={"versie": str})
    monkeypatch.setattr(riodata_uwv, "load", lambda *a, **k: uwv.copy())
    monkeypatch.setattr(riodata_roa, "load", lambda *a, **k: roa.copy())
    # Alleen de caches van de echte laders: de fixture `gouden` of een test vervangt ze soms door een lambda.
    laders = [lader for lader in (arbeidsmarkt._uwv, arbeidsmarkt._roa) if hasattr(lader, "cache_clear")]
    for lader in laders:
        lader.cache_clear()
    yield
    for lader in laders:
        lader.cache_clear()


@pytest.fixture
def gouden(duo_fixtures, monkeypatch):
    """De bevroren bronnen van de gouden tests (`tests/gouden.py`, #870), met het netwerk dicht."""
    from tests import gouden

    gouden.zet_klaar(monkeypatch)
    yield
    gouden.wis_caches()


@pytest.fixture
def dashboards_aan(monkeypatch):
    """De dashboardvlag staat standaard uit (#765); tests van de vaste dashboards zetten hem hiermee aan."""
    import routes.instellingen

    monkeypatch.setattr(routes.instellingen, "DASHBOARDS_ENABLED", True)


@pytest.fixture
def zonder_scopegrens():
    """Voor tests van de laad- en metadatamechaniek met test-ID's of vo-bestanden.

    De mbo/hbo/wo-grens zelf staat in test_scopeprofiel.py (#355).
    """
    from tools.catalog import _rio_duo_alles

    with (
        patch("tools.cbs.scope_blokkade", return_value=None),
        patch("tools.duo.scope_blokkade", return_value=None),
        patch("tools.rio.scope_blokkade", return_value=None),
        patch("tools.rio.scopeprofiel.sectorfilter_ontbreekt", return_value=None),
        patch("tools.catalog._rio_duo", side_effect=_rio_duo_alles),
    ):
        yield


@pytest.fixture
def zonder_scopekaart(monkeypatch):
    """Voor tests van de beurt met een nagebootst model: geen verduidelijkingskaart uit code vóór het model.

    Of een korte testvraag als "vraag" een maatkaart krijgt (#348), hangt af van de gepinde catalogus;
    zulke tests gaan over wat het model daarna doet. De kaart zelf staat in test_scopevraag.py.
    """
    # agent/__init__ exporteert run(), dat het module-attribuut agent.run overschaduwt.
    run_module = importlib.import_module("agent.run")
    monkeypatch.setattr(run_module, "scopevraag", lambda vraag, settings, eerder=(): None)


TEST_SECRET = "test-secret-for-tests"


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Factory voor een TestClient op een verse app met een eigen SQLite-bestand (#840).

    `maak()` zet `DATABASE_PATH` op `tmp_path/test.db`. Met `users` staat login aan (`CHAT_USERS` en een vast
    `CHAT_SECRET`), zonder `users` zijn beide gewist en is iedereen `gast`. `env` zet extra variabelen. Daarna herlaadt
    hij de modules in `herlaad`, in die volgorde (ze lezen hun env bij het importeren), roept `init_db()` aan als
    `init_db` waar is, en herlaadt als laatste `server`.
    """
    from fastapi.testclient import TestClient

    def maak(
        *,
        users: str | None = None,
        env: dict[str, str] | None = None,
        herlaad: tuple[str, ...] = ("core.auth", "persistence.db"),
        init_db: bool = True,
    ) -> TestClient:
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
        if users is None:
            monkeypatch.delenv("CHAT_USERS", raising=False)
            monkeypatch.delenv("CHAT_SECRET", raising=False)
        else:
            monkeypatch.setenv("CHAT_USERS", users)
            monkeypatch.setenv("CHAT_SECRET", TEST_SECRET)
        for naam, waarde in (env or {}).items():
            monkeypatch.setenv(naam, waarde)
        for module in herlaad:
            importlib.reload(importlib.import_module(module))
        if init_db:
            from persistence import db

            db.init_db()
        import server

        importlib.reload(server)
        return TestClient(server.app)

    return maak
