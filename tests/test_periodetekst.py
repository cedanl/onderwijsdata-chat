"""Een CBS-periodecode in de lopende tekst van het antwoord wordt het leesbare jaar (#989)."""

import importlib
import time

import pytest

from agent.loop import LoopResult
from agent.periodetekst import periodecode_als_label

run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie


@pytest.mark.parametrize(
    ("tekst", "verwacht"),
    [
        (
            "(CBS, 85423NED, Perioden: 2023SJ00, status definitief)",
            "(CBS, 85423NED, Perioden: 2023/24, status definitief)",
        ),
        ("Perioden: 2023JJ00", "Perioden: 2023"),
        ("In 2099SJ00 en 1999SJ00.", "In 2099/00 en 1999/00."),
        ("Van 2019SJ00-2023SJ00 steeg het aantal.", "Van 2019/20-2023/24 steeg het aantal."),
        ("**2023SJ00**: 341.720", "**2023/24**: 341.720"),
        (
            "| Perioden | Aantal |\n|---|---:|\n| 2023SJ00 | 341.720 |",
            "| Perioden | Aantal |\n|---|---:|\n| 2023/24 | 341.720 |",
        ),
    ],
    ids=["P03-zin", "kalenderjaar", "eeuwgrens", "bereik", "vet", "tabelrij"],
)
def test_periodecode_wordt_het_label(tekst, verwacht):
    assert periodecode_als_label(tekst) == verwacht


@pytest.mark.parametrize(
    "tekst",
    [
        "Perioden: 2023KW01",
        "Perioden: 2023MM01",
        "Perioden: 2023SJ01",
        "Code 12023SJ00 en 2023SJ00X.",
        "Tabel 85423NED.",
        "Perioden_2023SJ00",
    ],
)
def test_andere_codes_blijven_staan(tekst):
    assert periodecode_als_label(tekst) == tekst


@pytest.mark.parametrize(
    "tekst",
    [
        "```\nPerioden = 2023SJ00\n```",
        "~~~python\nfilter = \"Perioden eq '2023SJ00'\"\n~~~",
        "Filter op `Perioden eq '2023SJ00'`.",
        "Filter op ``2023SJ00``.",
        "Zie [de tabel](https://opendata.cbs.nl/?Perioden=2023SJ00).",
        "Zie https://opendata.cbs.nl/?Perioden=2023SJ00 voor meer.",
        '<span data-periode="2023SJ00">',
    ],
    ids=["codeblok", "tildeblok", "inline code", "dubbele backticks", "linkdoel", "url", "html"],
)
def test_code_links_en_html_blijven_letterlijk(tekst):
    assert periodecode_als_label(tekst) == tekst


def test_alleen_de_lopende_tekst_rond_een_codeblok_gaat_om():
    tekst = "In 2023SJ00:\n```\n2023SJ00\n```\nNa 2023SJ00."
    assert periodecode_als_label(tekst) == "In 2023/24:\n```\n2023SJ00\n```\nNa 2023/24."


def test_lange_invoer_blijft_snel():
    """Het draait synchroon op het eindantwoord: traag zoeken bevriest elke sessie op de worker."""
    tekst = "2023SJ0" * 50_000 + "1" * 50_000
    start = time.perf_counter()
    periodecode_als_label(tekst)
    assert time.perf_counter() - start < 0.5


# --- in het eindantwoord (_antwoordtekst) ---

_TELLING = "**Telling**\n- CBS: selectie Perioden 2023SJ00"


def _antwoordtekst(antwoord: str) -> str:
    return run_module._antwoordtekst(LoopResult(text=antwoord, finish_reason="stop"), antwoord, [], [])


@pytest.fixture
def telling(monkeypatch):
    """Een Telling-blok met een periodecode, zoals de app het onder het antwoord zet."""
    monkeypatch.setattr("agent.telling.telling_blok", lambda tool_results, tekst="": _TELLING)


def test_antwoord_krijgt_het_label_en_bronnen_en_telling_blijven_letterlijk(telling):
    antwoord = (
        "Er waren 341720 ingeschrevenen (CBS, 85423NED, Perioden: 2023SJ00).\n\n"
        "**Bronnen**\n- CBS 85423NED, Perioden 2023SJ00"
    )
    assert _antwoordtekst(antwoord) == (
        "Er waren 341.720 ingeschrevenen (CBS, 85423NED, Perioden: 2023/24).\n\n"
        f"**Bronnen**\n- CBS 85423NED, Perioden 2023SJ00\n\n{_TELLING}"
    )


def test_engels_antwoord_krijgt_ook_het_label(telling):
    antwoord = (
        "There were 341720 students enrolled in the period 2023SJ00 and the year 2022JJ00.\n\n"
        "**Bronnen**\n- CBS 85423NED, Perioden 2023SJ00"
    )
    assert _antwoordtekst(antwoord) == (
        "There were 341720 students enrolled in the period 2023/24 and the year 2022.\n\n"
        f"**Bronnen**\n- CBS 85423NED, Perioden 2023SJ00\n\n{_TELLING}"
    )
