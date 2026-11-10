"""Gouden tests voor get_mbo_indicatoren, get_inspectieoordeel en get_accreditatie op bevroren bronnen (#870).

De bronnen zijn op 02-11-2026 live opgehaald met `scripts/gouden_testfixtures.py` (bron-URL's in
`tests/fixtures/gouden/bronnen.json`); de fixture `gouden` zet ze klaar en sluit het netwerk af. De verwachte waarden
zijn uit die bestanden nagerekend buiten de tool om, met de berekening in het commentaar bij elke test.
"""

import json

import httpx
import pytest

from tests.netwerkblok import BLOK, NetwerkGeblokkeerd
from tools import inspectie
from tools.accreditatie import get_accreditatie
from tools.inspectie import get_inspectieoordeel
from tools.mbo_indicatoren import get_mbo_indicatoren

pytestmark = pytest.mark.usefixtures("gouden")


def _json(tekst: str) -> dict:
    uit = json.loads(tekst)
    assert isinstance(uit, dict), tekst
    return uit


def test_het_netwerk_is_dicht():
    """De gouden tests zijn netwerkvrij: een tool die toch naar buiten gaat, faalt hierop."""
    with pytest.raises(NetwerkGeblokkeerd):
        httpx.get("https://duo.nl/", timeout=1)
    BLOK.pogingen.clear()  # bewust geweigerd: laat de test zelf niet falen


# --- get_mbo_indicatoren --------------------------------------------------------------------------------------------
# Bron: DUO, 2026-indicatoren-per-instelling.xlsx (editie 2026, peildatum 1 oktober 2025), opgehaald 02-11-2026.
# Nagerekend met pandas, rij Instellingscode 27GZ en de kolommen onder de drie koprijen (Inst. / Vgl Grp):
#   pd.read_excel(xlsx, sheet_name="JR en DR", header=None); idem "VSV"
#   Jaarresultaat     Inst. 0.684789401324834  0.705640345056403  0.685177151120752
#                     Vgl   0.690877991916243  0.708770249234506  0.717899163108854
#   Diplomaresultaat  Inst. 0.705387205387205  0.725510660503951  0.702755267423015
#                     Vgl   0.704058436638075  0.719388888536265  0.72440228349962
#   Nieuwe vsv        Inst. 0.0747             0.0683             0.0639
#                     Vgl   0.0667601480282179 0.0632719250278129 0.0603722239308115
# Procent = fractie x 100, half naar boven afgerond op één decimaal; verschil = afgerond min afgerond.
_MONDRIAAN = {
    "jaarresultaat": [(68.5, 69.1, -0.6), (70.6, 70.9, -0.3), (68.5, 71.8, -3.3)],
    "diplomaresultaat": [(70.5, 70.4, 0.1), (72.6, 71.9, 0.7), (70.3, 72.4, -2.1)],
    "nieuwe_vsv": [(7.5, 6.7, 0.8), (6.8, 6.3, 0.5), (6.4, 6.0, 0.4)],
}


def test_mbo_indicatoren_roc_mondriaan():
    uit = _json(get_mbo_indicatoren("ROC Mondriaan"))

    assert uit["instelling"]["instellingscode"] == "27GZ"
    assert uit["vergelijkingsgroep"]["code"] == "ROC"
    for indicator, verwacht in _MONDRIAAN.items():
        reeks = uit[indicator]
        assert [r["schooljaar"] for r in reeks] == ["2022/23", "2023/24", "2024/25"]
        assert [(r["instelling"], r["vergelijkingsgroep"], r["verschil_procentpunt"]) for r in reeks] == verwacht
    assert [r.get("voorlopig", False) for r in uit["nieuwe_vsv"]] == [False, False, True]
    assert (uit["bron"]["editie"], uit["bron"]["peildatum"]) == (2026, "1 oktober 2025")


