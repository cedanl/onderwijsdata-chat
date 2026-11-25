"""De richting die een vraag aanneemt, getoetst tegen de reeks van de beurt (#1255)."""

import asyncio
import importlib
import json

import pandas as pd
import pytest

from agent.binding import verkeerd_gebonden
from agent.controles import maak_getalcontrole
from agent.loop import LoopResult
from agent.premisse import (
    BEVESTIGD,
    NIET_TE_TOETSEN,
    TEGENGESPROKEN,
    met_premissezin,
    premisse,
    premisse_instructie,
    premissezin,
    reeks_uit_stappen,
)
from tools import store

STIJGEND = {2019: 27135, 2020: 27500, 2021: 28000, 2022: 28355}
DALEND = {2019: 28355, 2020: 28000, 2021: 27500, 2022: 27135}
# Eerst omlaag, dan omhoog: het bereik in de vraag beslist.
DAL = {2019: 30000, 2020: 28000, 2021: 27000, 2022: 29000}


@pytest.mark.parametrize(
    ("vraag", "reeks", "uitkomst"),
    [
        ("Waarom is het aantal studenten gedaald?", STIJGEND, TEGENGESPROKEN),
        ("Waarom is het aantal studenten gedaald?", DALEND, BEVESTIGD),
        ("Waarom daalt het aantal eerstejaars sinds 2020?", STIJGEND, TEGENGESPROKEN),
        ("Hoe verklaar je de stijging van het aantal studenten tussen 2019 en 2021?", DALEND, TEGENGESPROKEN),
        ("Waarom is de instroom afgenomen van 2019/20 tot 2022/23?", DALEND, BEVESTIGD),
        ("Waarom is het aantal ingeschrevenen gekrompen?", STIJGEND, TEGENGESPROKEN),
        ("Wat verklaart de groei van het aantal studenten?", STIJGEND, BEVESTIGD),
        ("Wat verklaart de groei van het aantal studenten?", DALEND, TEGENGESPROKEN),
        ("Waardoor is de instroom toegenomen?", DALEND, TEGENGESPROKEN),
        ("Waarom daalde het aantal studenten tussen 2019 en 2021?", DAL, BEVESTIGD),
        ("Waarom daalde het aantal studenten tussen 2021 en 2022?", DAL, TEGENGESPROKEN),
        ("Waarom daalde het aantal studenten in de laatste 1 jaar?", DAL, TEGENGESPROKEN),
        # Geen eenduidige aanname: stil.
        ("Hoeveel studenten waren er in 2022?", STIJGEND, NIET_TE_TOETSEN),
        ("Is het aantal studenten gedaald?", STIJGEND, NIET_TE_TOETSEN),
        ("Is het aantal gedaald of gestegen?", STIJGEND, NIET_TE_TOETSEN),
        ("Waarom is het aantal niet gedaald?", STIJGEND, NIET_TE_TOETSEN),
        ("Waarom is het aandeel vrouwen gedaald?", STIJGEND, NIET_TE_TOETSEN),
        ("Waarom daalde het percentage uitvallers?", STIJGEND, NIET_TE_TOETSEN),
        # Een periode die de reeks niet heeft, of één jaar zonder "sinds".
        ("Waarom daalde het aantal tussen 2015 en 2016?", STIJGEND, NIET_TE_TOETSEN),
        ("Waarom daalde het aantal in 2021?", STIJGEND, NIET_TE_TOETSEN),
    ],
)
def test_premisse(vraag, reeks, uitkomst):
    assert premisse(vraag, reeks) == uitkomst


def test_verschil_nul_is_dalen_noch_stijgen():
    assert premisse("Waarom is het aantal gedaald?", {2019: 500, 2022: 500}) == NIET_TE_TOETSEN
    assert premisse("Waarom is het aantal gestegen?", {2019: 500, 2022: 500}) == NIET_TE_TOETSEN


