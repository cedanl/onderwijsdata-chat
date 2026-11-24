"""De dashboards warmen na een start op de achtergrond op (#1166): de eerste gebruiker wacht niet 10-23 s.

Geen netwerk: de laders en het register zijn nagebootst. Wachten gebeurt op een gebeurtenis, niet op de klok; de
time-outs zijn alleen een vangnet tegen hangen.
"""

import asyncio
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

import httpx
import pytest

import core.config
import server
from core import dashboard_opwarmen
from core.gelijktijdig import Druk, Runplaatsen
from routes import instellingen as routes_instellingen

REGISTER = [
    {"naam": "Aeres Hogeschool", "type": "hbo", "provincie": None},
    {"naam": "Avans Hogeschool", "type": "hbo", "provincie": "Noord-Brabant"},
    {"naam": "Erasmus Universiteit Rotterdam", "type": "wo", "provincie": "Zuid-Holland"},
    {"naam": "Albeda", "type": "mbo", "provincie": "Zuid-Holland"},
    {"naam": "Universiteit Utrecht", "type": "wo", "provincie": "Utrecht"},
]
GEHEIM = "Instelling Die Niet In Het Log Mag"
ROOT = Path(__file__).resolve().parent.parent

LADERS = (
    "load_dashboard_regio",
    "load_dashboard_rendement",
    "load_dashboard_financien",
    "load_dashboard_nationaal",
    "load_dashboard_arbeidsmarktmatch",
    "load_dashboard_personeel",
    "load_dashboard_opleidingen",
)


class Laders:
    """Nagebootste laders: per eindpunt de instellingen waarmee ze aangeroepen zijn."""

    def __init__(self, monkeypatch, register=REGISTER):
        self.aanroepen: list[tuple[str, str]] = []
        self.threads: set[str] = set()
        monkeypatch.setattr(dashboard_opwarmen, "get_all_instellingen", lambda: register)
        for naam in LADERS:
            monkeypatch.setattr(dashboard_opwarmen, naam, self._lader(naam.removeprefix("load_dashboard_")))

    def _lader(self, eindpunt):
        def laad(instelling):
            self.aanroepen.append((eindpunt, instelling))
            self.threads.add(threading.current_thread().name)
            return self.antwoord(eindpunt, instelling)

        laad.__name__ = f"load_dashboard_{eindpunt}"
        return laad

    def antwoord(self, eindpunt, instelling):
        return {"instelling": instelling, "gevonden": True}

    def eindpunten(self):
        return list(dict.fromkeys(e for e, _ in self.aanroepen))


@pytest.fixture
def alle_bronnen_aan(monkeypatch):
    from tools import beschikbaarheid

    for regel in ("financien", "wo_personeel", "studiekeuze"):
        monkeypatch.setattr(beschikbaarheid, regel, lambda: True)


def _draai(aan=True):
    async def loop():
        async with dashboard_opwarmen.opwarming(aan) as taak:
            if taak is not None:
                await asyncio.wait_for(asyncio.shield(taak), timeout=10)
            return taak

    return asyncio.run(loop())


# ── Welke instellingen en welke eindpunten ──────────────────────────────────


def test_per_soort_de_eerste_instelling_met_een_bekende_provincie():
    assert dashboard_opwarmen.kies_instellingen(REGISTER) == [
        "Avans Hogeschool",
        "Erasmus Universiteit Rotterdam",
        "Albeda",
    ]


def test_zonder_provincie_de_eerste_van_de_soort_en_een_ontbrekende_soort_valt_weg():
    register = [{"naam": "B", "type": "hbo", "provincie": None}, {"naam": "A", "type": "hbo"}]
    assert dashboard_opwarmen.kies_instellingen(register) == ["B"]
    assert dashboard_opwarmen.kies_instellingen([]) == []


def test_de_opwarming_roept_elke_lader_aan_voor_elke_gekozen_instelling(monkeypatch, alle_bronnen_aan):
    laders = Laders(monkeypatch)

    taak = _draai()

    assert taak is not None and taak.done() and taak.exception() is None
    assert laders.eindpunten()[:3] == ["regio", "rendement", "financien"]
    assert set(laders.eindpunten()) == {e.removeprefix("load_dashboard_") for e in LADERS}
    gekozen = {"Avans Hogeschool", "Erasmus Universiteit Rotterdam", "Albeda"}
    for eindpunt in ("regio", "rendement", "financien"):
        assert {i for e, i in laders.aanroepen if e == eindpunt} == gekozen
    # In de executor, niet op de event loop.
    assert threading.main_thread().name not in laders.threads


@pytest.mark.parametrize(
    ("regel", "eindpunt"),
    [("financien", "financien"), ("wo_personeel", "personeel"), ("studiekeuze", "opleidingen")],
)
def test_een_bron_die_hier_uit_staat_wordt_niet_opgewarmd(monkeypatch, alle_bronnen_aan, regel, eindpunt):
    from tools import beschikbaarheid

    monkeypatch.setattr(beschikbaarheid, regel, lambda: False)
    laders = Laders(monkeypatch)

    _draai()

    assert eindpunt not in laders.eindpunten()
    assert {"regio", "rendement"} <= set(laders.eindpunten())