# --- get_inspectieoordeel -------------------------------------------------------------------------------------------
# Bron: Onderwijsinspectie, 20261001-oordeel-en-standaard-bg.ods (peildatum 01-10-2026), opgehaald 02-11-2026,
# gefilterd op de besturen 31121, 40597, 40870 en 67237. Nagelezen in content.xml van het bevroren bestand (Kader en
# de standaardkolommen; FinancieelBeheer = FB, KwaliteitszorgEnAmbitie = KwA, de rest leeg):
#   ="40597" | Stichting ROC Midden Nederland      | MBO    | Goed        | 20230130 | BST2021   | BKA1-3 Goed, Goed,
#                                                                                                 Voldoende
#   ="67237" | Stichting Grafisch Lyceum Rotterdam | VO-MBO | Voldoende   | 20230414 | BST2021   | BKA1-3 Voldoende (3x)
#   ="31121" | Stichting Grafisch Lyceum Utrecht   | MBO    | Onvoldoende | 20260916 | BST21_V25 | BKA1-3 Voldoende,
#                                                                                                 Voldoende, Onvoldoende
#   ="40870" | Scalda Stichting                    | MBO    | (leeg)      | (leeg)   | BST2017   | FB Voldoende, KwA Goed,
#                                                   KA1-3 Voldoende, Goed, Voldoende; FB1 Voldoende, FB2 leeg, FB3 Voldoende
# Het bestuursnummer komt uit DUO's adressenbestand (tests/fixtures/duo): 25LH → 40597, 23JA → 67237, 23KG → 31121,
# 25PV → 40870. Tot #874 las de tool BKA1-3 niet en kregen de kader-2021-besturen `standaarden: {}`.
_BKA = ("Visie, ambities en doelen", "Uitvoering en kwaliteitscultuur", "Evaluatie, verantwoording en dialoog")


@pytest.mark.parametrize(
    ("instelling", "bestuur", "nummer", "sectoren", "oordeel", "vastgesteld", "gemengd", "bka"),
    [
        ("ROC Midden Nederland", "Stichting ROC Midden Nederland", 40597, ["mbo"], "Goed", "30-01-2023", False,
         ("Goed", "Goed", "Voldoende")),
        ("Grafisch Lyceum R'dam", "Stichting Grafisch Lyceum Rotterdam", 67237, ["vo", "mbo"], "Voldoende",
         "14-04-2023", True, ("Voldoende", "Voldoende", "Voldoende")),
    ],
)  # fmt: skip
def test_inspectieoordeel_per_bestuur(instelling, bestuur, nummer, sectoren, oordeel, vastgesteld, gemengd, bka):
    uit = _json(get_inspectieoordeel(instelling))

    assert uit["bestuur"] == {"naam": bestuur, "nummer": nummer, "sectoren": sectoren}
    assert (uit["eindoordeel"], uit["vastgesteld"], uit["gemengd"]) == (oordeel, vastgesteld, gemengd)
    assert uit["standaarden"] == dict(zip(_BKA, bka, strict=True))
    assert uit["kwaliteitsgebieden"] == {}
    assert (uit["kader"]["code"], uit["kader"]["naam"]) == ("BST2021", "Onderzoekskader 2021")
    assert uit["peildatum"] == uit["bron"]["peildatum"] == "01-10-2026"
    assert uit["bron"]["url"].endswith("20261001-oordeel-en-standaard-bg.ods")
    assert ("noot" in uit) is gemengd  # de noot over het hele bestuur, alleen bij vo naast mbo


def _oordeel(instellingscode: str) -> inspectie.Oordeel:
    """Het oordeel via het adressenbestand: Scalda en het GLU staan niet in het register van de gouden tests."""
    oordeel = inspectie.oordeel_voor_instelling(instellingscode, inspectie.peilbestand())
    assert oordeel is not None, instellingscode
    return oordeel


def test_inspectieoordeel_kader_2017_kwaliteitsgebieden_en_de_oude_standaarden():
    scalda = _oordeel("25PV")

    assert (scalda.bestuursnummer, scalda.bestuursnaam) == (40870, "Scalda Stichting")
    assert (scalda.kader, scalda.eindoordeel) == ("BST2017", None)  # het kader 2017 kende geen eindoordeel per bestuur
    assert scalda.kwaliteitsgebieden == {"Financieel beheer": "Voldoende", "Kwaliteitszorg en ambitie": "Goed"}
    assert scalda.standaarden == {"Kwaliteitszorg": "Voldoende", "Kwaliteitscultuur": "Goed",
                                  "Verantwoording en dialoog": "Voldoende", "Continuïteit": "Voldoende",
                                  "Rechtmatigheid": "Voldoende"}  # fmt: skip


