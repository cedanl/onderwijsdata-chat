"""De koppeltabel SBI-sectie → onderwijssector (#1224): volledig, één rij per sectie, elke dashboardsector gedekt.

De secties komen uit het opgenomen antwoord van CBS 83599NED (tests/fixtures/cbs/83599NED_provincies.json); de sectoren
die de dashboards tonen uit de indelingen van `data/sector_cluster_mapping.json` (hbo/wo: de onderdelen van DUO, mbo:
de hoofdgroepen).
"""

import json

import pytest

from data import arbeidsmarkt, sbi_koppeling
from tests import cbs_83599ned


def _secties_van_cbs() -> list[str]:
    titels = [r["Title"].strip() for r in cbs_83599ned.opname()["BedrijfstakkenBranchesSBI2008"]]
    return [code for code, _, _ in (t.partition(" ") for t in titels) if len(code) == 1]


def _dashboardsectoren() -> dict[str, list[str]]:
    indelingen = json.loads(arbeidsmarkt.SECTOR_CLUSTER_PATH.read_text())["_indelingen"]
    return {"mbo": indelingen["mbo"], "hbo": indelingen["hbo/wo"], "wo": indelingen["hbo/wo"]}


def test_elke_sbi_sectie_van_83599ned_heeft_precies_een_rij():
    secties = [r.sectie for r in sbi_koppeling.lees()]

    assert sorted(secties) == sorted(_secties_van_cbs())
    assert len(secties) == len(set(secties)) == 19


def test_namen_volgen_cbs():
    titels = {
        t.partition(" ")[0]: t.partition(" ")[2]
        for t in (r["Title"].strip() for r in cbs_83599ned.opname()["BedrijfstakkenBranchesSBI2008"])
    }
    assert {r.sectie: r.naam for r in sbi_koppeling.lees()} == {s: titels[s] for s in _secties_van_cbs()}


@pytest.mark.parametrize("niveau", sbi_koppeling.NIVEAUS)
def test_elke_dashboardsector_is_gekoppeld_of_bewust_niet(niveau):
    gekoppeld = set(sbi_koppeling.secties_per_sector(niveau))
    bewust_niet = set(sbi_koppeling.lees_zonder_koppeling()[niveau])

    assert not gekoppeld & bewust_niet, "een sector is gekoppeld én staat bij geen koppeling"
    assert set(_dashboardsectoren()[niveau]) <= gekoppeld | bewust_niet
    # Alleen sectoren die de dashboards kennen: een tikfout in de CSV koppelt anders een sector die niet bestaat.
    assert gekoppeld <= set(_dashboardsectoren()[niveau])


def test_elke_rij_heeft_een_reden_en_geen_koppeling_is_expliciet():
    rijen = sbi_koppeling.lees()
    assert all(r.reden for r in rijen)
    zonder = [r.sectie for r in rijen if not any(r.sectoren.values())]
    assert zonder == []  # elke sectie hoort bij minstens één niveau
    # N en S hebben voor hbo en wo bewust geen koppeling, met de reden in de rij.
    for sectie in ("N", "S"):
        (rij,) = [r for r in rijen if r.sectie == sectie]
        assert rij.sectoren["hbo"] == () and rij.sectoren["wo"] == ()
    ruw = sbi_koppeling.KOPPELTABEL.read_text(encoding="utf-8")
    assert ruw.count(sbi_koppeling.GEEN_KOPPELING) >= 5


def test_een_sectie_bij_meer_sectoren_telt_naar_rato():
    rijen = (
        sbi_koppeling.Rij("C", "Industrie", {"mbo": ("Techniek",), "hbo": ("TECHNIEK",), "wo": ()}, "r"),
        sbi_koppeling.Rij("M", "Zakelijk", {"mbo": (), "hbo": ("TECHNIEK", "ECONOMIE", "RECHT"), "wo": ()}, "r"),
        sbi_koppeling.Rij("S", "Overig", {"mbo": (), "hbo": (), "wo": ()}, "r"),
    )
    per_sector = sbi_koppeling.vacatures_per_sector({"C": 1000, "M": 900, "S": 500}, "hbo", rijen)

    assert per_sector == {"TECHNIEK": 1300, "ECONOMIE": 300, "RECHT": 300}
    assert sum(per_sector.values()) == 1000 + 900  # S hoort bij geen hbo-sector


def test_een_sectie_zonder_cijfer_telt_niet_als_nul():
    rijen = (sbi_koppeling.Rij("C", "Industrie", {"mbo": (), "hbo": ("TECHNIEK",), "wo": ()}, "r"),)
    assert sbi_koppeling.vacatures_per_sector({"C": None}, "hbo", rijen) == {}


@pytest.mark.parametrize(
    ("inhoud", "fout"),
    [
        ("sectie,naam,mbo,hbo,reden\nA,X,a,b,r\n", "kolommen"),
        ("sectie,naam,mbo,hbo,wo,reden\nA,X,a,b,c,\n", "reden"),
        ("sectie,naam,mbo,hbo,wo,reden\nA,X,a,b,c,r\nA,X,a,b,c,r\n", "meer dan één rij"),
        ("sectie,naam,mbo,hbo,wo,reden\nA,X,,b,c,r\n", "lege sector"),
    ],
)
def test_de_lader_valideert(tmp_path, inhoud, fout):
    pad = tmp_path / "koppeltabel.csv"
    pad.write_text(inhoud, encoding="utf-8")
    with pytest.raises(sbi_koppeling.OngeldigeKoppeltabel, match=fout):
        sbi_koppeling.lees(pad)


@pytest.mark.parametrize(
    ("type_", "soort", "niveau"), [("mbo", None, "mbo"), ("ho", "wo", "wo"), ("ho", "hbo", "hbo"), ("ho", None, "hbo")]
)
def test_niveau_van(type_, soort, niveau):
    assert sbi_koppeling.niveau_van(type_, soort) == niveau
