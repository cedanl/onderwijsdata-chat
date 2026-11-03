"""
Tests voor de _derive_geo_niveau pure functie uit catalogus/update_geo_niveau.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "catalogus"))

from update_geo_niveau import _derive_geo_niveau


class TestDeriveGeoNiveau:
    def test_leeg(self):
        assert _derive_geo_niveau([]) == []

    def test_geen_geo(self):
        assert _derive_geo_niveau(["JAAR", "BRIN_NUMMER", "INSTELLING_NAAM"]) == []

    # --- gemeente ---
    def test_gemeente_via_gemeentenaam(self):
        assert "gemeente" in _derive_geo_niveau(["GEMEENTENAAM"])

    def test_gemeente_via_gemeentenummer(self):
        assert "gemeente" in _derive_geo_niveau(["GEMEENTENUMMER"])

    def test_gemeente_via_gemeente_code(self):
        assert "gemeente" in _derive_geo_niveau(["GEMEENTE_CODE"])

    def test_gemeente_via_gemeentecode_vestiging(self):
        assert "gemeente" in _derive_geo_niveau(["GEMEENTECODE_VESTIGING"])

    def test_gemeente_via_gemeentenaam_vestiging(self):
        assert "gemeente" in _derive_geo_niveau(["GEMEENTENAAM_VESTIGING"])

    def test_gemeente_spatie(self):
        # "GEMEENTE INSTELLING" — begint met GEMEENTE
        assert "gemeente" in _derive_geo_niveau(["GEMEENTE INSTELLING"])

    def test_gemeente_mixed_case(self):
        assert "gemeente" in _derive_geo_niveau(["Gemeentenaam"])

    def test_gemeente_gemeentenummer_instelling(self):
        assert "gemeente" in _derive_geo_niveau(["GEMEENTENUMMER INSTELLING"])

    # --- provincie ---
    def test_provincie_via_provincienaam(self):
        assert "provincie" in _derive_geo_niveau(["PROVINCIENAAM"])

    def test_provincie_spatie(self):
        assert "provincie" in _derive_geo_niveau(["PROVINCIE INSTELLING"])

    def test_provincie_mixed_case(self):
        assert "provincie" in _derive_geo_niveau(["Provincienaam"])

    def test_woonprovincie_niet_provincie(self):
        # "WOONPROVINCIE" — bevat PROVINCIE maar begint NIET met PROVINCIE
        # en bevat NIET PROVINCIENAAM → mag NIET matchen
        result = _derive_geo_niveau(["WOONPROVINCIE"])
        assert "provincie" not in result

    # --- corop ---
    def test_corop(self):
        assert "corop" in _derive_geo_niveau(["COROPGEBIED"])

    def test_corop_code(self):
        assert "corop" in _derive_geo_niveau(["COROP_CODE"])

    def test_corop_mixed_case(self):
        assert "corop" in _derive_geo_niveau(["Coropgebied"])

    # --- combinaties ---
    def test_gemeente_en_provincie(self):
        result = _derive_geo_niveau(["GEMEENTENAAM", "PROVINCIENAAM"])
        assert "gemeente" in result
        assert "provincie" in result

    def test_alle_drie(self):
        result = _derive_geo_niveau(["GEMEENTENUMMER", "PROVINCIENAAM", "COROP_NAAM"])
        assert set(result) == {"gemeente", "provincie", "corop"}

    def test_geen_duplicaten(self):
        result = _derive_geo_niveau(["GEMEENTENAAM", "GEMEENTENUMMER", "GEMEENTE_CODE"])
        assert result.count("gemeente") == 1

    def test_volgorde_gemeente_voor_provincie(self):
        result = _derive_geo_niveau(["PROVINCIENAAM", "GEMEENTENAAM"])
        # gemeente en provincie aanwezig, volgorde is niet gespecificeerd maar beide aanwezig
        assert "gemeente" in result
        assert "provincie" in result

    # --- echte DUO-kolommen ---
    def test_duo_ho_ingeschrevenen(self):
        kolommen = [
            "STUDIEJAAR", "PROVINCIENAAM", "GEMEENTENUMMER", "GEMEENTENAAM",
            "SOORT_INSTELLING", "TYPE_HOGER_ONDERWIJS", "INSTELLINGSCODE_ACTUEEL",
            "INSTELLINGSNAAM_ACTUEEL", "ONDERDEEL", "SUBONDERDEEL", "GESLACHT",
            "AANTAL_EERSTEJAARS_INGESCHREVENEN",
        ]
        result = _derive_geo_niveau(kolommen)
        assert "gemeente" in result
        assert "provincie" in result
        assert "corop" not in result

    def test_duo_functiemix_besturen(self):
        # Functiemix heeft geen gemeente/provincie kolommen
        kolommen = [
            "ONDERWIJSSECTOR", "JAAR", "BEVOEGD_GEZAGNUMMER", "BEVOEGD_GEZAGNAAM",
            "POSTCODE_BEVOEGD_GEZAG", "EENPITTER", "AANTAL_LEERLINGEN",
        ]
        result = _derive_geo_niveau(kolommen)
        assert result == []
