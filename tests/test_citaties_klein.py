"""Bronwaarden onder 1.000 krijgen een citatie bij een bron die haar waarden exact meegeeft (#963).

Review 08-B3: "Biomedische Wetenschappen | 71 plaatsen" had geen citatie, want de citaties namen alleen getallen van
vier of meer cijfers mee, de grens van de getalcontrole. Bij financien, WOPI en de Studiekeuzedatabase staat elke
waarde als getypeerde meetwaarde met haar exacte waarde (`Meetwaarde.decimaal`). Een getal onder 1.000 krijgt daar
een citatie als het die waarde exact is, de zin of tabelrij de selectie noemt (opleiding, instelling, bestuur) en de
maat niet twijfelachtig is; en alleen als elk voorkomen van dat getal in de tekst zo een citatie krijgt. De
getalcontrole verandert niet.

Zonder netwerk: de proefexport van `onderwijsbronnen.skdb`, zoals tests/test_studiekeuze.py.
"""

import json

import pytest
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

from agent.citaties import citaties
from agent.grounding import unverified
from tools import studiekeuze


@pytest.fixture(autouse=True)
def proefexport(monkeypatch):
    monkeypatch.setattr(skdb, "haal_op", lambda *a, **k: proefbestand.standaard())
    studiekeuze._export.cache_clear()
    yield
    studiekeuze._export.cache_clear()


def _numerus_fixus() -> list[tuple[str, str]]:
    """De numerus-fixuslijst van de proefexport: Biomedische Wetenschappen, 60 plaatsen (2026) en 71 (2027)."""
    return [("get_studiekeuze", studiekeuze.get_studiekeuze(weergave="numerus_fixus"))]


def _skdb(*rijen: dict) -> list[tuple[str, str]]:
    uitkomst = {"dataset": studiekeuze.DATASET, "data_key": "skdb:opleidingen:proef", "rijen": list(rijen)}
    return [("get_studiekeuze", json.dumps(uitkomst))]


def test_b3_de_capaciteit_krijgt_een_citatie_het_jaartal_niet():
    tekst = "Biomedische Wetenschappen heeft 71 plaatsen (2027)."

    [citatie] = citaties(tekst, _numerus_fixus())

    assert citatie["getal"] == "71" and citatie["vastgesteld"] is True
    assert citatie["maat"] == "capaciteit"
    assert "Biomedische Wetenschappen" in citatie["selectie"] and "Studiejaar: 2027" in citatie["selectie"]
    assert "Studiekeuzedatabase" in citatie["bron"]


def test_b3_in_een_tabelrij_wijst_de_opleiding_de_rij_aan():
    tekst = (
        "| Opleiding | Voertaal | Plaatsen |\n|---|---|---|\n"
        "| Biomedische Wetenschappen | Voertaal-overstijgend | 60 |\n"
    )

    [citatie] = citaties(tekst, _numerus_fixus())

    assert (citatie["getal"], citatie["vastgesteld"]) == ("60", True)
    assert "Studiejaar: 2026" in citatie["selectie"]


def test_zonder_selectie_in_de_zin_geen_citatie():
    """Een klein getal is te vaak toeval: "71 plaatsen" zonder opleiding of instelling bindt niet."""
    assert citaties("Er zijn 71 plaatsen.", _numerus_fixus()) == []


def test_een_code_of_rangnummer_is_geen_meetwaarde():
    """keren_meedoen (2) staat niet als maat; een getal dat alleen daar staat, krijgt geen citatie."""
    assert citaties("Biomedische Wetenschappen doet 2 keer mee.", _numerus_fixus()) == []


def test_alles_of_niets_per_getal():
    """De frontend geeft het k-de voorkomen de k-de citatie met dat getal: een ongebonden voorkomen zou anders de
    citatie van een ander krijgen."""
    tekst = "Biomedische Wetenschappen heeft 71 plaatsen. Dat zijn er 71."
    assert citaties(tekst, _numerus_fixus()) == []


def test_elk_gebonden_voorkomen_krijgt_een_citatie():
    tekst = "Biomedische Wetenschappen heeft 71 plaatsen. Bij Biomedische Wetenschappen blijft het 71."
    assert [c["getal"] for c in citaties(tekst, _numerus_fixus()) if c["vastgesteld"]] == ["71", "71"]


def test_alleen_een_exacte_waarde_niet_afgerond_of_afgekapt():
    stappen = _skdb(
        {"instelling": "Hogeschool Utrecht", "opleiding": "ICT", "nse_oordeel": 3.61, "doorstroom_jaar2_pct": 70.0}
        | {"diploma_opleiding_pct": 45.5, "nse_respondenten": 120}
    )

    assert citaties("ICT scoort een 3 of een 4, en 45 of 46 procent haalt het diploma.", stappen) == []
    doorstroom, respondenten = citaties("Bij ICT stroomt 70% door, met 120 respondenten.", stappen)
    assert (doorstroom["maat"], doorstroom["eenheid"]) == ("doorstroom_jaar2_pct", "%")
    assert respondenten["maat"] == "nse_respondenten"


def test_twijfel_tussen_maten_geeft_geen_citatie():
    stappen = _skdb({"instelling": "Hogeschool Utrecht", "opleiding": "ICT", "studenten": 40, "eerstejaars": 40})

    assert citaties("ICT heeft 40.", stappen) == []
    [citatie] = citaties("ICT heeft 40 eerstejaars.", stappen)
    assert citatie["maat"] == "eerstejaars"


def test_gelijke_waarde_in_twee_rijen_van_dezelfde_maat_volgt_de_bronhierarchie():
    """B3 op test: 71 plaatsen in 2026 en in 2027; de tabelrij noemt geen jaar. Dezelfde maat, dezelfde tabel."""
    rij = {"instelling": "Universiteit Leiden", "opleiding": "Biomedische Wetenschappen", "capaciteit": 71}
    stappen = _skdb(rij | {"studiejaar": 2026}, rij | {"studiejaar": 2027})

    [citatie] = citaties("| Biomedische Wetenschappen | 71 |", stappen)

    assert citatie["vastgesteld"] is True and citatie["maat"] == "capaciteit"


def test_kleine_getallen_van_andere_bronnen_blijven_zonder_citatie():
    cbs = json.dumps({"data_key": "cbs:1", "rijen": [{"Onderwijssoort_label": "Hbo", "Totaal": 71}]})
    assert citaties("In het Hbo waren het er 71.", [("get_cbs_data", cbs)]) == []


def test_de_getalcontrole_blijft_bij_vier_cijfers():
    """Een klein getal dat nergens in de data staat, blijft buiten de getalcontrole: geen nieuwe meldingen."""
    [(_, resultaat)] = _numerus_fixus()
    assert unverified("Biomedische Wetenschappen heeft 72 plaatsen en 3 rondes.", [resultaat]) == []