def test_reeks_als_paren_en_als_schooljaarlabels():
    assert premisse("Waarom gedaald?", [("2021/22", 100), ("2023/24", 120)]) == TEGENGESPROKEN
    assert premisse("Waarom gedaald?", [("2021SJ00", 100), ("2023SJ00", 90)]) == BEVESTIGD
    assert premisse("Waarom gedaald?", [("2021", 100)]) == NIET_TE_TOETSEN  # één punt


def test_de_beurtinstructie_alleen_bij_een_aangenomen_richting():
    assert "uit van een daling" in premisse_instructie("Waarom is het aantal mbo-studenten gedaald?")
    assert "uit van een stijging" in premisse_instructie("Wat verklaart de groei van de instroom?")
    assert premisse_instructie("Hoeveel mbo-studenten zijn er?") == ""


def test_de_beurtcontext_van_run_noemt_de_richting():
    from agent.run import _beurtcontext

    assert "Richting in de vraag" in _beurtcontext("Waarom is het aantal studenten gedaald?", {}, False)
    assert "Richting in de vraag" not in _beurtcontext("Hoeveel studenten zijn er?", {}, False)


# --- de vaste zin, op een get_maat-resultaat ---

KEY = "duo:p01hoinges:3:premisse"


@pytest.fixture
def maat() -> str:
    """Een get_maat-resultaat voor de Hogeschool Utrecht, met de key in de store zoals get_maat hem achterlaat."""
    rijen = [
        {"STUDIEJAAR": 2021, "AANTAL_INGESCHREVENEN": 26370},
        {"STUDIEJAAR": 2022, "AANTAL_INGESCHREVENEN": 27135},
        {"STUDIEJAAR": 2023, "AANTAL_INGESCHREVENEN": 27441},
        {"STUDIEJAAR": 2024, "AANTAL_INGESCHREVENEN": 28355},
    ]
    store.put(
        KEY,
        pd.DataFrame([{**r, "INSTELLINGSCODE_ACTUEEL": "25DW"} for r in rijen]),
        store.KeyMeta(
            bron="duo",
            dataset="p01hoinges",
            resource=3,
            periodekolom="STUDIEJAAR",
            schooljaren=(2021, 2022, 2023, 2024),
            instellingskolom="INSTELLINGSCODE_ACTUEEL",
            instellingen=("25DW",),
        ),
    )
    return json.dumps(
        {
            "data_key": KEY,
            "maat": "personen_ho",
            "instelling": "25DW",
            "periodekolom": "STUDIEJAAR",
            "waardekolom": "AANTAL_INGESCHREVENEN",
            "rijen": rijen,
        }
    )


ZIN = (
    "De vraag gaat uit van een daling, maar het aantal ingeschrevenen steeg van 26.370 naar 28.355 (2021/22 → 2024/25)."
)


def test_de_vaste_zin_bij_een_tegengesproken_richting(maat):
    reeks = reeks_uit_stappen([("get_maat", maat)])
    assert reeks is not None
    assert premissezin("Waarom is het aantal studenten bij de Hogeschool Utrecht gedaald?", reeks) == ZIN


def test_de_getallen_van_de_zin_halen_de_getalcontrole_en_de_binding(maat):
    assert maak_getalcontrole([], [])(ZIN, [maat]) == []
    assert verkeerd_gebonden(ZIN, [maat]) == []


def test_het_antwoord_opent_met_de_zin(maat):
    tekst = met_premissezin(
        "De Hogeschool Utrecht telt 28.355 studenten.",
        "Waarom is het aantal studenten bij de Hogeschool Utrecht gedaald?",
        [("get_maat", maat)],
    )
    assert tekst == f"{ZIN}\n\nDe Hogeschool Utrecht telt 28.355 studenten."


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel studenten heeft de Hogeschool Utrecht?",  # niet te toetsen: geen richting
        "Waarom is het aantal studenten bij de Hogeschool Utrecht gestegen?",  # bevestigd
        "Waarom daalde het aandeel voltijd bij de Hogeschool Utrecht?",  # relatief
    ],
)
def test_zonder_tegenspraak_blijft_het_antwoord_gelijk(maat, vraag):
    tekst = "De Hogeschool Utrecht telt 28.355 studenten."
    assert met_premissezin(tekst, vraag, [("get_maat", maat)]) == tekst


