"""De taal van het antwoord is de taal van de vraag (besluit #326)."""

import asyncio
import importlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent.antwoordtaal import taal, taalinstructie, verkeerde_antwoordtaal
from agent.grounding import unverified
from agent.loop import LoopResult

run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie

_ENGELS_ANTWOORD = (
    "In 2023 there were 12,345 first-year students at the university. That is 3.2% more than the year "
    "before, and the share of women was 56.4%."
)
_NEDERLANDS_ANTWOORD = (
    "In 2023 waren er 12.345 eerstejaars aan de universiteit. Dat is 3,2% meer dan het jaar ervoor, "
    "en het aandeel vrouwen was 56,4%."
)


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel studenten heeft de Hogeschool Utrecht?",
        "Wat is de instroom in het hbo in 2023?",
        "Hoeveel eerstejaars had Avans Hogeschool in 2023?",
        "Geef een overzicht van het aantal mbo-studenten per niveau voor ROC Mondriaan.",
        _NEDERLANDS_ANTWOORD,
    ],
)
def test_nederlandse_tekst(vraag):
    assert taal(vraag) == "nl"


@pytest.mark.parametrize(
    "vraag",
    [
        "How many students does Utrecht University have?",
        "What is the intake in higher professional education in 2023?",
        # Audit 12: een Engelse vraag kreeg een Nederlands antwoord.
        "What is the ratio of men to women among first-year students at Avans Hogeschool, and what share are women?",
        "How many students does the Hogeschool van Amsterdam have?",
        _ENGELS_ANTWOORD,
    ],
)
def test_engelse_tekst(vraag):
    assert taal(vraag) == "en"


@pytest.mark.parametrize(
    "tekst",
    [
        "",
        "Avans Hogeschool",
        "HU 2023",
        "Naar geslacht",
        "Hoeveel students in the hbo?",
        "12.345",
        "How many at Hogeschool van Arnhem en Nijmegen?",
    ],
)
def test_kort_gemengd_of_alleen_namen_is_onzeker(tekst):
    assert taal(tekst) is None


def test_de_instructie_volgt_de_taal_van_de_vraag():
    engels = taalinstructie("How many students does Utrecht University have?")
    assert "in het Engels" in engels and "Answer in English" in engels
    assert "in het Nederlands" in taalinstructie("Hoeveel studenten heeft de Hogeschool Utrecht?")
    assert taalinstructie("Avans Hogeschool") == ""


def test_engelse_vraag_met_nederlands_antwoord_vraagt_een_engels_antwoord():
    [probleem] = verkeerde_antwoordtaal("How many first-year students were there in 2023?", _NEDERLANDS_ANTWOORD)
    assert "in het Engels" in probleem
    assert probleem.melding and not probleem.hard


def test_nederlandse_vraag_met_engels_antwoord_vraagt_een_nederlands_antwoord():
    [probleem] = verkeerde_antwoordtaal("Hoeveel eerstejaars waren er in 2023?", _ENGELS_ANTWOORD)
    assert "in het Nederlands" in probleem


@pytest.mark.parametrize(
    ("vraag", "antwoord"),
    [
        ("How many first-year students were there in 2023?", _ENGELS_ANTWOORD),
        ("Hoeveel eerstejaars waren er in 2023?", _NEDERLANDS_ANTWOORD),
        # Onzeker aan een van beide kanten: geen actie.
        ("Avans 2023", _NEDERLANDS_ANTWOORD),
        ("How many first-year students were there in 2023?", "12.345 (2023)"),
    ],
)
def test_zelfde_of_onzekere_taal_geeft_niets(vraag, antwoord):
    assert verkeerde_antwoordtaal(vraag, antwoord) == []


def test_nederlandse_bronnamen_in_een_engels_antwoord_maken_het_niet_nederlands():
    antwoord = (
        _ENGELS_ANTWOORD + "\n\nSources: CBS, Leerlingen en studenten; onderwijssoort, woonregio (85701NED), "
        "DUO, Ingeschrevenen in het hoger onderwijs, en de lijst van instellingen."
    )
    assert taal(antwoord) == "en"
    assert verkeerde_antwoordtaal("How many first-year students were there in 2023?", antwoord) == []


