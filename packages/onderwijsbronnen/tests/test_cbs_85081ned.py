"""CBS 85081NED (ontstane vacatures; BRC 2014, SBI 2008) staat in de catalogus (#1227), zonder netwerk.

De chat geeft met deze tabel de ontstane vacatures per jaar en beroep (besluit #1221): landelijk, per beroepsklasse of
-segment van de BRC 2014. De catalogus noemt titel, licentie, frequentie, de eenheid van de meetwaarde en de Perioden
met hun status (voorlopig of definitief).
"""

from onderwijsbronnen import cbs


def _record() -> dict:
    return next(r for r in cbs.catalog() if r["_cbs_id"] == "85081NED")


def test_titel_licentie_en_frequentie():
    record = _record()
    assert record["bron"] == "Ontstane vacatures; beroepenindeling ROA-CBS 2014 (BRC 2014), SBI 2008"
    assert record["licentie"] == "CC BY 4.0"
    assert record["frequentie"] == "Perjaar"
    assert record["documentatie"]["url"] == "https://opendata.cbs.nl/ODataApi/OData/85081NED"


def test_jaren_vanaf_2018_in_duizendtallen():
    record = _record()
    assert record["_perioden_formaat"] == ["JJ"]
    eerste, laatste = record["_periode_waarden"]
    assert eerste == "2018" and int(laatste) >= 2025
    assert record["_meetwaarden_details"]["OntstaneVacatures_1"]["unit"] == "x 1 000"


def test_beroep_en_bedrijfstak_als_dimensies_en_landelijk():
    record = _record()
    assert record["_dimensie_sleutels"]["Beroepenindeling"] == "Beroepenindeling"
    assert record["_dimensie_sleutels"]["Bedrijfstakken/branches (SBI2008)"] == "BedrijfstakkenBranchesSBI2008"
    assert record["_geo_niveau"] == []  # geen regio-dimensie: landelijk


def test_perioden_dragen_de_status_van_cbs():
    codes = cbs.get_dataset("85081NED")["perioden"]["codes"]["codes"]
    assert codes[0]["code"] == "2018JJ00"
    assert {c["status"] for c in codes} <= {"Voorlopig", "Definitief", "Nader voorlopig"}
