"""Elk groot getal in modeltekst moet uit toolresultaten komen, welk model ook (#48, #175)."""

import json

from agent.grounding import afgeleide_verschillen, getallen_in, unsourced_numbers, unverified

_CBS_RESULT = json.dumps(
    {
        "rijen": [
            {"Perioden": "2024SJ00", "TotaalIngeschrevenen_1": 378490},
            {"Perioden": "2025SJ00", "TotaalIngeschrevenen_1": 367960.0},
        ]
    }
)


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


def test_spatie_als_duizendtalscheiding_is_een_getal():
    # Audit 10 (#236): gpt-oss schrijft 4 287; zonder normalisatie werden dat 4 en 287,
    # allebei onder de drempel, en ging een verzonnen getal ongecontroleerd door.
    for tekst in (
        "Er waren 4 287 eerstejaars.",
        "Er waren 4\u00a0287 eerstejaars.",
        "Er waren 4\u202f287 eerstejaars.",
    ):
        assert unsourced_numbers(tekst, []) == {"4287"}
    assert unsourced_numbers("Landelijk 9\u202f876\u202f543 studenten.", []) == {"9876543"}


def test_spatienotatie_uit_de_data_is_gedekt():
    assert unsourced_numbers("In 2024/'25 stonden 378 490 studenten ingeschreven.", [_CBS_RESULT]) == set()


def test_losse_getallen_met_spatie_worden_niet_samengevoegd():
    # Alleen groepen van precies drie cijfers horen bij hetzelfde getal.
    assert unsourced_numbers("In 2024 12 opleidingen, in 2025 3 1234 keer.", []) == {"1234"}


# ── getallen_in: elk getal in Nederlandse notatie, ook kleine en jaartallen (#420) ──


def test_getallen_in_zonder_duizendtalscheiding_met_positie():
    tekst = "Van 378.490 naar 378 490, of 29\u00a0040 en 29\u202f040."
    assert getallen_in(tekst) == [
        ("378.490", "378490", 4),
        ("378 490", "378490", 17),
        ("29\u00a0040", "29040", 29),
        ("29\u202f040", "29040", 39),
    ]


def test_getallen_in_houdt_de_decimale_komma():
    assert [getal for _, getal, _ in getallen_in("Gemiddeld 9,6, of 1.234,5 per jaar (+9,5%).")] == [
        "9,6",
        "1234,5",
        "9,5",
    ]


def test_getallen_in_telt_ook_jaartallen_en_kleine_getallen():
    assert [getal for _, getal, _ in getallen_in("In 2024 waren 3 van de 12 opleidingen 12% groter.")] == [
        "2024",
        "3",
        "12",
        "12",
    ]


def test_getallen_in_slaat_codes_over():
    assert getallen_in("Bron: CBS 85423NED, periode 2024SJ00, code T001228.") == []


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


def test_toolresultaat_zonder_bron_is_geen_bewijs():
    # #201: run_analysis zonder gelezen key geeft {"bron": null, ...}.
    bronloos = json.dumps({"bron": None, "resultaat": 987654})
    assert unverified("Het totaal is 987654.", [bronloos]) == ["987654"]
    assert unverified("Het totaal is 987654.", [json.dumps({"bron": "duo", "resultaat": 987654})]) == []


def test_getal_dat_alleen_de_gebruiker_noemde_is_niet_gedekt():
    # #211: run.py geeft alleen assistentberichten als bron mee.
    assert unverified("Het totaal is 987654.", [], []) == ["987654"]


def test_verschil_van_twee_genoemde_getallen_uit_de_data_is_afgeleid():
    """CH-01 N23: 478.660 - 475.460 = 3.200 stond niet in de data en werd hard ingetrokken."""
    tekst = "Van 378.490 naar 367.960: 10.530 minder."
    assert afgeleide_verschillen(tekst, [_CBS_RESULT]) == {"10.530"}


def test_verschil_met_een_verzonnen_getal_is_niet_afgeleid():
    # 378.490 - 336.800 = 41.690, maar 336.800 staat niet in de data.
    tekst = "Van 378.490 naar 336.800: 41.690 minder."
    assert afgeleide_verschillen(tekst, [_CBS_RESULT]) == set()


def test_verschil_van_getallen_die_de_tekst_niet_noemt_is_niet_afgeleid():
    # 10.530 is het verschil van twee cellen, maar het antwoord noemt die cellen niet: niet na te rekenen.
    assert afgeleide_verschillen("Het aantal daalde met 10.530.", [_CBS_RESULT]) == set()
