"""noemt_ho: gaat een vraag aantoonbaar over hoger onderwijs? (#556, epic #554)."""

import ast
from pathlib import Path

import pytest

from tools.ho_markers import noemt_ho

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
        "leerlingen (vwo) per regio",
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
    ],
)
def test_noemt_ho_negeert_niet_ho_vraag(vraag):
    assert noemt_ho(vraag) is False


def test_lege_vraag_is_geen_ho():
    assert noemt_ho("") is False


def test_module_kent_alleen_strings():
    """Geen import van de catalogus of data: de module moet los te importeren zijn (geen cyclus)."""
    boom = ast.parse(_MODULE.read_text(encoding="utf-8"))
    modules = set()
    for knoop in ast.walk(boom):
        if isinstance(knoop, ast.Import):
            modules.update(alias.name for alias in knoop.names)
        elif isinstance(knoop, ast.ImportFrom):
            modules.add(knoop.module or "")
            modules.update(alias.name for alias in knoop.names)
    assert modules <= {"re"}
