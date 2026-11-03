"""noemt_ho: gaat een vraag aantoonbaar over hoger onderwijs? (#556, epic #554). noemt_vo_doorstroom: over doorstroom
uit het vo naar vervolgonderwijs (#877)? vo_context_poort: op welke vraag (#597)."""

import ast
from pathlib import Path

import pytest

from tools.ho_markers import beurtvraag, noemt_ho, noemt_vo_doorstroom, opent_vo_context, vo_context_poort

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
    assert vo_context_poort("instroom hbo") is True
    assert vo_context_poort("doorstroom vmbo mbo") is True
    assert vo_context_poort("vwo leerlingen") is False


def test_het_model_opent_de_poort_niet_door_hbo_toe_te_voegen():
    with beurtvraag("Hoeveel leerlingen zitten er op het vwo?"):
        assert vo_context_poort("vwo leerlingen hbo") is False
        assert vo_context_poort("doorstroom vwo mbo") is False


def test_het_model_sluit_de_poort_niet_door_hbo_weg_te_laten():
    with beurtvraag("Hoeveel vwo-leerlingen stromen door naar het wo?"):
        assert vo_context_poort("doorstroom vwo") is True


def test_na_de_beurt_beslist_de_zoekterm_weer():
    with beurtvraag("doorstroom vwo naar wo"):
        pass
    assert vo_context_poort("vwo leerlingen") is False


# Doorstroom uit het vo naar vervolgonderwijs (#877, besluit A): een vo-niveau met het mbo of een doorstroomwoord.
_DOORSTROOM = {
    # vmbo → mbo
    "Hoeveel vmbo-leerlingen stromen door naar het mbo?",
    "Hoeveel vmbo'ers gaan naar een roc?",
    "instroom in het mbo vanuit het vmbo",
    "doorstroom vmbo per leerweg",
    # havo → hbo en vwo → wo, zonder ho-woord
    "Waar gaan havo-leerlingen heen na hun diploma?",
    "Waar gaan havisten heen na hun diploma?",
    "Wat doen vwo-leerlingen na het examen?",
    "Hoeveel vwo'ers kiezen een vervolgopleiding?",
    "Welk vervolgonderwijs volgen leerlingen uit het voortgezet onderwijs?",
    "Wat doen leerlingen na de middelbare school?",
    "uitstroom uit het vo naar onderwijssoort",
    "Hoeveel havisten stromen er door na het behalen van hun diploma?",
    # vavo
    "Hoeveel vavo-deelnemers stromen door naar vervolgonderwijs?",
    "Hoeveel mensen halen via het vavo een diploma en gaan daarna naar het mbo?",
    # vsv-terugkeer: geen vo-niveau, wel terugkeer in het onderwijs
    "Hoeveel voortijdig schoolverlaters keren terug in het onderwijs?",
    "terugkeer vsv'ers onderwijs",
    "Hoeveel vsv'ers komen na een jaar terug?",
}
# Geen doorstroom: een losse vo-vraag, doorstroom of mbo zonder vo-niveau, vsv zonder terugkeer, of po/(v)so erbij.
_GEEN_DOORSTROOM = {
    "",
    "Hoeveel leerlingen zitten er op het vwo in Utrecht?",
    "Hoeveel mbo-studenten per instelling?",
    "doorstroom binnen het mbo per niveau",
    "doorstroom",
    "Hoeveel vmbo-leerlingen halen hun diploma?",
    "slagingspercentage op havo en vwo",
    "Hoeveel havisten zakken voor het examen?",
    "prognoses vo per instelling",
    "Hoeveel voortijdig schoolverlaters zijn er in het mbo?",
    "vsv per gemeente",
    "Hoeveel leerlingen zitten er vooral in de bovenbouw?",
    "doorstroom van de basisschool naar het vwo",
    "Hoeveel leerlingen gaan na groep 8 naar de havo en daarna naar het mbo?",
    "doorstroom van het vso naar het mbo",
    # Doorstroom binnen het vo is geen vervolgonderwijs.
    "doorstroom van het vmbo naar de havo",
    "Hoeveel havisten stromen door naar het vwo?",
    "Hoeveel vo-leerlingen stromen door naar de bovenbouw?",
}


@pytest.mark.parametrize("vraag", sorted(_DOORSTROOM))
def test_een_doorstroomvraag_uit_het_vo_opent_de_vo_context(vraag):
    assert noemt_vo_doorstroom(vraag) is True
    assert opent_vo_context(vraag) is True


@pytest.mark.parametrize("vraag", sorted(_GEEN_DOORSTROOM))
def test_een_vraag_zonder_doorstroom_uit_het_vo_opent_niets(vraag):
    assert noemt_vo_doorstroom(vraag) is False
    assert opent_vo_context(vraag) is False


def test_een_ho_vraag_opent_de_vo_context_zoals_voorheen():
    """noemt_ho blijft een eigen weg (epic #554): ook zonder vo-niveau of doorstroomwoord."""
    assert opent_vo_context("Hoeveel eerstejaars heeft de universiteit?") is True
    assert noemt_vo_doorstroom("Hoeveel eerstejaars heeft de universiteit?") is False


def test_de_poort_volgt_de_doorstroomvraag_van_de_beurt():
    with beurtvraag("Waar gaan havisten heen na hun diploma?"):
        assert vo_context_poort("havo diploma") is True
    with beurtvraag("En voor het vwo?"):  # een vervolgvraag zonder doorstroomwoord blijft dicht (#597)
        assert vo_context_poort("doorstroom vwo") is False


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