# ── Aan of uit ───────────────────────────────────────────────────────────────


def test_uit_geeft_geen_taak_en_laadt_niets(monkeypatch):
    laders = Laders(monkeypatch)

    assert _draai(aan=False) is None
    assert laders.aanroepen == []


def test_de_schakelaar_leest_0_en_false_als_uit(monkeypatch):
    import importlib

    try:
        for waarde, verwacht in (("0", False), ("false", False), ("False", False), ("1", True), ("true", True)):
            monkeypatch.setenv("DASHBOARD_WARMUP", waarde)
            assert importlib.reload(core.config).DASHBOARD_WARMUP is verwacht, waarde
        monkeypatch.delenv("DASHBOARD_WARMUP")
        assert importlib.reload(core.config).DASHBOARD_WARMUP is True, "standaard aan"
    finally:
        monkeypatch.undo()
        importlib.reload(core.config)


# ── Fouten, log en afsluiten ─────────────────────────────────────────────────


def test_een_fout_in_een_lader_stopt_de_opwarming_niet_en_logt_zonder_instelling(monkeypatch, alle_bronnen_aan, caplog):
    laders = Laders(monkeypatch, register=[{"naam": GEHEIM, "type": "hbo", "provincie": "Utrecht"}])

    def antwoord(eindpunt, instelling):
        if eindpunt == "regio":
            raise RuntimeError(f"kapot voor {instelling}")
        return {"instelling": instelling, "gevonden": True}

    laders.antwoord = antwoord
    with caplog.at_level(logging.INFO, logger=dashboard_opwarmen.logger.name):
        taak = _draai()

    assert taak is not None and taak.exception() is None
    assert "rendement" in laders.eindpunten() and "opleidingen" in laders.eindpunten()
    waarschuwingen = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(waarschuwingen) == 1
    regel = waarschuwingen[0].getMessage()
    assert "eindpunt=regio" in regel and "RuntimeError" in regel and "fout_hash=" in regel
    klaar = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO and "opgewarmd" in r.getMessage()]
    assert len(klaar) == 1
    assert "duur=" in klaar[0] and "rendement" in klaar[0] and "mislukt=regio" in klaar[0]
    for record in caplog.records:
        if record.levelno >= logging.INFO:
            assert GEHEIM not in record.getMessage()
            assert "Utrecht" not in record.getMessage()


