"""De `periode` van een CBS-tabel loopt niet achter op de bron (#1070).

`periode` is de tekst van CBS zelf (TableInfos `Period`), `_periode_waarden` komt uit de Perioden-dimensie. CBS zet
bij een nieuwe periode alleen de tabel bij; de tekst in de catalogus liep dan achter (85776NED: tekst tot 2022/'23,
tabel tot 2023/'24).
"""

import json
import sys
from pathlib import Path

import pytest

from onderwijsbronnen import cbs
from onderwijsbronnen.cbs import periode

CATALOGUS = Path(cbs.__file__).parent / "data"
sys.path.insert(0, str(Path(__file__).parent.parent / "catalogus" / "cbs"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.mark.parametrize(
    "tekst, jaar",
    [
        ("2006/'07-2023/'24", 2023),
        ("2015/'16-2025/26", 2025),
        ("2006/'07-2022/'2023", 2022),
        ("2013 - 2025", 2025),
        ("2013 1e kwartaal", 2013),
        ("2024/'25 naar 2025/'26", 2025),
        ("2015/'16 naar 2016/'17 t/m 2022/'23 naar 2023/'24", 2023),
        ("2007/8", 2007),
        ("2001 - 2006.", 2006),
        ("1 oktober 2013", 2013),
        # "tot" sluit het laatste jaar uit: 2021 tot 2026 is het blok 2021 t/m 2025.
        ("2021 tot 2026", 2025),
        ("1861 tot 1866", 1865),
        ("1999/'00 tot en met 2004/'05", 2004),
        ("", None),
        ("onbekend", None),
    ],
)
def test_eindjaar_is_het_laatste_jaar_van_de_tekst(tekst, jaar):
    assert periode.eindjaar(tekst) == jaar


def test_tekst_die_achterloopt_op_de_waarden():
    assert periode.loopt_achter({"periode": "2006/'07-2022/'23", "_periode_waarden": ["2006/'07", "2023/'24"]})


def test_tekst_die_bij_de_waarden_past_loopt_niet_achter():
    assert not periode.loopt_achter({"periode": "2006/'07-2023/'24", "_periode_waarden": ["2006/'07", "2023/'24"]})


@pytest.mark.parametrize(
    "record",
    [
        {"periode": "2008, 2010, 2012", "_periode_waarden": []},
        {"periode": "2023"},
        {"periode": "", "_periode_waarden": ["2023/'24"]},
        {"periode": "n.v.t.", "_periode_waarden": ["2023/'24"]},
    ],
    ids=["zonder waarden", "waarden ontbreken", "lege tekst", "tekst zonder jaar"],
)
def test_zonder_vergelijkbare_tekst_of_waarden_geen_oordeel(record):
    assert not periode.loopt_achter(record)


def test_geen_actuele_tabel_in_de_catalogus_loopt_achter():
    """Voor elke actuele CBS-tabel valt het eind van `periode` samen met de laatste periode van de tabel."""
    records = json.loads((CATALOGUS / "cbs_datasets_enriched.json").read_text(encoding="utf-8"))
    achter = [
        f"{r['_cbs_id']}: {r['periode']!r} naast {r['_periode_waarden'][-1]!r}"
        for r in records
        if not r.get("_archief") and periode.loopt_achter(r)
    ]
    assert achter == []


def test_elke_actuele_tabel_met_perioden_heeft_een_vergelijkbare_tekst():
    """Een tekst zonder jaar zou de controle hierboven stil laten slagen."""
    records = json.loads((CATALOGUS / "cbs_datasets_enriched.json").read_text(encoding="utf-8"))
    zonder = [
        r["_cbs_id"]
        for r in records
        if not r.get("_archief") and r.get("_periode_waarden") and periode.eindjaar(r.get("periode") or "") is None
    ]
    assert zonder == []


class TestBijTabel:
    """Loopt CBS zelf achter (de tekst zegt "2019", de tabel heeft ook 2025), dan volgt de tekst de tabel (#1070)."""

    def test_tekst_van_cbs_die_bij_de_tabel_past_blijft_staan(self):
        labels = ["2006/'07", "2007/'08", "2023/'24"]
        assert periode.bij_tabel("2006/'07-2023/'24", labels) == "2006/'07-2023/'24"

    def test_tekst_die_achterloopt_wordt_het_bereik_van_de_tabel(self):
        labels = ["2010/'11 naar 2011/'12", "2011/'12 naar 2012/'13", "2024/'25 naar 2025/'26"]
        assert periode.bij_tabel("2015/'16 naar 2016/'17 t/m 2023/'24 naar 2024/'25", labels) == (
            "2010/'11 naar 2011/'12 t/m 2024/'25 naar 2025/'26"
        )

    def test_tekst_die_later_begint_dan_de_tabel_wordt_het_bereik_van_de_tabel(self):
        labels = ["2011/'12", "2012/'13", "2025/'26"]
        assert periode.bij_tabel("2021/'22-2025/'26", labels) == "2011/'12-2025/'26"

    def test_een_tabel_met_twee_perioden_noemt_beide(self):
        assert periode.bij_tabel("2019", ["2019", "2025"]) == "2019 en 2025"

    def test_een_tabel_met_een_periode_noemt_die(self):
        assert periode.bij_tabel("", ["2024"]) == "2024"

    def test_zonder_perioden_van_de_tabel_blijft_de_tekst_staan(self):
        assert periode.bij_tabel("2008, 2010", []) == "2008, 2010"


class TestVersheid:
    """`perioden_verouderd` in /version telt ook een record waarvan de tekst achterloopt (#1070)."""

    @staticmethod
    def _info(status="ok"):
        return {"_cbs_id": "1", "bronmeta": {}, "perioden": {"status": status}}

    def test_achterlopende_tekst_telt_als_verouderd(self):
        from bouw_artefact import versheid

        records = [{"_cbs_id": "1", "periode": "2006/'07-2022/'23", "_periode_waarden": ["2006/'07", "2023/'24"]}]
        assert versheid(records, [self._info()])["perioden_verouderd"] == 1

    def test_verouderde_controle_en_achterlopende_tekst_tellen_een_keer(self):
        from bouw_artefact import versheid

        records = [{"_cbs_id": "1", "periode": "2006/'07-2022/'23", "_periode_waarden": ["2006/'07", "2023/'24"]}]
        assert versheid(records, [self._info("verouderd")])["perioden_verouderd"] == 1

    def test_een_gearchiveerde_tabel_telt_niet_mee(self):
        from bouw_artefact import versheid

        records = [
            {"_cbs_id": "1", "_archief": True, "periode": "2005 - 2013", "_periode_waarden": ["2005/'06", "2010/'11"]}
        ]
        assert versheid(records, [self._info()])["perioden_verouderd"] == 0


class TestBronvelden:
    """De wekelijkse controle haalt naast `_laatste_update` ook `periode` bij CBS: dezelfde aanroep."""

    def test_periode_en_wijzigingsdatum_komen_uit_tableinfos(self):
        from update_laatste_update import bronvelden

        waarde = {"Modified": "2026-09-15T02:00:00", "Period": " 2006/'07-2023/'24 "}
        assert bronvelden(waarde) == {"_laatste_update": "2026-09-15", "periode": "2006/'07-2023/'24"}

    def test_een_leeg_veld_overschrijft_niets(self):
        from update_laatste_update import bronvelden

        assert bronvelden({"Modified": "2026-09-15T02:00:00", "Period": ""}) == {"_laatste_update": "2026-09-15"}

    def test_alleen_een_gewijzigd_veld_wordt_teruggeschreven(self):
        from update_laatste_update import werk_bij

        ds = {"_laatste_update": "2026-09-15", "periode": "2006/'07-2022/'23"}
        gewijzigd = werk_bij(ds, {"_laatste_update": "2026-09-15", "periode": "2006/'07-2023/'24"})
        assert gewijzigd == ["periode"] and ds["periode"] == "2006/'07-2023/'24"
        assert werk_bij(ds, {"_laatste_update": "2026-09-15", "periode": "2006/'07-2023/'24"}) == []
