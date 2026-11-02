"""Gouden tests voor elk recept van get_maat en voor compute_kpi op bevroren bronnen (#870).

Elk recept uit `tools.maten.MATEN` draait hier één keer of vaker op de echte bestanden van DUO en CBS, op 02-11-2026
live opgehaald met `scripts/gouden_testfixtures.py` (bron-URL's in `tests/fixtures/gouden/bronnen.json`). De fixture
`gouden` zet ze klaar en sluit het netwerk af. Niet de Hogeschool Utrecht: die heeft de live ijkwaarden van #190
(`tests/test_maten_ijk.py`). De verwachte waarden zijn met pandas op de bevroren bestanden nagerekend, buiten de tools
om; de berekening staat bij elke test.
"""

import json

import pytest

from tools import maten
from tools.kpi import compute_kpi
from tools.maten import get_maat

pytestmark = pytest.mark.usefixtures("gouden")

_UU = "Universiteit Utrecht"


def _uit(tekst: str) -> dict:
    uit = json.loads(tekst)
    assert "data_key" in uit, uit
    return uit


def _per_jaar(uit: dict) -> dict:
    return {r[uit["periodekolom"]]: r[uit["waardekolom"]] for r in uit["rijen"]}


def test_elk_recept_heeft_hier_een_gouden_test():
    """Een nieuw recept zonder gouden test valt hier op: voeg dan een fixture en een test toe."""
    getest = {
        maten.PERSONEN_HO,
        maten.INSCHRIJVINGEN_HO,
        maten.EERSTEJAARS_HO,
        maten.MBO_STUDENTEN,
        maten.DEELNEMERS_HO_LANDELIJK,
        maten.MBO_STUDENTEN_LANDELIJK,
        maten.DOORSTROOM_VMBO_MBO,
    }
    assert set(maten.MATEN) == getest


# --- DUO, per instelling --------------------------------------------------------------------------------------------
# Bron: DUO p01hoinges, p02ho1ejrs en p03hoinschr, bestand 4 ("… wetenschappelijk onderwijs inclusief
# opleidingsvorm"), versie van 08-04-2026, opgehaald 02-11-2026, gefilterd op INSTELLINGSCODE_ACTUEEL 21PD.
# Nagerekend met pandas:
#   df = pd.read_csv(gz); df.pivot_table(index="STUDIEJAAR", columns="OPLEIDINGSVORM", values=<telkolom>, aggfunc="sum")
# Elk bestand heeft één onderdrukte cel (-1), in DT: p01 en p03 in 2022, p02 in 2021. Bij voltijd valt die buiten de
# selectie; bij alle vormen telt de cel niet mee (de app maskeert -1), dus de som is 1 hoger dan de ruwe som met -1.
_PERSONEN_VT = {2021: 36534, 2022: 37317, 2023: 37910, 2024: 37357, 2025: 36769}
# Alle vormen: ruwe som 36932, 37673, 38288, 37701, 37099; 2022 zonder de -1: 37673 + 1 = 37674.
_PERSONEN_ALLE = {2021: 36932, 2022: 37674, 2023: 38288, 2024: 37701, 2025: 37099}
_EERSTEJAARS_VT = {2021: 5076, 2022: 5133, 2023: 5183, 2024: 5218, 2025: 4884}
_INSCHRIJVINGEN_VT = {2021: 38402, 2022: 39212, 2023: 39749, 2024: 39074, 2025: 38619}


@pytest.mark.parametrize(
    ("maat", "vorm", "verwacht"),
    [
        (maten.PERSONEN_HO, "voltijd", _PERSONEN_VT),
        (maten.PERSONEN_HO, "alle", _PERSONEN_ALLE),
        (maten.EERSTEJAARS_HO, "voltijd", _EERSTEJAARS_VT),
        (maten.INSCHRIJVINGEN_HO, "voltijd", _INSCHRIJVINGEN_VT),
    ],
)
def test_ho_recepten_per_studiejaar_universiteit_utrecht(maat, vorm, verwacht):
    uit = _uit(get_maat(maat, _UU, vorm=vorm))

    assert uit["instelling"]["instellingscode"] == "21PD"
    assert uit["recept"]["bestand"] == 4
    assert _per_jaar(uit) == verwacht


