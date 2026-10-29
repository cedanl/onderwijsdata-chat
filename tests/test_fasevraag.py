"""Instroom in het hoger onderwijs zonder fase krijgt een vaste kaart uit code (#743).

"Wat is de instroom in 2025 van de HvA?" telde de eerstejaars ho (DUO), en pas na doorvragen bleek dat de masters
ontbraken: die tellen daar niet als instroom. Nu vraagt code vooraf welke instroom, met wat elke optie wel en niet
kan. Alleen bij deze ene dubbelzinnigheid: buiten de vaste lijst vraagt de app niet extra.
"""

import pytest

from agent import scopevraag as module
from agent.scopevraag import fasevraag, scopevraag
from tools import instelling

_REGISTER = [
    {"naam": "Hogeschool van Amsterdam", "type": "hbo", "aliassen": ["HvA"]},
    {"naam": "Universiteit Leiden", "type": "wo", "aliassen": []},
    {"naam": "ROC van Amsterdam", "type": "mbo", "aliassen": ["ROCvA"]},
]


@pytest.fixture(autouse=True)
def register(monkeypatch):
    monkeypatch.setattr(module, "get_all", lambda: _REGISTER)
    monkeypatch.setattr(instelling, "get_all", lambda: _REGISTER)


@pytest.mark.parametrize(
    "vraag",
    [
        "Wat is de instroom in 2025 van de HvA t.o.v. omringende hogescholen?",
        "Hoe ontwikkelt de instroom bij de Universiteit Leiden zich?",
        "Wat is de instroom in het wo bij informatica?",
        "Hoeveel instromers had het hoger onderwijs in 2024?",
    ],
)
def test_instroom_in_het_ho_zonder_fase_vraagt_welke_instroom(vraag):
    kaart = scopevraag(vraag)

    assert kaart is not None and kaart.slot == "fase"
    assert kaart.vraag == "Welke instroom bedoel je?"
    eerste, tweede = kaart.opties
    assert eerste["aanbevolen"] is True and "zonder masters" in eerste["label"]
    assert "85422NED" in tweede["label"] and "landelijk" in tweede["label"]
    assert all(optie.get("beschrijving") for optie in kaart.opties)


@pytest.mark.parametrize(
    "vraag",
    [
        "Wat is de instroom in de bachelor bij de HvA?",
        "Hoeveel eerstejaars had de HvA in 2025?",
        "Wat is de instroom in masteropleidingen in het wo?",
        "Hoe is de trend van instroom in B Informatica en B Computer Science?",
        "Wat is de instroom bij ROC van Amsterdam?",
        "Wat is de instroom in het mbo?",
        "Hoeveel studenten heeft de HvA?",
        "Wat is de instroom?",
    ],
)
def test_met_een_fase_buiten_het_ho_of_zonder_instroom_geen_kaart(vraag):
    assert fasevraag(vraag) is None


def test_een_losse_letter_is_geen_opleidingsnaam():
    assert fasevraag("Wat is de instroom van de HvA, b maar dan per jaar?") is not None


def test_dezelfde_vraag_geeft_dezelfde_kaart_en_de_opties_zijn_kopieen():
    vraag = "Wat is de instroom van de HvA?"
    eerste, tweede = fasevraag(vraag), fasevraag(vraag)
    assert eerste == tweede
    assert eerste is not None and tweede is not None
    eerste.opties[0]["label"] = "anders"
    assert tweede.opties[0]["label"] != "anders"
