"""Hoort het periodebereik in de tekst bij de KPI die het getal leverde? (#235)

De getalcontrole ziet dat +29.040 uit compute_kpi komt, maar niet over welke
jaren. Audit 10: "2019/20 → 2024/25: +29.040", terwijl de KPI 2019/20 → 2025/26
was. compute_kpi geeft die jaren nu mee als `periode`; noemt een zin het
KPI-getal samen met een bereik van schooljaren, dan moet dat bereik kloppen.
Eén genoemd schooljaar is geen bereik: daarover gaat binding.py. Een bereik mag ook in
kale jaartallen staan ("2024 tot 2030"); DUO-prognoses kennen geen schooljaarnotatie.
"""

import re

from tools import periode

from .binding import segmenten
from .kpi_bron import bereik as kpi_bereik
from .kpi_bron import met_periode
from .probleem import Probleem

# Duizendtallen met (harde of smalle) spatie, zoals gpt-oss ze schrijft (#236).
_SPATIE_DUIZENDTAL = re.compile(r"(?<=\d)[ \u00a0\u202f](?=\d{3}(?!\d))")


def noemt(segment: str, waarde: str) -> bool:
    """Staat de KPI-waarde (zonder teken of %) als los getal in het segment?"""
    kaal = waarde.lstrip("+-−").rstrip("%")
    segment = _SPATIE_DUIZENDTAL.sub(".", segment)
    return re.search(rf"(?<![\d.,]){re.escape(kaal)}(?![\d,]|\.\d)", segment) is not None


def verkeerde_kpi_periodes(tekst: str, tool_results: list[str]) -> list[str]:
    problemen = []
    for kpi in met_periode(tool_results):
        van, tot = kpi["periode"]["van"], kpi["periode"]["tot"]
        bereik = kpi_bereik(kpi)
        if bereik is None:
            continue
        for segment in segmenten(tekst):
            genoemd = periode.genoemd_bereik(segment)
            if genoemd is None or not noemt(segment, kpi["value"]):
                continue
            if genoemd != bereik:
                metric = kpi.get("bron", {}).get("metric", "KPI")
                problemen.append(
                    Probleem(
                        f"{kpi['value']} is de {metric} van {van} tot {tot}, maar de tekst noemt "
                        f"{periode.label(genoemd[0])} tot {periode.label(genoemd[1])}.",
                        "Die waarde komt uit compute_kpi: noem de periode uit `periode`.",
                    )
                )
    return list(dict.fromkeys(problemen))
