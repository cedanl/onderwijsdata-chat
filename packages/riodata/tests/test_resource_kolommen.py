"""
Tests voor de multi-resource _kolommen structuurlogica
uit catalogus/update_duo_resource_kolommen.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "catalogus"))

from update_duo_resource_kolommen import _build_kolommen_dict, _parse_csv_header


class TestBuildKolommenDict:
    """Tests voor _build_kolommen_dict: puur, geen netwerk nodig."""

    def _r(self, naam: str) -> dict:
        return {"naam": naam, "url": f"https://example.com/{naam}.csv", "format": "CSV", "id": naam}

    def test_enkele_resource_blijft_list(self):
        # Single-resource: geen dict nodig, maar de functie wordt niet aangeroepen
        # voor single resources. Test dat de helper correct handelt bij 1 resource.
        resources = [self._r("Dataset A")]
        fetched = {"Dataset A": ["COL1", "COL2"]}
        result = _build_kolommen_dict(resources, fetched, fallback=["COL1", "COL2"])
        assert isinstance(result, dict)
        assert result == {"Dataset A": ["COL1", "COL2"]}

    def test_multi_resource_geeft_dict(self):
        resources = [self._r("Dataset A"), self._r("Dataset B")]
        fetched = {"Dataset A": ["COL1", "COL2"], "Dataset B": ["COL3", "COL4"]}
        result = _build_kolommen_dict(resources, fetched, fallback=["OLD"])
        assert isinstance(result, dict)
        assert result == {"Dataset A": ["COL1", "COL2"], "Dataset B": ["COL3", "COL4"]}

    def test_gedeeltelijk_ophalen_resource0_fallback(self):
        # Dataset B kon niet worden opgehaald
        resources = [self._r("Dataset A"), self._r("Dataset B")]
        fetched = {"Dataset A": ["COL1", "COL2"]}
        result = _build_kolommen_dict(resources, fetched, fallback=["ORIGINAL"])
        assert result["Dataset A"] == ["COL1", "COL2"]
        assert result["Dataset B"] == []

    def test_geen_ophalen_resource0_krijgt_fallback(self):
        # Niets kon worden opgehaald → resource 0 krijgt de bestaande _kolommen
        resources = [self._r("Dataset A"), self._r("Dataset B")]
        fetched = {}
        result = _build_kolommen_dict(resources, fetched, fallback=["ORIGINAL_COL1", "ORIGINAL_COL2"])
        assert result["Dataset A"] == ["ORIGINAL_COL1", "ORIGINAL_COL2"]
        assert result["Dataset B"] == []

    def test_drie_resources_gedeeltelijk(self):
        resources = [self._r("A"), self._r("B"), self._r("C")]
        fetched = {"A": ["X", "Y"], "C": ["Z"]}
        result = _build_kolommen_dict(resources, fetched, fallback=["OLD"])
        assert result["A"] == ["X", "Y"]
        assert result["B"] == []
        assert result["C"] == ["Z"]

    def test_lege_resources_lijst(self):
        result = _build_kolommen_dict([], {}, fallback=[])
        assert result == {}


class TestParseCsvHeader:
    """Tests voor _parse_csv_header: puur CSV-parsing."""

    def test_standaard_komma_separator(self):
        tekst = '"COL1","COL2","COL3"\n"val1","val2","val3"\n'
        result = _parse_csv_header(tekst)
        assert result == ["COL1", "COL2", "COL3"]

    def test_punkomma_separator(self):
        tekst = "COL1;COL2;COL3\nval1;val2;val3\n"
        result = _parse_csv_header(tekst)
        assert result == ["COL1", "COL2", "COL3"]

    def test_aanhalingstekens_worden_gestript(self):
        tekst = '"ONDERWIJSSECTOR";"JAAR";"NAAM"\n'
        result = _parse_csv_header(tekst)
        assert result == ["ONDERWIJSSECTOR", "JAAR", "NAAM"]

    def test_lege_tekst(self):
        result = _parse_csv_header("")
        assert result == []

    def test_alleen_newlines(self):
        result = _parse_csv_header("\n\n\n")
        assert result == []

    def test_tab_separator(self):
        tekst = "COL1\tCOL2\tCOL3\nval1\tval2\tval3\n"
        result = _parse_csv_header(tekst)
        assert result == ["COL1", "COL2", "COL3"]

    def test_echte_duo_header(self):
        tekst = (
            '"STUDIEJAAR","PROVINCIENAAM","GEMEENTENUMMER","GEMEENTENAAM",'
            '"SOORT_INSTELLING","TYPE_HOGER_ONDERWIJS"\n'
            '"2021","Drenthe","0114","Emmen","reguliere inst.","associate degree"\n'
        )
        result = _parse_csv_header(tekst)
        assert result == [
            "STUDIEJAAR", "PROVINCIENAAM", "GEMEENTENUMMER", "GEMEENTENAAM",
            "SOORT_INSTELLING", "TYPE_HOGER_ONDERWIJS",
        ]

    def test_bom_header(self):
        # CSV met UTF-8 BOM
        tekst = "﻿COL1,COL2,COL3\nval1,val2,val3\n"
        result = _parse_csv_header(tekst)
        assert result == ["COL1", "COL2", "COL3"]
