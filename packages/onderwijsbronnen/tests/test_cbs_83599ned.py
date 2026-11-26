"""CBS 83599NED (openstaande vacatures; SBI 2008, regio) staat in de catalogus (#1223), zonder netwerk.

De arbeidsmarktdashboards lezen hun vacatures uit deze tabel (besluit #1221); de catalogus noemt titel, licentie,
frequentie en de laatste periode, en de Perioden-dimensie met de status per kwartaal (voorlopig of definitief).
"""

from onderwijsbronnen import cbs


def _record() -> dict:
    return next(r for r in cbs.catalog() if r["_cbs_id"] == "83599NED")


def test_titel_licentie_en_frequentie():
    record = _record()
    assert record["bron"] == "Openstaande vacatures; SBI 2008, regio"
    assert record["licentie"] == "CC BY 4.0"
    assert record["frequentie"] == "Perkwartaal"
    assert record["documentatie"]["url"] == "https://opendata.cbs.nl/ODataApi/OData/83599NED"


def test_kwartalen_vanaf_2011_met_de_laatste_periode():
    record = _record()
    assert record["_perioden_formaat"] == ["KW"]
    eerste, laatste = record["_periode_waarden"]
    assert eerste == "2011 1e kwartaal"
    assert laatste.endswith("kwartaal") and int(laatste[:4]) >= 2026


def test_provincie_en_bedrijfstak_als_dimensies():
    record = _record()
    assert "provincie" in record["_geo_niveau"]
    assert record["_dimensie_sleutels"]["Bedrijfstakken/Branches (SBI 2008)"] == "BedrijfstakkenBranchesSBI2008"
    assert record["_meetwaarden_details"]["OpenstaandeVacatures_1"]["unit"] == "x 1000"


def test_perioden_dragen_de_status_van_cbs():
    codes = cbs.get_dataset("83599NED")["perioden"]["codes"]["codes"]
    status = {c["code"]: c["status"] for c in codes}
    assert status["2011KW01"] == "Definitief"
    assert status[codes[-1]["code"]] == "Voorlopig"