def test_inspectieoordeel_kader_2021_versie_2025():
    glu = _oordeel("23KG")

    assert (glu.bestuursnummer, glu.kader, glu.eindoordeel, glu.vastgesteld) == (
        31121,
        "BST21_V25",
        "Onvoldoende",
        "16-09-2026",
    )
    assert glu.standaarden == dict(zip(_BKA, ("Voldoende", "Voldoende", "Onvoldoende"), strict=True))
    assert glu.kwaliteitsgebieden == {}


# --- get_accreditatie -----------------------------------------------------------------------------------------------
# Bron: DUO, Overzicht Erkenningen ho (HO_Erkenningen_RIO, versie van 02-11-2026), opgehaald 02-11-2026, gefilterd op
# INSTELLINGSCODE 21PD (Universiteit Utrecht). Nagelezen met pandas, de ACTUEEL-rijen per ERKENDEOPLEIDINGSCODE:
#   df = pd.read_csv(gz, dtype=str); df[(df.ERKENDEOPLEIDINGSCODE == code) & (df.STATUS == "ACTUEEL")]
#   50035 Culturele Antropologie ...  VOLTIJD           besluit 2019-09-09, begin 2019-09-09, inlever 2025-05-01,
#                                                       uitstel 2027-05-02, reden ART_5_16_LID_4
#   56838 Sociale Geografie ...       VOLTIJD, DEELTIJD besluit 2025-12-16, inlever 2031-11-01 (beide rijen gelijk)
#   50981 Zorg, Gezondheid & ...      VOLTIJD           besluit 2026-04-28, verval 2028-09-01, reden ART_5_31_LID_3
#                                                       (zonder uitsteldatum)


def _datums(uit: dict) -> dict:
    return {sleutel: {k: v for k, v in veld.items() if k != "betekenis"} for sleutel, veld in uit["datums"].items()}


def test_accreditatie_verlengd_met_grond_en_een_uiterste_indiening_in_het_verleden():
    uit = _json(get_accreditatie("Universiteit Utrecht", "50035"))

    assert uit["opleiding"] == {"croho": "50035", "naam": "Culturele Antropologie en Ontwikkelingssociologie",
                                "niveau": ["wo bachelor"], "vormen": ["voltijd"]}  # fmt: skip
    assert _datums(uit) == {
        "besluitdatum": {"datum": "09-09-2019"},
        "begindatum": {"datum": "09-09-2019"},
        "uiterste_indiening_volgende_beoordeling": {"datum": "01-05-2025"},
        "verlengd_tot": {"datum": "02-05-2027", "grond": "artikel 5.16 lid 4 WHW", "verstreken": False},
    }
    assert "01-05-2025" in uit["noot"] and "niet dat de accreditatie is verlopen" in uit["noot"]
    assert uit["bron"]["peilmoment"] == "versie van 02-11-2026"


def test_accreditatie_over_vestigingen_en_vormen_heen():
    uit = _json(get_accreditatie("Universiteit Utrecht", "Sociale Geografie en Planologie"))

    assert uit["opleiding"]["croho"] == "56838"
    assert uit["opleiding"]["vormen"] == ["deeltijd", "voltijd"]
    assert _datums(uit) == {
        "besluitdatum": {"datum": "16-12-2025"},
        "uiterste_indiening_volgende_beoordeling": {"datum": "01-11-2031"},
    }


def test_accreditatie_van_een_nieuwe_opleiding_met_vervaldatum_en_grond_zonder_datum():
    uit = _json(get_accreditatie("Universiteit Utrecht", "50981"))

    assert _datums(uit) == {
        "besluitdatum": {"datum": "28-04-2026"},
        "vervaldatum_nieuwe_opleiding": {"datum": "01-09-2028", "verstreken": False},
        "verlengd_tot": {"datum": None, "grond": "artikel 5.31 lid 3 WHW"},
    }
