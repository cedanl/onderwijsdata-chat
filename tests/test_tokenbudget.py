"""Een dag- en maandbudget aan tokens per gebruiker (#678, audit S24/F-08).

Het tokengebruik per run stond al in het log (`TOKENS`-regels); nu telt het ook mee in de database, per gebruiker en
per dag, gewogen naar wat het kost. Boven het budget start er geen modelrun meer, met een melding voor de gebruiker.
Faalt de database, dan gaat het chatten door: liever geen budget dan geen chat.
"""

import asyncio
import datetime as dt
import importlib

import pytest

from agent.stream import Tokens


@pytest.fixture
def budget(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from persistence import db

    importlib.reload(db)
    db.init_db()
    from core import tokenbudget

    monkeypatch.setattr(tokenbudget, "TOKENBUDGET_DAG", 100_000)
    monkeypatch.setattr(tokenbudget, "TOKENBUDGET_MAAND", 300_000)
    return tokenbudget


# ── De weging ─────────────────────────────────────────────────────────────────────────────────────────────────────


def test_de_weging_volgt_de_tariefverhouding():
    """Nieuwe invoer x1, uit de cache gelezen x0,1, cache geschreven x1,25, uitvoer x5; `invoer` bevat de cache al."""
    from core.tokenbudget import eenheden

    assert eenheden(Tokens(invoer=1_000)) == 1_000
    assert eenheden(Tokens(invoer=10_000, cache_gelezen=10_000)) == 1_000
    assert eenheden(Tokens(invoer=1_000, cache_geschreven=1_000)) == 1_250
    assert eenheden(Tokens(uitvoer=1_000)) == 5_000
    # Een typische vraag na #1027: 71k invoer waarvan 69k uit de cache, 2k uitvoer.
    assert eenheden(Tokens(invoer=71_000, uitvoer=2_000, cache_gelezen=69_000)) == 2_000 + 6_900 + 10_000


def test_een_cachegetal_groter_dan_de_invoer_geeft_geen_negatieve_nieuwe_invoer():
    from core.tokenbudget import eenheden

    assert eenheden(Tokens(invoer=100, cache_gelezen=500)) == 50


# ── Boeken en tellen ──────────────────────────────────────────────────────────────────────────────────────────────


def test_een_run_telt_mee_voor_de_gebruiker_van_de_verbinding(budget):
    budget.zet_gebruiker("anna@hu.nl")
    budget.boek(Tokens(invoer=40_000))
    budget.boek(Tokens(invoer=30_000))
    assert budget.gebruik("anna@hu.nl") == (70_000, 70_000)
    assert budget.gebruik("bob@hu.nl") == (0, 0)


def test_boeken_in_een_thread_ziet_de_gebruiker_van_de_taak(budget):
    """De loop boekt via asyncio.to_thread; de ContextVar van de verbinding gaat mee."""

    async def run():
        budget.zet_gebruiker("anna@hu.nl")
        await asyncio.to_thread(budget.boek, Tokens(invoer=5_000))

    asyncio.run(run())
    assert budget.gebruik("anna@hu.nl") == (5_000, 5_000)


def test_zonder_gebruiker_telt_er_niets(budget):
    budget.zet_gebruiker(None)
    budget.boek(Tokens(invoer=5_000))
    assert budget.gebruik("anna@hu.nl") == (0, 0)


def test_de_gebruikersnaam_staat_niet_leesbaar_in_de_database(budget):
    from persistence import db

    budget.zet_gebruiker("anna@hu.nl")
    budget.boek(Tokens(invoer=1_000))
    with db._connection() as conn:
        rijen = db._execute(conn, "SELECT sleutel FROM tokengebruik", ()).fetchall()
    assert rijen and all("anna" not in r["sleutel"] for r in rijen)


def test_de_maand_telt_de_dagen_van_deze_maand(budget, monkeypatch):
    budget.zet_gebruiker("anna@hu.nl")
    for dag, n in ((dt.date(2026, 10, 31), 50_000), (dt.date(2026, 11, 1), 20_000), (dt.date(2026, 11, 19), 30_000)):
        monkeypatch.setattr(budget, "_vandaag", lambda d=dag: d)
        budget.boek(Tokens(invoer=n))
    assert budget.gebruik("anna@hu.nl") == (30_000, 50_000), "oktober telt niet mee in november"


# ── De toets vóór een run ─────────────────────────────────────────────────────────────────────────────────────────


def test_onder_het_budget_mag_het(budget):
    budget.zet_gebruiker("anna@hu.nl")
    budget.boek(Tokens(invoer=99_000))
    assert budget.over_budget("anna@hu.nl") is None


def test_boven_het_dagbudget_een_melding_voor_morgen(budget):
    budget.zet_gebruiker("anna@hu.nl")
    budget.boek(Tokens(invoer=100_000))
    melding = budget.over_budget("anna@hu.nl")
    assert melding and "vandaag" in melding.lower() and "morgen" in melding.lower()


def test_boven_het_maandbudget_een_melding_voor_volgende_maand(budget, monkeypatch):
    budget.zet_gebruiker("anna@hu.nl")
    for dag in (dt.date(2026, 11, 1), dt.date(2026, 11, 2), dt.date(2026, 11, 3)):
        monkeypatch.setattr(budget, "_vandaag", lambda d=dag: d)
        budget.boek(Tokens(invoer=100_000))
    monkeypatch.setattr(budget, "_vandaag", lambda: dt.date(2026, 11, 4))
    melding = budget.over_budget("anna@hu.nl")
    assert melding and "deze maand" in melding and "1 december" in melding


def test_een_budget_van_nul_staat_uit(budget, monkeypatch):
    monkeypatch.setattr(budget, "TOKENBUDGET_DAG", 0)
    monkeypatch.setattr(budget, "TOKENBUDGET_MAAND", 0)
    budget.zet_gebruiker("anna@hu.nl")
    budget.boek(Tokens(invoer=10_000_000))
    assert budget.over_budget("anna@hu.nl") is None


def test_gast_heeft_geen_budget(budget):
    assert budget.over_budget(None) is None
    assert budget.over_budget("gast") is None


def test_een_databasefout_laat_de_chat_door(budget, monkeypatch, caplog):
    from persistence import db

    def kapot(*a, **k):
        raise RuntimeError("database weg")

    monkeypatch.setattr(db, "tokengebruik_stand", kapot)
    monkeypatch.setattr(db, "tokengebruik_boek", kapot)
    budget.zet_gebruiker("anna@hu.nl")
    budget.boek(Tokens(invoer=1_000))  # geen uitzondering
    with caplog.at_level("WARNING"):
        assert budget.over_budget("anna@hu.nl") is None
    assert "database" in caplog.text.lower()


def test_oude_dagen_worden_opgeruimd(budget, monkeypatch):
    from persistence import db

    budget.zet_gebruiker("anna@hu.nl")
    monkeypatch.setattr(budget, "_vandaag", lambda: dt.date.today() - dt.timedelta(days=70))
    budget.boek(Tokens(invoer=1_000))
    monkeypatch.setattr(budget, "_vandaag", dt.date.today)
    budget.boek(Tokens(invoer=2_000))
    with db._connection() as conn:
        db.purge_expired_revocations(conn)
        conn.commit()
        dagen = [r["dag"] for r in db._execute(conn, "SELECT dag FROM tokengebruik", ()).fetchall()]
    assert dagen == [dt.date.today().isoformat()]


# ── De chat weigert boven het budget, zonder modelaanroep ────────────────────────────────────────────────────────


def test_de_chat_weigert_een_vraag_boven_het_budget(budget, monkeypatch):
    import routes.chat as chat

    monkeypatch.setattr(chat._berichtlimiter, "probeer", lambda sleutel: None)
    budget.zet_gebruiker("anna@hu.nl")
    budget.boek(Tokens(invoer=100_000))
    gezien = []

    async def emit(bericht):
        gezien.append(bericht)

    assert asyncio.run(chat._binnen_limiet({"username": "anna@hu.nl"}, emit)) is False
    assert gezien and gezien[0]["type"] == "error" and "morgen" in gezien[0]["message"].lower()
    assert asyncio.run(chat._binnen_limiet({"username": "bob@hu.nl"}, emit)) is True
