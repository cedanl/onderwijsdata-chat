"""Eén naamregel voor de bestandsnamen van rapportdownloads, in de browser en op de server (#1124, #1125).

frontend/src/bestandsnaam.js doet hetzelfde; `tests/fixtures/bestandsnamen.json` houdt de twee gelijk
(frontend/src/__tests__/bestandsnaam.test.js leest hetzelfde bestand).
"""

import json
from pathlib import Path

import pytest

from core.bestandsnaam import RAPPORT_MAX, bestandsdeel, rapportdeel
from routes.rapport_docx import bestandsnaam

GEVALLEN = json.loads((Path(__file__).parent / "fixtures" / "bestandsnamen.json").read_text(encoding="utf-8"))


def test_de_fixture_en_de_code_noemen_hetzelfde_maximum():
    assert GEVALLEN["maximum"] == RAPPORT_MAX


@pytest.mark.parametrize("geval", GEVALLEN["gevallen"], ids=lambda g: g["titel"][:30] or "leeg")
def test_rapportdeel_volgt_de_gedeelde_gevallen(geval):
    assert rapportdeel(geval["titel"]) == geval["deel"]


def test_een_accent_wordt_een_letter_en_een_emoji_hooguit_een_streepje():
    assert rapportdeel("Commerciële opleidingen") == "Commerciele_opleidingen"
    assert "__" not in rapportdeel("🎓📊 studenten 📊🎓 en meer")


def test_een_titel_van_300_tekens_blijft_onder_de_grens_van_een_bestandssysteem():
    titel = "Commerciële opleidingen in het hoger onderwijs " * 7
    naam = bestandsnaam(titel)
    assert len(titel) > 300
    assert len(naam.removesuffix(".docx")) <= RAPPORT_MAX
    assert len(naam.encode()) < 255
    assert naam.endswith("_opleidingen_in.docx")  # op een woordgrens, geen half woord


def test_een_korte_titel_houdt_zijn_naam():
    assert bestandsnaam("Instroom HU 2023/24") == "Instroom_HU_2023_24.docx"


def test_bestandsdeel_kapt_een_gegeven_maximum_op_een_woordgrens_af():
    assert bestandsdeel("aaa bbb ccc", 9) == "aaa_bbb"
    assert bestandsdeel("aaa bbb ccc", 7) == "aaa_bbb"
    assert bestandsdeel("aaabbbccc", 4) == "aaab"
