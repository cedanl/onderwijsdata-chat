"""Hoort het periodebereik in de tekst bij de KPI die het getal leverde? (#235)

De getalcontrole ziet dat +29.040 uit compute_kpi komt, maar niet over welke
jaren. Audit 10: "2019/20 → 2024/25: +29.040", terwijl de KPI 2019/20 → 2025/26
was. compute_kpi geeft die jaren nu mee als `periode`; noemt een zin het
KPI-getal samen met een bereik van schooljaren, dan moet dat bereik kloppen.
Eén genoemd schooljaar is geen bereik: daarover gaat binding.py. Een bereik mag ook in
kale jaartallen staan ("2024 tot 2030"); DUO-prognoses kennen geen schooljaarnotatie.
"""

from tools import periode

from .binding import segmenten
from .kpi_bron import kpis, noemt
from .probleem import Probleem


def verkeerde_kpi_periodes(tekst: str, tool_results: list[str]) -> list[str]:
    problemen = []
    for kpi in kpis(tool_results):
        if kpi.periode is None or kpi.bereik is None:
            continue
        van, tot = kpi.periode["van"], kpi.periode["tot"]
        for segment in segmenten(tekst):
            genoemd = periode.genoemd_bereik(segment)
            if genoemd is None or not noemt(segment, kpi):
                continue
            if genoemd != kpi.bereik:
                metric = (kpi.bron or {}).get("metric", "KPI")
                problemen.append(
                    Probleem(
                        f"{kpi.waarde} is de {metric} van {van} tot {tot}, maar de tekst noemt "
                        f"{periode.label(genoemd[0])} tot {periode.label(genoemd[1])}.",
                        "Die waarde komt uit compute_kpi: noem de periode uit `periode`.",
                    )
                )
    return list(dict.fromkeys(problemen))
