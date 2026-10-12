"""compute_kpi-resultaten: een afgeleide waarde met een eigen bron (#235, #409, #420).

Een KPI is een afgeleide waarde (verschil, som, gemiddelde) met een eigen bron:
de jaren in `periode` en de selectie in `bron`. De periode-, scope- en
bindingscontrole, de citaties (meetwaarden) en de dashboardvalidatie lezen KPI's
alleen hier; de periode- en scopecontrole zoeken een KPI-waarde in de tekst met
`noemt`, het dashboard vergelijkt een modelwaarde met `sleutel`.
"""

import json
import re
from dataclasses import dataclass

from tools import periode

# Duizendtallen met (harde of smalle) spatie, zoals gpt-oss ze schrijft (#236).
_SPATIE_DUIZENDTAL = re.compile(r"(?<=\d)[ \u00a0\u202f](?=\d{3}(?!\d))")


@dataclass(frozen=True)
class Kpi:
    """Eén compute_kpi-resultaat zoals de controles het lezen."""

    waarde: str  # zoals compute_kpi hem toont: +29.040, −8.700, 9,6, +9,5%
    cijfers: str | None  # de cijfers van een gehele waarde, zonder teken of %: 29040; None bij 9,6
    bereik: tuple[int, int] | None  # startjaren van de eerste en laatste periode; None zonder schooljaren
    periode: dict | None  # {"van": "2019/20", "tot": "2025/26"}; None zonder periode
    bron: dict | None  # data_key, kolom, metric, …; None zonder bron
    raw: int | float | None = None  # het getal zelf, zoals compute_kpi het berekende; None als het ontbreekt
    label: str | None = None  # het label dat het model meegaf
    trend: str | None = None  # de trend die de tool berekende, bijv. +5%
    richting: str | None = None  # trendDirection: up, down of None


def kpi(data) -> Kpi | None:
    """Eén geparset toolresultaat als KPI; None als het geen object met een `value` is."""
    if not isinstance(data, dict) or "value" not in data:
        return None
    return _kpi(data)


def kpis(tool_results: list[str]) -> list[Kpi]:
    """Elk toolresultaat dat een JSON-object met een `value` is; een fout of andere uitvoer telt niet."""
    gelezen = []
    for result in tool_results:
        try:
            data = json.loads(result)
        except (TypeError, ValueError):
            continue
        if (gelezen_kpi := kpi(data)) is not None:
            gelezen.append(gelezen_kpi)
    return gelezen


def _tekst(waarde) -> str | None:
    return waarde if isinstance(waarde, str) else None


def _kpi(data: dict) -> Kpi:
    waarde = str(data["value"])
    jaren = data["periode"] if isinstance(data.get("periode"), dict) else None
    bron = data["bron"] if isinstance(data.get("bron"), dict) else None
    raw = data.get("raw")
    return Kpi(
        waarde,
        _cijfers(waarde),
        _bereik(jaren),
        jaren,
        bron,
        raw=raw if isinstance(raw, int | float) and not isinstance(raw, bool) else None,
        label=_tekst(data.get("label")),
        trend=_tekst(data.get("trend")),
        richting=_tekst(data.get("trendDirection")),
    )


def sleutel(waarde) -> str:
    """Vergelijkbare vorm van een getal: '30.083', '30 083' en '30083' zijn hetzelfde getal."""
    return str(waarde).replace(".", "").replace(" ", "").replace("\u00a0", "").strip().lower()


def _kaal(waarde: str) -> str:
    """De waarde zonder teken of procent: +29.040 → 29.040, +9,5% → 9,5."""
    return waarde.lstrip("+-−").rstrip("%")


def _cijfers(waarde: str) -> str | None:
    cijfers = _kaal(waarde).replace(".", "")
    return cijfers if cijfers.isdigit() else None


def _bereik(jaren: dict | None) -> tuple[int, int] | None:
    """Startjaren van de eerste en laatste periode; None als die geen schooljaren zijn."""
    if jaren is None:
        return None
    return periode.schooljaarbereik(str(jaren.get("van")), str(jaren.get("tot")))


def noemt(segment: str, kpi: Kpi) -> bool:
    """Staat de KPI-waarde (zonder teken of %) als los getal in het segment?"""
    kaal = _kaal(kpi.waarde)
    segment = _SPATIE_DUIZENDTAL.sub(".", segment)
    return re.search(rf"(?<![\d.,]){re.escape(kaal)}(?![\d,]|\.\d)", segment) is not None
