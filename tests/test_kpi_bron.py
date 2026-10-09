"""Eén lezer en één getalvergelijking voor compute_kpi-resultaten (#420, CH-13).

De tabellen hieronder zijn eerst groen gemaakt tegen de oude lezers (`met_periode`,
`kpi_scope._kpis`, `binding._kpis` en `kpi_periode.noemt`); daarna zijn alleen de
adapters omgezet. Zo blijft het gedrag van de controles gelijk.
"""

import json

import pytest

from agent.kpi_bron import kpis, noemt
from agent.kpi_periode import verkeerde_kpi_periodes

_SCHOOLJAREN = {"van": "2019/20", "tot": "2025/26"}


# --- adapters: de enige regels die meegaan met de lezer ---


def _met_periode(results: list[str]) -> list[str]:
    """De waarden die de periodelezers zien (kpi_periode, binding)."""
    return [kpi.waarde for kpi in kpis(results) if kpi.periode is not None]


def _met_bron(results: list[str]) -> list[str]:
    """De waarden die de scopelezer ziet (kpi_scope)."""
    return [kpi.waarde for kpi in kpis(results) if kpi.bron is not None]


def _kpi(waarde: str, periode: dict | None = None):
    [kpi] = kpis([json.dumps({"value": waarde, "periode": periode or _SCHOOLJAREN})])
    return kpi


def _cijfers(waarde: str) -> str | None:
    """De cijfers waarmee binding een KPI-waarde vergelijkt; None als die geen geheel getal is."""
    return _kpi(waarde).cijfers


def _bereik(periode: dict) -> tuple[int, int] | None:
    return _kpi("1", periode).bereik


def _noemt(segment: str, waarde: str) -> bool:
    return noemt(segment, _kpi(waarde))


# --- welke toolresultaten een KPI zijn ---

_BEURT = [
    "geen json",
    json.dumps([{"value": "+1"}]),
    json.dumps({"fout": "Kolom 'N' niet gevonden."}),
    json.dumps({"data_key": "duo:x", "rijen": [{"N": 29040}]}),
    json.dumps("+29.040"),
    json.dumps({"label": "Groei", "value": "+463", "bron": {"data_key": "duo:x", "aantal_waarden": 3893}}),
    json.dumps({"label": "WO", "value": "+29.040", "periode": _SCHOOLJAREN}),
    json.dumps(
        {
            "value": "-8.700",
            "periode": {"van": "2023/24", "tot": "2024/25"},
            "bron": {"data_key": "cbs:x", "metric": "delta"},
        }
    ),
]


def test_alleen_json_objecten_met_een_waarde_zijn_een_kpi():
    assert _met_periode(_BEURT[:5]) == []
    assert _met_bron(_BEURT[:5]) == []


def test_periode_is_optioneel_en_de_periodelezers_zien_alleen_kpis_met_periode():
    assert _met_periode(_BEURT) == ["+29.040", "-8.700"]


def test_bron_is_optioneel_en_de_scopelezer_ziet_alleen_kpis_met_bron():
    assert _met_bron(_BEURT) == ["+463", "-8.700"]


@pytest.mark.parametrize(
    ("waarde", "cijfers"),
    [
        ("+29.040", "29040"),
        ("−8.700", "8700"),  # Unicode-min
        ("-41.558", "41558"),
        ("+463", "463"),
        ("12%", "12"),
        ("9,6", None),
        ("+9,5%", None),
    ],
)
def test_cijfers_van_een_gehele_waarde_zonder_teken_of_procent(waarde, cijfers):
    assert _cijfers(waarde) == cijfers


def test_bereik_in_schooljaren():
    assert _bereik(_SCHOOLJAREN) == (2019, 2025)


def test_kalenderjaren_zijn_geen_schooljaarbereik():
    assert _bereik({"van": "2024", "tot": "2030"}) is None


# --- noemt: staat de KPI-waarde als los getal in de tekst? ---


@pytest.mark.parametrize(
    ("segment", "waarde", "genoemd"),
    [
        # Duizendtal met een punt of een (harde of smalle) spatie (#236).
        ("Het wo groeide met 29.040.", "+29.040", True),
        ("Het wo groeide met 29 040.", "+29.040", True),
        ("Het wo groeide met 29 040.", "+29.040", True),
        ("Het wo groeide met 29 040.", "+29.040", True),
        ("2024 tot 2030: -41 558", "-41.558", True),
        # Teken en procent tellen niet.
        ("Van 344.630 naar 335.930: -8.700.", "−8.700", True),
        ("Een daling van −8.700.", "-8.700", True),
        ("De groei was +463.", "+463", True),
        ("Dat is 12 procent.", "12%", True),
        ("Dat is 12 %.", "+12%", True),
        ("Van 2020/21 tot 2025/26: +9,5%.", "+9,5%", True),
        # Een ander getal dat de waarde bevat.
        ("Het gemiddelde was 9,60.", "9,6", False),
        ("Het gemiddelde was 19,6.", "9,6", False),
        ("Het verschil was 8.7000.", "8.700", False),
        ("Het verschil was 18.700.", "8.700", False),
        ("Het aantal was 4630 of 1463.", "463", False),
        ("Het aantal was 12,5.", "12", False),
        ("Het aantal was 1.234,5.", "1.234", False),
        ("Het aantal was 29.040.123.", "29.040", False),
        # Een punt met een cijfer erna: 12.5 is geen 12.
        ("Het aantal was 12.5.", "12", False),
        # Zonder duizendtalscheiding is het een ander getal: 2024 is geen KPI van 2.024.
        ("In 2024 steeg het aantal.", "+2.024", False),
        ("Het wo groeide met 29040.", "+29.040", False),
        # Zoals vóór #420: direct gevolgd door een komma telt niet, ook als leesteken.
        ("Het wo groeide met 29.040, vooral in de randstad.", "+29.040", False),
        # Markdown-nadruk met liggende streepjes is gewone tekst: de waarde staat er.
        ("Het wo groeide met _29.040_.", "+29.040", True),
        ("Het wo groeide met __29.040__.", "+29.040", True),
        ("Het steeg met _+9,5%_.", "+9,5%", True),
        # Zoals vóór #420: drie cijfers na een getal en een spatie zijn een duizendtal, ook na een jaartal.
        ("In 2024 463 studenten minder.", "-463", False),
        ("Het aantal steeg.", "+463", False),
    ],
)
def test_noemt(segment, waarde, genoemd):
    assert _noemt(segment, waarde) is genoemd


# --- noemt in de periodecontrole ---


def test_de_periodecontrole_ziet_een_kpi_met_markdown_nadruk():
    kpi = json.dumps({"value": "+29.040", "periode": {"van": "2019/20", "tot": "2024/25"}})
    tekst = "Van 2018/19 tot 2024/25 groeide het wo met _+29.040_ studenten."
    [probleem] = verkeerde_kpi_periodes(tekst, [kpi])
    assert "2019/20" in probleem
