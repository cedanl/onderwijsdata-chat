"""Arbeidsmarktregio van een gemeente, in de namen die UWV en ROA gebruiken (#454).

Het profiel nam het RPA-gebied uit de DUO-adressen: een oudere indeling met andere namen en
grenzen. 16 van de 27 namen kende ROA niet (Utrecht-Midden, Centraal-Groningen, Fryslân, De
Vallei, Nijmegen, ...), dus get_roa_benchmark weigerde de regio van het profiel. De gemeente
van het adres plus de CBS-gebiedsindeling geeft de regio die ROA kent.
"""

import pytest

from data import arbeidsmarktregio


@pytest.mark.parametrize(
    ("gemeente", "regio"),
    [
        (344, "Midden-Utrecht"),  # Utrecht; DUO-RPA: Utrecht-Midden
        (14, "Groningen"),  # Groningen; DUO-RPA: Centraal-Groningen
        (80, "Friesland"),  # Leeuwarden; DUO-RPA: Fryslân
        (228, "FoodValley"),  # Ede; DUO-RPA: De Vallei
        (268, "Rijk van Nijmegen"),  # Nijmegen; DUO-RPA: Nijmegen
        (363, "Groot Amsterdam"),
    ],
)
def test_een_gemeente_geeft_de_arbeidsmarktregio_van_uwv_en_roa(gemeente, regio):
    assert arbeidsmarktregio.van_gemeente(gemeente) == regio


def test_de_voorloopnul_maakt_niet_uit():
    """DUO geeft GEMEENTENUMMER als getal (80), CBS als code met voorloopnul (0080), zie #24."""
    assert arbeidsmarktregio.van_gemeente(80) == arbeidsmarktregio.van_gemeente("0080") == "Friesland"
    assert arbeidsmarktregio.van_gemeente(" 80 ") == "Friesland"


@pytest.mark.parametrize("gemeente", [9999, None, "", "Utrecht", float("nan")])
def test_een_onbekende_gemeente_geeft_geen_regio(gemeente):
    """Geen gok: zonder regio valt het profiel terug op de provincie."""
    assert arbeidsmarktregio.van_gemeente(gemeente) is None


def test_de_indeling_heeft_alle_gemeenten_en_35_regios_met_bron():
    gemeenten = arbeidsmarktregio.gemeenten()

    assert len(gemeenten) > 300
    assert all(len(code) == 4 and code.isdigit() for code in gemeenten)
    assert len(set(gemeenten.values())) == 35
    assert arbeidsmarktregio.bron()["tabel"] == "86247NED"