def test_een_gevraagd_schooljaar_selecteert_alleen_dat_jaar():
    uit = _uit(get_maat(maten.PERSONEN_HO, _UU, vorm="voltijd", schooljaren=["2024/25"]))
    assert _per_jaar(uit) == {2024: 37357}


# Bron: DUO mbo-studenten-per-instelling, bestand 0 (per instelling en leerweg), versie van 02-02-2026, opgehaald
# 02-11-2026. Nagerekend met pandas op de rijen van INSTELLINGSCODE 27GZ (ROC Mondriaan):
#   JAAR   BBL  BOLDT  BOLVT   EX    alle = BBL+BOLDT+BOLVT+EX   bol = BOLDT+BOLVT
#   2021  4507      0  15282  228    20017                       15282
#   2022  4610      0  14459  254    19323                       14459
#   2023  4500      0  13783  306    18589                       13783
#   2024  4339      0  13851  277    18467                       13851
#   2025  4468      0  14519  234    19221                       14519
@pytest.mark.parametrize(
    ("vorm", "verwacht"),
    [
        ("alle", {2021: 20017, 2022: 19323, 2023: 18589, 2024: 18467, 2025: 19221}),
        ("bol", {2021: 15282, 2022: 14459, 2023: 13783, 2024: 13851, 2025: 14519}),
        ("bbl", {2021: 4507, 2022: 4610, 2023: 4500, 2024: 4339, 2025: 4468}),
    ],
)
def test_mbo_studenten_per_instelling_roc_mondriaan(vorm, verwacht):
    uit = _uit(get_maat(maten.MBO_STUDENTEN, "ROC Mondriaan", vorm=vorm))

    assert uit["instelling"]["instellingscode"] == "27GZ"
    assert uit["waardekolom"] == maten.AANTAL
    assert _per_jaar(uit) == verwacht


# --- CBS, landelijk -------------------------------------------------------------------------------------------------
# Bron: CBS-OData, opgehaald 02-11-2026: de rijen die het recept opvraagt, met DataProperties, de dimensielabels en
# TableInfos. Nagerekend met pandas op de bevroren rijen (`pd.DataFrame(opname["rijen"])`), elke andere dimensie op
# de code van het recept:
#   85423NED TotaalIngeschrevenen_1, Opleidingsfase A045745, Geslacht T001038
#     hbo (A025294) alle (T001228): 2024SJ00 449930, 2025SJ00 440220; voltijd (A028666): 2024SJ00 378490
#     wo  (A025297) alle (T001228): 2024SJ00 341720, 2025SJ00 335930
#   85354NED MboStudenten_1, Leerweg A025290 (alle) / A041868 (bol) / A025293 (bbl)
#     2024SJ00: 475460 / 328610 / 137220; 2025SJ00: 475550 / 329710 / 137100
# Waar ze elkaar raken, zijn dit dezelfde getallen als de ijkwaarden van de kritieke evalset (tests/e2e/ijkwaarden.json:
# cbs-hbo-totaal-2024, cbs-hbo-voltijd-2024 en -2025, cbs-wo-totaal-2024, cbs-mbo-totaal-2024).
@pytest.mark.parametrize(
    ("maat", "args", "verwacht"),
    [
        (maten.DEELNEMERS_HO_LANDELIJK, {"sector": "hbo"}, {"2024SJ00": 449930, "2025SJ00": 440220}),
        (maten.DEELNEMERS_HO_LANDELIJK, {"sector": "hbo", "vorm": "voltijd"}, {"2024SJ00": 378490, "2025SJ00": 367960}),
        (maten.DEELNEMERS_HO_LANDELIJK, {"sector": "wo"}, {"2024SJ00": 341720, "2025SJ00": 335930}),
        (maten.MBO_STUDENTEN_LANDELIJK, {}, {"2024SJ00": 475460, "2025SJ00": 475550}),
        (maten.MBO_STUDENTEN_LANDELIJK, {"vorm": "bol"}, {"2024SJ00": 328610, "2025SJ00": 329710}),
        (maten.MBO_STUDENTEN_LANDELIJK, {"vorm": "bbl"}, {"2024SJ00": 137220, "2025SJ00": 137100}),
    ],
)
def test_landelijke_cbs_recepten(maat, args, verwacht):
    uit = _uit(get_maat(maat, schooljaren=["2024/25", "2025/26"], **args))

    assert uit["recept"]["bron"] == "cbs"
    assert _per_jaar(uit) == verwacht


