"""Eén getalnotatie in tekst, tabel en grafiek: 3303 in de tekst wordt 3.303, zoals in de grafiek (CH-11r, #445)."""

import asyncio
import importlib
import json

import pytest

from agent.getalnotatie import nl_notatie
from agent.grounding import getallen_met_positie, unverified
from agent.stream import StreamResult

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")


@pytest.mark.parametrize(
    ("tekst", "verwacht"),
    [
        ("Er waren 3303 studenten.", "Er waren 3.303 studenten."),
        ("Landelijk 1234567 inschrijvingen.", "Landelijk 1.234.567 inschrijvingen."),
        ("Een daling van -8700.", "Een daling van -8.700."),
        ("Gemiddeld 1234,5 per jaar.", "Gemiddeld 1.234,5 per jaar."),
        ("Van 33030 naar 32910, 120 minder.", "Van 33.030 naar 32.910, 120 minder."),
        ("**3303** eerstejaars", "**3.303** eerstejaars"),
        ("Tussen 1200-1500 per opleiding.", "Tussen 1.200-1.500 per opleiding."),
        # gpt-oss schrijft de duizendtallen met een spatie (#236); de grondingscontrole leest dat als één getal.
        ("Er waren 4 287 eerstejaars.", "Er waren 4.287 eerstejaars."),
        ("Er waren 4\u00a0287 eerstejaars.", "Er waren 4.287 eerstejaars."),
    ],
)
def test_duizendtallen_krijgen_een_punt_in_de_tekst(tekst, verwacht):
    assert nl_notatie(tekst) == verwacht


@pytest.mark.parametrize(
    "tekst",
    [
        "Er waren 3.303 studenten.",
        "Een stijging van 2.5 en 2,5 procent.",
        "Gemiddeld 1.234,5 per jaar.",
        "Dat is 12,5% van 999 studenten.",
        # Jaartallen en schooljaren.
        "In 2023 en in 2023/24, ook 2023/2024 en 2019-2023.",
        "Studiejaar 2023-24 en peiljaar 1999.",
        # Codes: dataset-id's, perioden, codes met een voorloopnul.
        "Bron: CBS 85423NED, periode 2024SJ00, code T001228, tabel 03753.",
        "CROHO 34479, crebo-code 25180, opleidingscode: 56965, BRIN 30RD.",
        "De opleidingscodes 34479, 34480 en 34481.",
        "Postcode 3584 CS in Utrecht.",
        # Engelse decimale punt: dubbelzinnig, dus ongemoeid.
        "Een gemiddelde van 1234.5 punten.",
        "Key duo:p01hoinges:1234 en cbs:85423NED:0.",
    ],
)
def test_jaren_codes_en_al_genoteerde_getallen_blijven_staan(tekst):
    assert nl_notatie(tekst) == tekst


def test_codeblok_inline_code_en_links_blijven_staan():
    tekst = (
        "Zie `filter AANTAL > 3303` en [de tabel](https://opendata.cbs.nl/statline/85423NED/12345).\n"
        "```python\ndf[df.AANTAL > 12345]\n```\n"
        "Daarna 12345 studenten op https://duo.nl/open_onderwijsdata/12345."
    )
    verwacht = tekst.replace("Daarna 12345", "Daarna 12.345")
    assert nl_notatie(tekst) == verwacht


def test_tabelcellen_krijgen_de_notatie_behalve_codekolommen():
    tekst = (
        "| Opleiding | CROHO | Jaar | Aantal |\n"
        "|---|---:|---|---:|\n"
        "| Rechten | 50800 | 2023 | 33030 |\n"
        "| Geneeskunde | 56551 | 2024 | 3303 |\n"
        "\n"
        "Samen 36333 studenten."
    )
    assert nl_notatie(tekst) == (
        "| Opleiding | CROHO | Jaar | Aantal |\n"
        "|---|---:|---|---:|\n"
        "| Rechten | 50800 | 2023 | 33.030 |\n"
        "| Geneeskunde | 56551 | 2024 | 3.303 |\n"
        "\n"
        "Samen 36.333 studenten."
    )


def test_tabel_zonder_buitenste_pijpen():
    tekst = "Instelling | BRIN-nummer | Aantal\n--- | --- | ---\nHU | 25DW | 38124\nUU | 21PD | 39021"
    assert nl_notatie(tekst) == (
        "Instelling | BRIN-nummer | Aantal\n--- | --- | ---\nHU | 25DW | 38.124\nUU | 21PD | 39.021"
    )


def test_codekolom_geldt_alleen_binnen_haar_tabel():
    tekst = "| Code | Aantal |\n|---|---|\n| 34479 | 4210 |\n\n| Instelling | Aantal |\n|---|---|\n| 34479 | 4210 |"
    assert nl_notatie(tekst) == (
        "| Code | Aantal |\n|---|---|\n| 34479 | 4.210 |\n\n| Instelling | Aantal |\n|---|---|\n| 34.479 | 4.210 |"
    )


_DATA = json.dumps({"rijen": [{"Perioden": "2024SJ00", "N": 378490}, {"Perioden": "2025SJ00", "N": 3303}]})


@pytest.mark.parametrize(
    "tekst",
    [
        "In 2024/'25 waren er 378490 studenten, daarna 3303.",
        "Het aantal daalde van 336800 naar 331200.",
        "| Jaar | Aantal |\n|---|---|\n| 2024 | 378490 |\n| 2025 | 9999 |",
        "Gemiddeld 1234,5 per jaar, 12,5% minder, code 85423NED.",
    ],
)
def test_grondingscontrole_en_citaties_lezen_dezelfde_getallen(tekst):
    """De controle draaide op de modeltekst; na de notatie moet ze hetzelfde vinden (#445, criterium 4)."""
    genormaliseerd = nl_notatie(tekst)
    voor = [_cijfers(n) for n in unverified(tekst, [_DATA])]
    na = [_cijfers(n) for n in unverified(genormaliseerd, [_DATA])]
    assert voor == na
    assert [c for _, c, _ in getallen_met_positie(tekst)] == [c for _, c, _ in getallen_met_positie(genormaliseerd)]


def _cijfers(getal: str) -> str:
    return getal.replace(".", "").replace(" ", "")


def test_het_antwoord_in_de_chat_krijgt_de_notatie(monkeypatch):
    """Het eindantwoord gebruikt dezelfde notatie als de grafiek."""

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return StreamResult(text="Het waren er 3303, in 2023.", tool_calls=[], finish_reason="stop")

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    # Een vervolgvraag: het getal komt uit het eerdere antwoord, dus de controle laat het door.
    gesprek = [
        {"role": "user", "content": "Hoeveel eerstejaars had de HU?"},
        {"role": "assistant", "content": "De HU had 3.303 eerstejaars in 2023."},
        {"role": "user", "content": "Hoeveel waren het ook alweer?"},
    ]
    asyncio.run(run_module.run(gesprek, {}, emit, asyncio.Event(), model="openai/gpt-4o"))
    einde = next(e for e in events if e["type"] == "message_end")
    assert einde["content"] == "Het waren er 3.303, in 2023."
    assert "controle" not in einde
