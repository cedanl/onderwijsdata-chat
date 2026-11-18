"""Vraagt de gebruiker om een verklaring? Code beslist, niet het model (#1036).

Besluit (vastgelegd in deze test): "reden" telt alleen in een verzoekvorm ("de reden voor/van/achter", "om welke
reden", "wat is de reden"), niet als los onderwerpwoord. "verklaring" telt niet in "verklaring van de
afkorting/term/begrip/woord" en niet in "verklaring omtrent gedrag".
"""

import pytest

from tools.verklaring_markers import vraagt_verklaring


@pytest.mark.parametrize(
    "vraag",
    [
        "Waarom daalt de instroom?",
        "Hoe komt het dat de instroom daalt?",
        "Hoe komt dat?",
        "Wat is de oorzaak van de daling?",
        "Wat zijn de oorzaken?",
        "Geef een verklaring voor de daling.",
        "Kun je dit verklaren?",
        "Komt dat door de coronapandemie?",
        "Wat zit erachter?",
        "Wat is de reden van de daling?",
        "Om welke reden kiezen minder studenten voor de pabo?",
        "Wat is de reden achter de groei?",
    ],
)
def test_een_verzoek_om_een_verklaring(vraag):
    assert vraagt_verklaring(vraag)


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel eerstejaars hbo zijn er per jaar sinds 2020?",
        "Wat is de verklaring van de afkorting HBO?",
        "Wat is de verklaring van het begrip instroom?",
        "Hoeveel studenten volgen redenen om te studeren",
        "Hoeveel mbo-studenten hebben een verklaring omtrent gedrag nodig?",
        "",
    ],
)
def test_geen_verzoek_om_een_verklaring(vraag):
    assert not vraagt_verklaring(vraag)


@pytest.mark.parametrize("vervolg", ["En voor wo?", "Ook voor het mbo?", "en in Utrecht", "Voor de pabo?"])
def test_een_elliptische_vervolgvraag_houdt_het_verzoek_van_de_vorige_vraag(vervolg):
    assert vraagt_verklaring(vervolg, vorige="Waarom daalt de instroom?")


def test_een_volledige_nieuwe_vraag_na_een_waaromvraag_vraagt_niets():
    assert not vraagt_verklaring("Hoeveel zijn het in 2023, per instelling?", vorige="Waarom daalt de instroom?")


def test_een_korte_vervolgvraag_na_een_gewone_datavraag_vraagt_niets():
    assert not vraagt_verklaring("En voor wo?", vorige="Hoeveel eerstejaars hbo zijn er per jaar sinds 2020?")


def test_een_eigen_verzoek_na_een_databeurt_telt():
    assert vraagt_verklaring("Hoe komt dat?", vorige="Hoeveel eerstejaars hbo zijn er per jaar sinds 2020?")
