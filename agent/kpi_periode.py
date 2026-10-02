"""Hoort het periodebereik in de tekst bij de KPI die het getal leverde? (#235)

De getalcontrole ziet dat +29.040 uit compute_kpi komt, maar niet over welke
jaren. Audit 10: "2019/20 → 2024/25: +29.040", terwijl de KPI 2019/20 → 2025/26
was. compute_kpi geeft die jaren nu mee als `periode`; noemt een zin het
KPI-getal samen met een bereik van schooljaren, dan moet dat bereik kloppen.
Eén genoemd schooljaar is geen bereik: daarover gaat binding.py.
"""

import json
import re

from tools import periode

from .binding import segmenten
from .probleem import Probleem


def _kpis(tool_results: list[str]) -> list[dict]:
    kpis = []
    for result in tool_results:
        try:
            data = json.loads(result)
        except (TypeError, ValueError):
            continue
        if isinstance(data, dict) and "periode" in data and "value" in data:
            kpis.append(data)
    return kpis


def _noemt(segment: str, waarde: str) -> bool:
    """Staat de KPI-waarde (zonder teken of %) als los getal in het segment?"""
    kaal = waarde.lstrip("+-−").rstrip("%")
    return re.search(rf"(?<![\d.,]){re.escape(kaal)}(?![\d,]|\.\d)", segment) is not None


def _startjaar(label: str) -> int | None:
    return next(iter(periode.gevraagde_schooljaren(label)), None)


def verkeerde_kpi_periodes(tekst: str, tool_results: list[str]) -> list[str]:
    problemen = []
    for kpi in _kpis(tool_results):
        van, tot = kpi["periode"]["van"], kpi["periode"]["tot"]
        bereik = (_startjaar(van), _startjaar(tot))
        if None in bereik:
            continue
        for segment in segmenten(tekst):
            genoemd = periode.gevraagde_schooljaren(segment)
            if len(genoemd) < 2 or not _noemt(segment, kpi["value"]):
                continue
            if (min(genoemd), max(genoemd)) != bereik:
                metric = kpi.get("bron", {}).get("metric", "KPI")
                problemen.append(Probleem(
                    f"{kpi['value']} is de {metric} van {van} tot {tot}, maar de tekst noemt "
                    f"{periode.label(min(genoemd))} tot {periode.label(max(genoemd))}.",
                    "Die waarde komt uit compute_kpi: noem de periode uit `periode`.",
                ))
    return list(dict.fromkeys(problemen))
