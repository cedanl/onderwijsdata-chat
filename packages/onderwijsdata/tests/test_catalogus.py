"""
Tests voor pure catalogus-helperfuncties.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "catalogus"))

import pytest
from catalogus import _infer_perioden_formaat, _infer_geo_niveau, to_data_json_entry


# ── _infer_perioden_formaat ──────────────────────────────────────────────────

class TestInferPeriodFormaat:
    def test_schooljaar_voor_po_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "Primair onderwijs") == ["SJ"]

    def test_schooljaar_voor_vo_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "Voortgezet onderwijs") == ["SJ"]

    def test_schooljaar_voor_mbo_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "Middelbaar beroepsonderwijs") == ["SJ"]

    def test_schooljaar_voor_ho_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "Hoger onderwijs") == ["SJ"]

    def test_schooljaar_voor_volwassenen_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "Volwasseneneducatie") == ["SJ"]

    def test_schooljaar_voor_mbo_studenten_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "Mbo studenten") == ["SJ"]

    def test_schooljaar_voor_onderwijs_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "Onderwijs") == ["SJ"]

    def test_schooljaar_voor_vo_leerlingen_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "Vo leerlingen") == ["SJ"]

    def test_kalenderjaar_voor_financiering_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "Financiering en uitgaven onderwijs") == ["JJ"]

    def test_kalenderjaar_voor_arbeidsmarkt_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "Onderwijs en arbeidsmarkt") == ["JJ"]

    def test_kalenderjaar_voor_bevolking_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "Onderwijsniveau bevolking") == ["JJ"]

    def test_kwartaal(self):
        assert _infer_perioden_formaat("Kwartaal", "Primair onderwijs") == ["KW"]

    def test_maand(self):
        assert _infer_perioden_formaat("Maandelijks", "Onderwijs") == ["MM"]

    def test_stopgezet_leeg(self):
        assert _infer_perioden_formaat("Stopgezet", "Primair onderwijs") == []

    def test_stopgezet_case_insensitive(self):
        assert _infer_perioden_formaat("stopgezet", "Hoger onderwijs") == []

    def test_case_insensitive_thema(self):
        assert _infer_perioden_formaat("Jaarlijks", "FINANCIERING EN UITGAVEN ONDERWIJS") == ["JJ"]

    def test_kwartaal_beats_thema(self):
        assert _infer_perioden_formaat("Kwartaal", "Financiering en uitgaven onderwijs") == ["KW"]


# ── _infer_geo_niveau ────────────────────────────────────────────────────────

class TestInferGeoNiveau:
    def test_geen_regios_als_geen_dim(self):
        assert _infer_geo_niveau("Mbo studenten", []) == []

    def test_geen_regios_als_geen_regios_dim(self):
        assert _infer_geo_niveau("Mbo studenten regio", ["Geslacht", "Perioden"]) == []

    def test_regiokenmerken_geeft_meest_granulaire(self):
        result = _infer_geo_niveau(
            "Mbo; studenten, niveau, leerweg, studierichting, regiokenmerken",
            ["Geslacht", "RegioS", "Niveau", "Perioden"],
        )
        assert result == ["landelijk", "corop", "provincie", "gemeente"]

    def test_woonregio_geeft_provincie_gemeente(self):
        result = _infer_geo_niveau(
            "Gediplomeerden; onderwijssoort, woonregio",
            ["Onderwijssoort", "Geslacht", "RegioS", "Perioden"],
        )
        assert result == ["landelijk", "provincie", "gemeente"]

    def test_gemeente_in_bron(self):
        result = _infer_geo_niveau(
            "Po; leerlingen per gemeente",
            ["RegioS", "Perioden"],
        )
        assert result == ["gemeente"]

    def test_provincie_in_bron(self):
        result = _infer_geo_niveau(
            "Vo; leerlingen per provincie",
            ["RegioS", "Perioden"],
        )
        assert result == ["provincie"]

    def test_fallback_geeft_landelijk_provincie(self):
        result = _infer_geo_niveau(
            "Mbo studenten aantallen",
            ["RegioS", "Perioden"],
        )
        assert result == ["landelijk", "provincie"]

    def test_case_insensitive_bron(self):
        result = _infer_geo_niveau(
            "Studenten; REGIOKENMERKEN",
            ["RegioS"],
        )
        assert result == ["landelijk", "corop", "provincie", "gemeente"]


# ── to_data_json_entry nieuwe velden ─────────────────────────────────────────

class TestToDataJsonEntry:
    def _make_info(self, title="Test dataset", freq="Jaarlijks", period="2020-2024", modified="2024-01-01"):
        return {"Title": title, "Frequency": freq, "Period": period, "Modified": modified}

    def test_bevat_dimensies(self):
        entry = to_data_json_entry(
            "TEST01NED",
            self._make_info(),
            ["Geslacht", "RegioS", "Perioden"],
            ["Deelnemers"],
            "Primair onderwijs",
        )
        assert entry["_dimensies"] == ["Geslacht", "RegioS", "Perioden"]

    def test_bevat_meetwaarden(self):
        entry = to_data_json_entry(
            "TEST01NED",
            self._make_info(),
            ["Geslacht", "Perioden"],
            ["Deelnemers", "Gediplomeerden"],
            "Primair onderwijs",
        )
        assert entry["_meetwaarden"] == ["Deelnemers", "Gediplomeerden"]

    def test_perioden_formaat_schooljaar(self):
        entry = to_data_json_entry(
            "TEST01NED",
            self._make_info(),
            ["Geslacht", "Perioden"],
            ["Deelnemers"],
            "Primair onderwijs",
        )
        assert entry["_perioden_formaat"] == ["SJ"]

    def test_perioden_formaat_kalenderjaar(self):
        entry = to_data_json_entry(
            "TEST01NED",
            self._make_info(),
            ["Geslacht", "Perioden"],
            ["Bedrag"],
            "Financiering en uitgaven onderwijs",
        )
        assert entry["_perioden_formaat"] == ["JJ"]

    def test_geo_niveau_met_regiokenmerken(self):
        entry = to_data_json_entry(
            "TEST01NED",
            self._make_info(title="Mbo; studenten, regiokenmerken"),
            ["Geslacht", "RegioS", "Perioden"],
            ["Deelnemers"],
            "Middelbaar beroepsonderwijs",
        )
        assert entry["_geo_niveau"] == ["landelijk", "corop", "provincie", "gemeente"]

    def test_geo_niveau_leeg_zonder_regios(self):
        entry = to_data_json_entry(
            "TEST01NED",
            self._make_info(title="Mbo studenten nationaal"),
            ["Geslacht", "Perioden"],
            ["Deelnemers"],
            "Middelbaar beroepsonderwijs",
        )
        assert entry["_geo_niveau"] == []

    def test_stopgezet_geeft_lege_perioden(self):
        entry = to_data_json_entry(
            "TEST01NED",
            self._make_info(freq="Stopgezet"),
            [],
            [],
            "Primair onderwijs",
        )
        assert entry["_perioden_formaat"] == []

    def test_bestaande_velden_ongewijzigd(self):
        entry = to_data_json_entry(
            "TEST01NED",
            self._make_info(),
            [],
            [],
            "Primair onderwijs",
        )
        assert entry["leverancier"] == "CBS"
        assert "_cbs_id" in entry
        assert "_archief" in entry
