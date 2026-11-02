"""Gouden tests voor get_uwv_vacatures en get_roa_benchmark op bevroren bronnen (#870).

De bronnen zijn op 02-11-2026 via riodata opgehaald met `scripts/gouden_testfixtures.py` (zie
`tests/fixtures/gouden/bronnen.json`); de fixture `gouden` zet ze klaar en sluit het netwerk af. De verwachte waarden
zijn met pandas op de bevroren bestanden nagerekend, buiten de tools om; de berekening staat bij elke test.
"""

import json

import pytest

from tools.arbeidsmarkt import get_roa_benchmark, get_uwv_vacatures

pytestmark = pytest.mark.usefixtures("gouden")

# Bron: UWV Open Match (riodata uwv.load("latest", rec_type="Vacature"), bevroren stand van 16-05-2023), opgehaald
# 02-11-2026, gefilterd op PROVINCIE Flevoland. Nagerekend met pandas:
#   u = pd.read_csv(gz); u.AANTAL.sum() → 5848; u.BEROEPENCLUSTER.nunique() → 301
#   u.groupby("BEROEPENCLUSTER").AANTAL.sum().nlargest(4)
#     Chauffeurs goederenvervoer 423, Magazijnmedewerkers 353, Monteurs werktuigbouw 225, Productiemedewerkers 204
#   gemeente Almere: u[u.GEMEENTE == "Almere"].AANTAL.sum() → 2573; 241 clusters
#     Chauffeurs goederenvervoer 164, Magazijnmedewerkers 142, Klantenservice- en callcentermedewerkers 106,
#     Monteurs werktuigbouw 94


def test_uwv_vacatures_in_een_provincie():
    uit = json.loads(get_uwv_vacatures("Flevoland"))

    assert (uit["provincie"], uit["peildatum"], uit["totaal_vacatures"]) == ("Flevoland", "2023-05-16", 5848)
    assert list(uit["clusters"].items())[:4] == [
        ("Chauffeurs goederenvervoer", 423),
        ("Magazijnmedewerkers", 353),
        ("Monteurs werktuigbouw", 225),
        ("Productiemedewerkers", 204),
    ]
    assert uit["clusters_getoond"] == "de 15 grootste van 301 beroepenclusters"


def test_uwv_vacatures_in_een_gemeente():
    uit = json.loads(get_uwv_vacatures("Flevoland", gemeente="Almere"))

    assert (uit["gemeente"], uit["totaal_vacatures"]) == ("Almere", 2573)
    assert list(uit["clusters"].items())[:4] == [
        ("Chauffeurs goederenvervoer", 164),
        ("Magazijnmedewerkers", 142),
        ("Klantenservice- en callcentermedewerkers", 106),
        ("Monteurs werktuigbouw", 94),
    ]
    assert uit["clusters_getoond"] == "de 15 grootste van 241 beroepenclusters"


# Bron: ROA AIS 2030 (riodata roa.load("ais2030", "arbeidsmarkt"), versie v20251218), opgehaald 02-11-2026,
# gefilterd op regionaam Nederland, aggregatieniveau "opleidingsniveau (ONR2019)" en de indicatoren van de tool.
# Nagelezen met pandas: r = pd.read_csv(gz); r.pivot_table(index="detailniveau", columns="onderwerp",
# values=["perc", "aantal"]) en de kolom typering:
#                   werkloosheid  vast dienstverband  buiten vakrichting  baanopeningen  instroom  ITA 2030
#   Mbo2                       5                  81                  48         101500    130800  matig
#   Mbo3                       2                  86                  37         141000    168300  matig
#   Mbo4                       3                  81                  34         325800    358700  redelijk
#   Bachelor                   4                  65                  25         435600    533700  matig
#   Master, doctor             4                  49                  24         337900    285200  goed
_SIS = {
    "Mbo2": (5, 81, 48),
    "Mbo3": (2, 86, 37),
    "Mbo4": (3, 81, 34),
    "Bachelor": (4, 65, 25),
    "Master, doctor": (4, 49, 24),
}
_PROGNOSE = {
    "Mbo2": (101500, 130800, "matig"),
    "Mbo3": (141000, 168300, "matig"),
    "Mbo4": (325800, 358700, "redelijk"),
    "Bachelor": (435600, 533700, "matig"),
    "Master, doctor": (337900, 285200, "goed"),
}


def test_roa_benchmark_landelijk_per_opleidingsniveau():
    uit = json.loads(get_roa_benchmark())

    assert (uit["regio"], uit["versie"]) == ("Nederland", "v20251218")
    assert {
        niveau: tuple(w[i]["perc"] for i in ("werkloosheid", "vast dienstverband", "buiten de vakrichting"))
        for niveau, w in uit["schoolverlaters_sis_2024"].items()
    } == _SIS
    assert {
        niveau: (
            w["verwachte baanopeningen tot 2030"]["aantal"],
            w["verwachte instroom van schoolverlaters tot 2030"]["aantal"],
            w["ITA toekomstige arbeidsmarktsituatie in 2030"]["typering"],
        )
        for niveau, w in uit["prognose_tot_2030"].items()
    } == _PROGNOSE
