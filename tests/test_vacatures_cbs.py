"""De lader van CBS 83599NED (#1223): per provincie en SBI-sectie het laatste kwartaal en het gemiddelde van vier.

Alles uit het opgenomen OData-antwoord (tests/fixtures/cbs/83599NED_provincies.json, 26-11-2026), zonder netwerk. Utrecht,
alle economische activiteiten (A-U), in duizendtallen: 34,8 (2025 kw4), 35,3, 35,9 en 34,4 (2026 kw3). CBS noemt elk
kwartaal vanaf 2022 voorlopig.
"""

import pytest

from core import brongebruik
from data import vacatures_cbs
from tests import cbs_83599ned


def _sectie(stand, code):
    return next(s for s in stand.secties if s.code == code)


def test_laatste_kwartaal_en_gemiddelde_van_vier_als_aantal(cbs_vacatures):
    stand = vacatures_cbs.stand("Utrecht")

    assert stand is not None
    assert stand.laatste.titel == "2026 3e kwartaal"
    assert stand.totaal.laatste.vacatures == 34_400
    assert stand.totaal.laatste.als_dict()["periode"] == "2026 3e kwartaal"
    # (34,8 + 35,3 + 35,9 + 34,4) / 4 = 35,1 duizend
    assert stand.totaal.gemiddelde.vacatures == 35_100
    assert [p.titel for p in stand.gemiddeld_over] == [
        "2025 4e kwartaal",
        "2026 1e kwartaal",
        "2026 2e kwartaal",
        "2026 3e kwartaal",
    ]
    assert stand.totaal.gemiddelde.als_dict()["periode"] == "2025 4e kwartaal t/m 2026 3e kwartaal"
    # Q Gezondheids- en welzijnszorg: 6,5, 6,2, 6,8 en 6,6 duizend
    zorg = _sectie(stand, "Q")
    assert (zorg.naam, zorg.laatste.vacatures, zorg.gemiddelde.vacatures) == (
        "Gezondheids- en welzijnszorg",
        6_600,
        6_525,
    )


def test_de_lader_vraagt_alle_kwartalen_van_de_provincies(cbs_vacatures):
    vacatures_cbs.stand("Utrecht")

    # Eén $filter op de provincies, geen filter op de perioden: alle kwartalen vanaf 2011 kw1.
    assert cbs_vacatures and all(p["$filter"] == cbs_83599ned.FILTER for p in cbs_vacatures)
    assert vacatures_cbs.API_URL == "https://opendata.cbs.nl/ODataApi/odata/83599NED"


def test_twaalf_provincies_en_negentien_secties(cbs_vacatures):
    assert len(vacatures_cbs.provincies()) == 12
    stand = vacatures_cbs.stand("Groningen")
    assert stand is not None
    assert [s.code for s in stand.secties] == list("ABCDEFGHIJKLMNOPQRS")
    assert stand.totaal.code == "A-U"


@pytest.mark.parametrize("naam", ["Friesland", "Fryslân", "fryslan"])
def test_friesland_heet_bij_cbs_fryslan(cbs_vacatures, naam):
    stand = vacatures_cbs.stand(naam)
    assert stand is not None and stand.provincie == "Fryslân"


def test_onbekende_provincie_is_none(cbs_vacatures):
    assert vacatures_cbs.stand("Atlantis") is None


def test_voorlopige_perioden_zijn_gemarkeerd(cbs_vacatures):
    stand = vacatures_cbs.stand("Utrecht")

    assert stand is not None
    assert stand.laatste.voorlopig and all(p.voorlopig for p in stand.gemiddeld_over)
    assert stand.totaal.laatste.status == vacatures_cbs.VOORLOPIG
    assert stand.totaal.laatste.als_dict()["voorlopig"] is True


def test_een_definitief_kwartaal_is_niet_voorlopig(monkeypatch):
    def definitief(bron):
        for periode in bron["Perioden"]:
            periode["Status"] = "Definitief"

    cbs_83599ned.zet_klaar(monkeypatch, definitief)
    try:
        stand = vacatures_cbs.stand("Utrecht")
        assert stand is not None
        assert stand.totaal.laatste.status == vacatures_cbs.DEFINITIEF
        assert stand.totaal.gemiddelde.voorlopig is False
    finally:
        vacatures_cbs._tabel.cache_clear()


def test_de_voorlopig_markering_gaat_mee_naar_het_bronblok(cbs_vacatures):
    with brongebruik.verzamel() as gemeld:
        vacatures_cbs.stand("Utrecht")

    (melding,) = [m for m in gemeld if m["dataset"] == "83599NED"]
    assert melding["bron"] == "CBS"
    assert melding["licentie"] == "CC BY 4.0"
    assert melding["laatste_periode"] == "2026 3e kwartaal"
    assert melding["voorlopig_perioden"] == melding["gemiddeld_over"]
    assert melding["peildatum"] == "2026-09-30"


def _leeg(regio: str, sbi: str, periode: str, weg: bool = False):
    def aanpassen(bron):
        rijen = bron["TypedDataSet"]
        for rij in list(rijen):
            if (rij["RegioS"].strip(), rij["BedrijfstakkenBranchesSBI2008"].strip(), rij["Perioden"]) == (
                regio,
                sbi,
                periode,
            ):
                if weg:
                    rijen.remove(rij)
                else:
                    rij["OpenstaandeVacatures_1"] = None

    return aanpassen


@pytest.mark.parametrize("weg", [False, True], ids=["lege cel", "ontbrekende rij"])
def test_lege_cel_is_geen_gegevens_nooit_nul(monkeypatch, weg):
    # Utrecht (PV26), C Industrie (307500), het laatste kwartaal.
    cbs_83599ned.zet_klaar(monkeypatch, _leeg("PV26", "307500", "2026KW03", weg))
    try:
        stand = vacatures_cbs.stand("Utrecht")
        assert stand is not None
        industrie = _sectie(stand, "C")
        assert industrie.laatste.vacatures is None and industrie.laatste.status == vacatures_cbs.GEEN_GEGEVENS
        # Een gemiddelde over minder kwartalen is een ander getal: ook geen gegevens.
        assert industrie.gemiddelde.vacatures is None
        assert industrie.gemiddelde.als_dict()["status"] == "geen gegevens"
        # De rest van de provincie heeft gewoon cijfers.
        assert stand.totaal.laatste.vacatures == 34_400
    finally:
        vacatures_cbs._tabel.cache_clear()


def test_een_nul_van_cbs_blijft_nul(cbs_vacatures):
    # B Delfstoffenwinning in Utrecht: CBS geeft 0,0 (minder dan 50 vacatures); dat is een cijfer, geen lege cel.
    stand = vacatures_cbs.stand("Utrecht")
    assert stand is not None
    delfstoffen = _sectie(stand, "B")
    assert delfstoffen.laatste.vacatures == 0 and delfstoffen.laatste.status == vacatures_cbs.VOORLOPIG


@pytest.mark.parametrize(
    ("code", "einde"),
    [("2026KW03", "2026-09-30"), ("2025KW04", "2025-12-31"), ("2024KW01", "2024-03-31"), ("2026JJ00", None)],
)
def test_kwartaal_einde(code, einde):
    assert vacatures_cbs.kwartaal_einde(code) == einde