def _systeembericht(vraag: str) -> str:
    """De beurttekst van het systeembericht dat run() aan de toolloop geeft."""
    meegegeven = {}

    async def nep_loop(history, **kwargs):
        meegegeven.update(kwargs)
        return SimpleNamespace(aborted="tools")

    async def emit(_event):
        pass

    with (
        patch.object(run_module, "tool_loop", nep_loop),
        patch.object(run_module, "genoemde_bronnen", lambda v: "BRONNEN UIT DE VRAAG"),
    ):
        # Na een scopevraag: de kaart uit code komt niet meer, het model antwoordt.
        asyncio.run(run_module.run([{"role": "user", "content": vraag}], session={"clarify_rondes": 1}, emit=emit))
    return "\n".join(blok["text"] for blok in meegegeven["system"][0]["content"][1:])


def test_engelse_vraag_krijgt_de_instructie_engels_te_antwoorden():
    beurt = _systeembericht("How many first-year students were there at Avans Hogeschool in 2023?")
    assert "Answer in English" in beurt and "in het Engels" in beurt
    assert "BRONNEN UIT DE VRAAG" in beurt


def test_nederlandse_vraag_krijgt_de_instructie_nederlands_te_antwoorden():
    beurt = _systeembericht("Hoeveel eerstejaars had Avans Hogeschool in 2023?")
    assert "Schrijf het antwoord in het Nederlands" in beurt and "English" not in beurt
    assert "BRONNEN UIT DE VRAAG" in beurt


def _antwoordtekst(antwoord: str) -> str:
    return run_module._antwoordtekst(LoopResult(text=antwoord, finish_reason="stop"), antwoord, [], [])


def test_nederlands_antwoord_krijgt_de_nederlandse_notatie():
    antwoord = "Er waren 3303 eerstejaars, een aandeel van 56.4% en een ratio van 1.29."
    assert _antwoordtekst(antwoord) == "Er waren 3.303 eerstejaars, een aandeel van 56,4% en een ratio van 1,29."


def test_engels_antwoord_houdt_de_notatie_van_het_model():
    antwoord = "There were 3303 first-year students, a share of 56.4% and a ratio of 1.29 in 2023."
    assert _antwoordtekst(antwoord) == antwoord
    assert _antwoordtekst("There were 12,345 students and 1,234.5 on average.") == (
        "There were 12,345 students and 1,234.5 on average."
    )


def test_nederlands_antwoord_krijgt_de_je_vorm():
    antwoord = "Het getal dat u noemt, 3303, staat in de data. Jullie instelling had 56.4% vrouwen."
    assert _antwoordtekst(antwoord) == (
        "Het getal dat je noemt, 3.303, staat in de data. Je instelling had 56,4% vrouwen."
    )


def test_engels_antwoord_houdt_zijn_tekst():
    antwoord = "In the U.S. data there were 3303 first-year students, as you asked, in 2023."
    assert _antwoordtekst(antwoord) == antwoord


def test_grondingscontrole_slaagt_op_een_antwoord_met_u_vormen_ruw_en_na_de_omzetting():
    """Je-vorm en notatie veranderen geen getal: de controle vindt ruw en getoond hetzelfde (#536)."""
    data = [json.dumps({"rijen": [{"AANTAL": 3303, "AANDEEL_VROUW": 56.4}]})]
    antwoord = (
        "Het getal dat u noemt, 3303, staat in de data: uw instelling had 3.303 eerstejaars, "
        "van wie 56.4% vrouw. Wilt u de trend zien?"
    )
    getoond = _antwoordtekst(antwoord)

    assert getoond == (
        "Het getal dat je noemt, 3.303, staat in de data: je instelling had 3.303 eerstejaars, "
        "van wie 56,4% vrouw. Wil je de trend zien?"
    )
    assert unverified(antwoord, data) == []
    assert unverified(getoond, data) == []
