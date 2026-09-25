"""Elk groot getal in modeltekst moet uit toolresultaten komen, welk model ook (#48, #175)."""

import json

from agent.grounding import unsourced_numbers, unverified

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


# ── Chatantwoorden (#185): ook percentages, in de vorm waarin ze in de tekst staan ──

_DUO_RESULT = json.dumps({"rijen": [{"STUDIEJAAR": 2025, "personen": 26370, "inschrijvingen": 28889}]})


def test_unverified_noemt_ongedekte_getallen_zoals_ze_in_de_tekst_staan():
    # Live-audit 7a: GPT-OSS telde 6.340 op waar de toolrijen 5.943 gaven.
    tekst = "In totaal 6.340 eerstejaars, waarvan 26.370 personen."
    assert unverified(tekst, [_DUO_RESULT]) == ["6.340"]


def test_percentage_moet_uit_een_tool_komen():
    # Sonnet: 2.519 / 26.370 = "9,5%"; het toolgetal 9.55 geeft afgerond 9,6.
    assert unverified("Het verschil is 9,5%.", [json.dumps({"value": 9.55})]) == ["9,5%"]
    assert unverified("Het verschil is 9,6%.", [json.dumps({"value": 9.55})]) == []


def test_percentage_mag_als_fractie_in_de_tooluitvoer_staan():
    assert unverified("Een aandeel van 9,6%.", [json.dumps({"aandeel": 0.0955})]) == []


def test_percentage_zonder_toolgetal_wordt_gevonden():
    assert unverified("Een daling van 7 procent.", [_DUO_RESULT]) == ["7 procent"]


def test_nul_en_honderd_procent_zijn_geen_berekening():
    assert unverified("Van 0% naar 100% dekking.", []) == []


def test_afgerond_getal_telt_als_ongedekt():
    # Sonnet: "circa 10.000 lager" waar het verschil 42.200 was.
    assert unverified("Dat is circa 10.000 minder.", [_DUO_RESULT]) == ["10.000"]


def test_getal_uit_een_eerder_bericht_telt_in_nederlandse_notatie():
    assert unverified("Nog steeds 28.355.", [], ["In 2021/22 waren het 28.355 personen."]) == []
    assert unverified("Een daling van 7,0%.", [], ["De daling was 7,0%."]) == []