def test_een_register_dat_niet_laadt_stopt_de_app_niet(monkeypatch, caplog):
    def kapot():
        raise ConnectionError("DUO onbereikbaar")

    laders = Laders(monkeypatch)
    monkeypatch.setattr(dashboard_opwarmen, "get_all_instellingen", kapot)
    with caplog.at_level(logging.INFO, logger=dashboard_opwarmen.logger.name):
        taak = _draai()

    assert taak is not None and taak.exception() is None
    assert laders.aanroepen == []
    assert any("ConnectionError" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


def test_een_volle_wachtrij_slaat_het_eindpunt_over(monkeypatch, alle_bronnen_aan, caplog):
    laders = Laders(monkeypatch)

    class Vol:
        def plaats(self):
            raise Druk

    monkeypatch.setattr(routes_instellingen, "_dashboardplaatsen", Vol())
    with caplog.at_level(logging.WARNING, logger=dashboard_opwarmen.logger.name):
        taak = _draai()

    assert taak is not None and taak.exception() is None
    assert laders.aanroepen == []
    assert all("Druk" in r.getMessage() for r in caplog.records)


def test_de_opwarming_gebruikt_de_plaatsen_van_de_dashboards_en_laadt_na_elkaar(monkeypatch, alle_bronnen_aan):
    """Hooguit één lading tegelijk, en elke lading in een plaats van `_dashboardplaatsen` (MAX_DASHBOARD_LOADS)."""
    laders = Laders(monkeypatch)
    plaatsen = Runplaatsen(max_tegelijk=4, wacht_s=5)
    monkeypatch.setattr(routes_instellingen, "_dashboardplaatsen", plaatsen)
    bezet: list[int] = []

    def antwoord(eindpunt, instelling):
        bezet.append(4 - plaatsen._semafoor._value)  # bezette plaatsen tijdens deze lading
        return {}

    laders.antwoord = antwoord
    taak = _draai()

    assert taak is not None and taak.exception() is None
    assert len(bezet) == len(laders.aanroepen) > 0
    assert set(bezet) == {1}


def test_de_taak_wordt_bij_het_afsluiten_geannuleerd(monkeypatch):
    """Een lader die niet afkomt houdt het afsluiten niet op: de taak wordt geannuleerd en afgewacht."""
    begonnen = asyncio.Event()

    async def hangt(loader, instelling):
        begonnen.set()
        await asyncio.Event().wait()

    Laders(monkeypatch)
    monkeypatch.setattr(routes_instellingen, "_in_een_plaats", hangt)

    async def loop():
        async with dashboard_opwarmen.opwarming(True) as taak:
            assert taak is not None
            await asyncio.wait_for(begonnen.wait(), timeout=10)
            assert not taak.done()
        return taak

    taak = asyncio.run(asyncio.wait_for(loop(), timeout=10))
    assert taak.cancelled()


def test_de_module_laadt_zonder_routes_en_de_loginconfiguratie():
    """server.py importeert deze module. `routes` laadt `core.auth`, dat bij een login zonder CHAT_SECRET of een
    ongeldige sessieduur al bij het laden weigert: dan eindigde de start in een traceback in plaats van de ene melding
    van Config.validate (#1164, tests/test_logging_opstart.py). De module laadt `routes` dus pas in de taak."""
    basis = {k: v for k, v in os.environ.items() if k not in ("CHAT_SECRET", "OIDC_PROVIDER", "SESSION_TTL_HOURS")}
    code = "import sys, core.dashboard_opwarmen; print(sorted({'routes', 'core.auth'} & set(sys.modules)))"
    uitslag = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env={**basis, "CHAT_USERS": "admin:pw", "APP_ENV": "test"},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert uitslag.returncode == 0, uitslag.stderr
    assert uitslag.stdout.strip().splitlines()[-1] == "[]"


def test_server_laadt_de_opwarming_pas_na_de_configuratiecontrole(tmp_path):
    """server.py importeert een deel van core vóór de logging-setup en Config.validate; de opwarming trekt de
    dashboardbronnen (en pandas) mee en hoort, zoals routes, daarna. Een verkeerde configuratie stopt dus eerst."""
    basis = {k: v for k, v in os.environ.items() if k not in ("CHAT_SECRET", "OIDC_PROVIDER", "SESSION_TTL_HOURS")}
    code = (
        "import sys\ntry:\n    import server\nexcept SystemExit:\n    print('core.dashboard_opwarmen' in sys.modules)\n"
    )
    uitslag = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env={**basis, "CHAT_USERS": "admin:pw", "APP_ENV": "local", "DATABASE_PATH": str(tmp_path / "start.db")},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert "Configuration validation failed" in uitslag.stdout + uitslag.stderr
    assert uitslag.stdout.strip().splitlines()[-1] == "False"


# ── In de lifespan van de app ────────────────────────────────────────────────


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))


def _vlaggen(monkeypatch, dashboards, warmup):
    monkeypatch.setattr(core.config, "DASHBOARDS_ENABLED", dashboards)
    monkeypatch.setattr(core.config, "DASHBOARD_WARMUP", warmup)


@pytest.mark.parametrize(("dashboards", "warmup"), [(False, True), (True, False), (False, False)])
def test_de_lifespan_start_geen_opwarming_als_een_vlag_uit_staat(monkeypatch, database, dashboards, warmup):
    _vlaggen(monkeypatch, dashboards, warmup)
    gestart = []

    async def opwarmen():
        gestart.append(1)

    monkeypatch.setattr(dashboard_opwarmen, "_opwarmen", opwarmen)
    app = server.create_app(api_docs=False)

    async def loop():
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0)  # de taak zou nu al gestart zijn
            await asyncio.sleep(0)

    asyncio.run(loop())
    assert gestart == []


def test_health_en_ready_antwoorden_terwijl_de_opwarming_nog_loopt(monkeypatch, database, alle_bronnen_aan):
    """De opwarming start na on_startup() en houdt de start niet op: met een lader die blijft hangen antwoorden
    /health en /ready gewoon; bij het afsluiten wordt de taak geannuleerd."""
    _vlaggen(monkeypatch, True, True)
    laders = Laders(monkeypatch)
    begonnen, los = threading.Event(), threading.Event()
    volgorde = []

    def traag(eindpunt, instelling):
        begonnen.set()
        los.wait(timeout=10)
        return {}

    laders.antwoord = traag
    origineel = server.on_startup

    async def on_startup():
        await origineel()
        volgorde.append("on_startup")

    monkeypatch.setattr(server, "on_startup", on_startup)
    app = server.create_app(api_docs=False)

    async def loop():
        try:
            async with (
                app.router.lifespan_context(app),
                httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http,
            ):
                assert await asyncio.to_thread(begonnen.wait, 10), "de opwarming startte niet"
                volgorde.append("opwarming")
                health = await http.get("/health")
                ready = await http.get("/ready")
                assert not los.is_set()
                assert laders.aanroepen == [("regio", "Avans Hogeschool")]
                return health, ready
        finally:
            los.set()  # de thread van de executor afmaken, anders wacht het afsluiten van de loop erop

    health, ready = asyncio.run(loop())
    assert volgorde == ["on_startup", "opwarming"]
    assert health.status_code == 200
    assert ready.status_code in (200, 503) and "checks" in ready.json()
