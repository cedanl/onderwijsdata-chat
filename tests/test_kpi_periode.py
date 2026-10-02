"""Een KPI-getal met het periodebereik van de KPI, niet een zelfgekozen bereik (#235)."""

import json

from agent.kpi_periode import verkeerde_kpi_periodes

# Audit 10 (WO, Sonnet): +29.040 is 2019/20 → 2025/26; het antwoord schreef 2024/25.
_KPI = json.dumps(
    {
        "label": "WO",
        "value": "+29.040",
        "raw": 29040.0,
        "trend": "+29.040",
        "periode": {"van": "2019/20", "tot": "2025/26"},
        "bron": {"data_key": "cbs:x", "kolom": "N", "metric": "delta"},
    }
)
_PCT = json.dumps(
    {
        "label": "WO",
        "value": "+9,5%",
        "raw": 9.5,
        "periode": {"van": "2019/20", "tot": "2025/26"},
        "bron": {"data_key": "cbs:x", "kolom": "N", "metric": "pct_change"},
    }
)


def test_verkeerd_eindjaar_bij_een_kpi_is_een_probleem():
    [probleem] = verkeerde_kpi_periodes("2019/20 → 2024/25: +29.040 (+9,5%)", [_KPI])
    assert "2025/26" in probleem and "29.040" in probleem


def test_juist_bereik_is_goed():
    assert verkeerde_kpi_periodes("Van 2019/20 tot 2025/26 groeide het wo met +29.040.", [_KPI]) == []


def test_getal_zonder_plusteken_telt_ook():
    assert verkeerde_kpi_periodes("Tussen 2019/20 en 2024/25 kwamen er 29.040 bij.", [_KPI])


def test_percentage_kpi_wordt_ook_gecontroleerd():
    assert verkeerde_kpi_periodes("Van 2020/21 tot 2025/26: +9,5%.", [_PCT])


def test_een_genoemd_jaar_is_geen_bereik():
    # Eén schooljaar zegt niet over welk bereik de KPI gaat; daarover beslist binding.py.
    assert verkeerde_kpi_periodes("In 2025/26 was de groei +29.040.", [_KPI]) == []


def test_zin_zonder_het_kpi_getal_wordt_niet_gecontroleerd():
    assert verkeerde_kpi_periodes("Van 2019/20 tot 2024/25 steeg het aantal.", [_KPI]) == []


def test_ander_toolresultaat_wordt_genegeerd():
    andere = json.dumps({"data_key": "duo:x", "rijen": [{"N": 29040}]})
    assert verkeerde_kpi_periodes("2019/20 → 2024/25: +29.040", [andere, "geen json"]) == []
