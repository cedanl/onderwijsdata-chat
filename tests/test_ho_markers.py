"""noemt_ho: gaat een vraag aantoonbaar over hoger onderwijs? (#556, epic #554). ho_poort: op welke vraag (#597)."""

import ast
from pathlib import Path

import pytest

from tools.ho_markers import beurtvraag, ho_poort, noemt_ho

_MODULE = Path(__file__).resolve().parent.parent / "tools" / "ho_markers.py"


@pytest.mark.parametrize(
    "vraag",
    [
        "Welk deel van de vwo-geslaagden gaat naar wo?",
        "doorstroom havo naar hbo",
        "hoeveel eerstejaars op de universiteit komen van het vwo",
        "instroom in het hoger onderwijs per jaar",
        "instroom hoger  onderwijs",  # meerdere spaties
        "studenten per hogeschool",
        "welke hogescholen groeien?",
        "aantal studenten aan de Nederlandse universiteiten",
        "uitval in het ho",
        "HBO of WO",
        "Hanzehogeschool instroom",
        "aantal wo-masters",
        "hbo-opleidingen per sector",
        "wo, hbo en mbo naast elkaar",
        "leerlingen (wo) per regio",
        "Hoger Onderwijs in Groningen",
    ],
)
def test_noemt_ho_herkent_ho_vraag(vraag):
    assert noemt_ho(vraag) is True


@pytest.mark.parametrize(
    "vraag",
    [
        "",
        "welke mbo-instellingen krimpen het sterkst richting 2030?",
        "instroom mbo per instelling",
        "aantal studenten per regio",
        "woningen per gemeente",
        "hoeveel examenkandidaten in het vmbo",
        "hoger dan vorig jaar",
        "hoeveel leerlingen",
        "doorstroom",
        "instelling",
        "instroom",
        "studenten",
        "regio",
        "op woensdag",
        "hobby's van studenten",
        "whoa, wat een daling",
        # Havo en vwo zijn vo (#597): zonder een ho-woord blijft een vo-vraag buiten de poort (#355).
        "Hoeveel leerlingen zitten er op het vwo?",
        "slagingspercentage op havo en vwo",
        "Hoeveel havo-geslaagden zijn er per regio?",
        "leerlingen (vwo) per regio",
        "havo/vwo per provincie",
    ],
)
def test_noemt_ho_negeert_niet_ho_vraag(vraag):
    assert noemt_ho(vraag) is False


def test_lege_vraag_is_geen_ho():
    assert noemt_ho("") is False


# De poort kijkt naar de vraag van de gebruiker, niet naar de zoekterm van het model (#597).
def test_buiten_een_beurt_beslist_de_zoekterm():
    """MCP en evals kennen geen gebruikersvraag: daar blijft de zoekterm de toets."""
    assert ho_poort("instroom hbo") is True
    assert ho_poort("vwo leerlingen") is False


def test_het_model_opent_de_poort_niet_door_hbo_toe_te_voegen():
    with beurtvraag("Hoeveel leerlingen zitten er op het vwo?"):
        assert ho_poort("vwo leerlingen hbo") is False


def test_het_model_sluit_de_poort_niet_door_hbo_weg_te_laten():
    with beurtvraag("Hoeveel vwo-leerlingen stromen door naar het wo?"):
        assert ho_poort("doorstroom vwo") is True


def test_na_de_beurt_beslist_de_zoekterm_weer():
    with beurtvraag("doorstroom vwo naar wo"):
        pass
    assert ho_poort("vwo leerlingen") is False


def test_module_kent_alleen_strings():
    """Geen import van de catalogus of data: de module moet los te importeren zijn (geen cyclus).
    De standaardbibliotheek mag, voor de beurtvraag (#597)."""
    boom = ast.parse(_MODULE.read_text(encoding="utf-8"))
    modules = set()
    for knoop in ast.walk(boom):
        if isinstance(knoop, ast.Import):
            modules.update(alias.name for alias in knoop.names)
        elif isinstance(knoop, ast.ImportFrom):
            modules.add(knoop.module or "")
            modules.update(alias.name for alias in knoop.names)
    assert modules <= {"re", "contextlib", "contextvars", "collections.abc", "Generator", "ContextVar"}
