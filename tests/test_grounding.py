"""Elk groot getal in modeltekst moet uit toolresultaten komen, welk model ook (#48, #175)."""

import json

from agent.grounding import unsourced_numbers

_CBS_RESULT = json.dumps({"rijen": [
    {"Perioden": "2024SJ00", "TotaalIngeschrevenen_1": 378490},
    {"Perioden": "2025SJ00", "TotaalIngeschrevenen_1": 367960.0},
]})


def test_getallen_uit_de_data_zijn_gedekt_ook_met_duizendtalpunt():
    tekst = "In 2024/'25 stonden 378.490 studenten ingeschreven, in 2025/'26 367960."
    assert unsourced_numbers(tekst, [_CBS_RESULT]) == set()


def test_verzonnen_getal_wordt_gevonden():
    # Live-audit 6: het Opus-rapport gaf 336.800 / 331.200 waar de data 378.490 / 367.960 had.
    tekst = "Het aantal daalde van 336.800 naar 331.200."
    assert unsourced_numbers(tekst, [_CBS_RESULT]) == {"336800", "331200"}


def test_tabelnummers_en_codes_zijn_geen_getallen():
    # #48: 85423NED in een bronvermelding liet het dashboard omvallen.
    tekst = "Bron: CBS 85423NED, periode 2024SJ00, code T001228."
    assert unsourced_numbers(tekst, []) == set()


def test_jaartallen_en_kleine_getallen_worden_niet_gecontroleerd():
    tekst = "Tussen 2021 en 2025 veranderden 3 van de 12 opleidingen."
    assert unsourced_numbers(tekst, []) == set()


def test_decimale_komma_is_geen_duizendtal():
    # 12,5 is geen 125 en valt onder de drempel; 1.234,5 is 1234.
    assert unsourced_numbers("Een daling van 12,5%.", []) == set()
    assert unsourced_numbers("Gemiddeld 1.234,5 per jaar.", []) == {"1234"}