# 85569NED InstromersTotaal_1: de som van MaatschappelijkePositie1JaarEerder A041923 (vmbo-b/k 3-4) en A041922
# (vmbo-g/t 3-4), per periode:
#   r.pivot(index="Perioden", columns="MaatschappelijkePositie1JaarEerder", values="InstromersTotaal_1").sum(axis=1)
#   2018: 47710 + 45590   2019: 46000 + 46220   2020: 44850 + 47460   2021: 42240 + 41850
#   2022: 39880 + 39980   2023: 38150 + 39890   2024: 41660 + 42770   2025: 39940 + 43080 (= 83020, ijkwaarde #667)
_DOORSTROOM = {
    "2018SJ00": 93300,
    "2019SJ00": 92220,
    "2020SJ00": 92310,
    "2021SJ00": 84090,
    "2022SJ00": 79860,
    "2023SJ00": 78040,
    "2024SJ00": 84430,
    "2025SJ00": 83020,
}


def test_doorstroom_vmbo_mbo_is_de_som_van_de_twee_vmbo_posities():
    uit = _uit(get_maat(maten.DOORSTROOM_VMBO_MBO))

    assert _per_jaar(uit) == _DOORSTROOM
    assert uit["recept"]["som"] == {"MaatschappelijkePositie1JaarEerder": ["A041923", "A041922"]}


# --- compute_kpi ----------------------------------------------------------------------------------------------------
# De reeks: ingeschreven personen voltijd van de Universiteit Utrecht (hierboven, _PERSONEN_VT), een aantal-kolom met
# één rij per studiejaar. Met de hand nagerekend over 2021/22 (36534) tot 2025/26 (36769):
#   delta      = 36769 - 36534             = 235
#   pct_change = (36769 / 36534 - 1) * 100 = 0,6432…  → +0,6%
#   index      = 36769 / 36534 * 100       = 100,6432… → 100,6
# en met van=2022, tot=2024 (37317 → 37357): delta 40.
@pytest.mark.parametrize(
    ("metric", "raw", "tekst"),
    [
        ("delta", 235, "+235"),
        ("pct_change", (36769 / 36534 - 1) * 100, "+0,6%"),
        ("index", 36769 / 36534 * 100, "100,6"),
    ],
)
def test_compute_kpi_over_een_reeks_met_bekende_uitkomst(metric, raw, tekst):
    key = _uit(get_maat(maten.PERSONEN_HO, _UU, vorm="voltijd"))["data_key"]

    uit = json.loads(compute_kpi(key, "AANTAL_INGESCHREVENEN", metric, sort_column="STUDIEJAAR"))

    assert uit["raw"] == pytest.approx(raw)
    assert uit["value"] == tekst
    assert uit["periode"] == {"van": "2021/22", "tot": "2025/26"}
    assert uit["bron"]["aantal_waarden"] == 5


def test_compute_kpi_binnen_een_bereik():
    key = _uit(get_maat(maten.PERSONEN_HO, _UU, vorm="voltijd"))["data_key"]

    uit = json.loads(compute_kpi(key, "AANTAL_INGESCHREVENEN", "delta", sort_column="STUDIEJAAR", van=2022, tot=2024))

    assert (uit["raw"], uit["periode"]) == (40, {"van": "2022/23", "tot": "2024/25"})
