"""Een gekozen verduidelijkingsoptie bindt het antwoord (#246).

Audit 11: de gebruiker koos "2023 (laatste beschikbare werkelijke cijfers)"; het
antwoord vergeleek de vo-prognose toch met 2018 uit een bestand dat bij 2018 ophoudt.
Elk getal kwam uit een tool, dus de getalcontrole zweeg.
"""

from agent.keuze import genegeerde_keuze

_KEUZE = ["2023 (laatste beschikbare werkelijke cijfers)"]


def test_antwoord_over_een_ander_jaar_wordt_gemeld():
    tekst = "In 2030 zijn er 896.099 leerlingen, 8,85% minder dan in 2018 (983.119)."
    [probleem] = genegeerde_keuze(_KEUZE, tekst)
    assert "2023" in probleem


def test_antwoord_over_het_gekozen_jaar_is_goed():
    assert genegeerde_keuze(_KEUZE, "In 2023 waren er 905.000 leerlingen; in 2030 896.099.") == []


def test_eerlijk_melden_dat_het_jaar_ontbreekt_is_goed():
    assert genegeerde_keuze(_KEUZE, "Voor 2023 staan er geen werkelijke cijfers in de data.") == []


def test_schooljaar_als_keuze_telt_ook_in_label_vorm():
    assert genegeerde_keuze(["2023/24"], "In schooljaar 2023/2024 waren het er 26.370.") == []
    assert genegeerde_keuze(["2023/24"], "In 2024/25 waren het er 26.370.")


def test_keuze_zonder_jaar_bindt_niets():
    assert genegeerde_keuze(["Trend over tijd"], "Van 2019 tot 2024 steeg het aantal.") == []
    assert genegeerde_keuze([], "In 2018 waren het er 983.119.") == []


def test_meerdere_keuzes_elk_jaar_moet_terugkomen():
    keuzes = ["Hogeschool Utrecht", "2022/23", "2024/25"]
    [probleem] = genegeerde_keuze(keuzes, "In 2022/23 waren het er 27.441.")
    assert "2024" in probleem