def test_een_deelantwoord_houdt_zijn_melding_bovenaan(maat):
    from agent.budget import DEELANTWOORD
    from agent.run import _met_premisse

    tekst = _met_premisse(f"{DEELANTWOORD}\n\nTekst.", "Waarom is het aantal gedaald?", [("get_maat", maat)])
    assert tekst == f"{DEELANTWOORD}\n\n{ZIN}\n\nTekst."


def _beurt(monkeypatch, vraag: str, maat: str) -> dict:
    """Eén beurt door run(), met een nagebootste lus die get_maat aanriep: het message_end-bericht."""
    run_module = importlib.import_module("agent.run")

    async def nep_lus(*args, **kwargs):
        return LoopResult(
            text="De Hogeschool Utrecht telt 28.355 studenten.",
            finish_reason="stop",
            steps=[("get_maat", maat)],
            tool_calls=[{"name": "get_maat", "arguments": "{}"}],
        )

    monkeypatch.setattr(run_module, "tool_loop", nep_lus)
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    asyncio.run(run_module.run([{"role": "user", "content": vraag}], {}, emit, asyncio.Event(), model="openai/gpt-4o"))
    return next(e for e in events if e["type"] == "message_end")


@pytest.mark.usefixtures("zonder_scopekaart")
def test_run_opent_het_antwoord_met_de_zin(maat, monkeypatch):
    """De bedrading in run(), niet alleen de hulpfunctie: na de lus opent het antwoord met de vaste zin (#1255)."""
    einde = _beurt(monkeypatch, "Waarom is het aantal studenten bij de Hogeschool Utrecht gedaald?", maat)
    assert einde["content"].startswith(f"{ZIN}\n\n")
    assert "De Hogeschool Utrecht telt 28.355 studenten." in einde["content"]
    assert "controle" not in einde


@pytest.mark.usefixtures("zonder_scopekaart")
def test_run_zonder_tegenspraak_opent_niet_met_de_zin(maat, monkeypatch):
    einde = _beurt(monkeypatch, "Waarom is het aantal studenten bij de Hogeschool Utrecht gestegen?", maat)
    assert "De vraag gaat uit van" not in einde["content"]
    assert "De Hogeschool Utrecht telt 28.355 studenten." in einde["content"]


def test_twee_reeksen_die_elkaar_tegenspreken_zijn_niet_te_toetsen(maat):
    ander = json.loads(maat)
    ander["rijen"] = [
        {"STUDIEJAAR": 2021, "AANTAL_INGESCHREVENEN": 9000},
        {"STUDIEJAAR": 2024, "AANTAL_INGESCHREVENEN": 100},
    ]
    assert reeks_uit_stappen([("get_maat", maat), ("get_maat", json.dumps(ander))]) is None


def test_een_query_data_tabel_met_een_reeks(maat):
    """Een tabel van query_data (één rij per jaar, één meetkolom) is ook een reeks; met een instelling per rij niet."""
    tabel = {
        "data_key": KEY,
        "rijen": [
            {"STUDIEJAAR": 2021, "STUDIEJAAR_LABEL": "2021/2022", "AANTAL_INGESCHREVENEN": 26370},
            {"STUDIEJAAR": 2024, "STUDIEJAAR_LABEL": "2024/2025", "AANTAL_INGESCHREVENEN": 28355},
        ],
    }
    reeks = reeks_uit_stappen([("query_data", json.dumps(tabel))])
    assert reeks is not None and [p.waarde for p in reeks.punten] == [26370, 28355]
    tabel["rijen"][1]["INSTELLINGSNAAM"] = "Fontys"
    tabel["rijen"][0]["INSTELLINGSNAAM"] = "HU"
    assert reeks_uit_stappen([("query_data", json.dumps(tabel))]) is None
