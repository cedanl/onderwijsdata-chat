"""Een uitgeschreven rekensom in het antwoord wordt nagerekend (#1001, reaudit 10-11)."""

import pytest

from agent.probleem import meldingen
from agent.rekensom import onjuiste_rekensommen


def test_de_som_uit_de_reaudit_is_een_probleem():
    [probleem] = onjuiste_rekensommen("Dat zijn 3 × 3 × 3 × 4 × 15 = 540 combinaties.")

    assert "3 × 3 × 3 × 4 × 15 is 1.620, niet 540" in probleem
    assert "3 × 3 × 3 × 4 × 15 is 1.620, niet 540" in meldingen([probleem])[0]


@pytest.mark.parametrize(
    "tekst",
    [
        "Dat zijn 3 × 3 × 3 × 4 × 15 = 1.620 combinaties.",
        "Het aandeel is 571 / 8.060 × 100 = 7,1 procent.",
        "Het aandeel is 571 / 8.060 × 100 = 7,1%.",
        "Een derde: 1 / 3 = 33%.",
        "Samen 12.345 + 655 = 13.000 studenten.",
        "Eerst vermenigvuldigen: 2 + 3 × 4 = 14.",
        "Het verschil is 478.660 − 475.460 = 3.200.",
        "Zonder spaties: 3x4 = 12 en 10/4 = 2,5.",
        "Over 2024 − 2019 = 5 jaar.",
    ],
)
def test_een_juiste_som_is_in_orde(tekst):
    assert onjuiste_rekensommen(tekst) == []


@pytest.mark.parametrize(
    ("tekst", "melding"),
    [
        ("Het aandeel is 571 / 8.060 × 100 = 9,5%.", "571 / 8.060 × 100 is 7,1%, niet 9,5%"),
        ("Eerst vermenigvuldigen: 2 + 3 × 4 = 20.", "2 + 3 × 4 is 14, niet 20"),
        ("Het verschil is 478.660 − 475.460 = 3.100.", "478.660 − 475.460 is 3.200, niet 3.100"),
        ("Gemiddeld 10 ÷ 4 = 2,4 per groep.", "10 ÷ 4 is 2,5, niet 2,4"),
    ],
)
def test_een_foute_som_noemt_de_juiste_uitkomst(tekst, melding):
    [probleem] = onjuiste_rekensommen(tekst)

    assert melding in probleem


@pytest.mark.parametrize(
    "tekst",
    [
        "In 2024/25 waren het er 500.",
        "in 2023/24 = 500 studenten",
        "In 2023/2024 = 500 studenten.",
        "Over 2019-2023 = 4 jaar daalde het aantal.",
        "In 2023-24 = 500 studenten.",
    ],
)
def test_een_schooljaar_is_geen_deling(tekst):
    assert onjuiste_rekensommen(tekst) == []


@pytest.mark.parametrize(
    "tekst",
    [
        "Dat zijn ongeveer 3 × 3 × 3 × 4 × 15 = 540 combinaties.",
        "Dat zijn circa 3 × 180 = 500 studenten.",
        "3 × 180 ≈ 500, dus 3 × 180 = 500 bij benadering.",
    ],
)
def test_een_benadering_wordt_niet_nagerekend(tekst):
    assert onjuiste_rekensommen(tekst) == []


@pytest.mark.parametrize(
    "tekst",
    [
        "Dat zijn 3 × 3 × 3 × 4 × 15 combinaties, dus 540.",
        "Een som zonder is-teken: 3 + 4.",
        "Over twee zinnen: 3 + 4.\n= 9",
        "Een minteken vooraan: −3 + 5 = 2.",
        "Haakjes: (3 + 4) × 2 = 14.",
        "Een code: A025279 + 1 = 5.",
        "Een percentage als term: 50% + 3 = 4.",
        "Rechts weer een som: 3 × 4 = 10 + 2.",
        "Een variabele: x = 3 * 4.",
        "Delen door nul: 5 / 0 = 1.",
    ],
)
def test_wat_geen_strikte_som_is_slaat_de_controle_over(tekst):
    assert onjuiste_rekensommen(tekst) == []


def test_alleen_een_som_die_in_elke_lezing_fout_is_telt():
    # 1,620: in de Nederlandse lezing 1,62, in de Engelse 1.620 (controles.lezingen).
    assert onjuiste_rekensommen("3 × 3 × 3 × 4 × 15 = 1,620", "3 × 3 × 3 × 4 × 15 = 1.620") == []
    assert len(onjuiste_rekensommen("3 × 4 = 540", "3 × 4 = 540")) == 1


def test_elke_foute_som_in_een_tekst_geeft_een_probleem():
    tekst = "Eerst 2 × 3 = 7. Daarna 10 + 5 = 15. Tot slot 4 × 4 = 15."

    problemen = onjuiste_rekensommen(tekst)

    assert len(problemen) == 2
    assert "2 × 3 is 6, niet 7" in problemen[0] and "4 × 4 is 16, niet 15" in problemen[1]
