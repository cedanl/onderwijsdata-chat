"""compute_kpi-resultaten: een afgeleide waarde met een eigen bron (#235, #409, #420).

Een KPI is een afgeleide waarde (verschil, som, gemiddelde) met een eigen bron:
de jaren in `periode` en de selectie in `bron`. De periode-, scope- en
bindingscontrole lezen KPI's alleen hier, en zoeken een KPI-waarde in de tekst
met dezelfde getalherkenning als de getalcontrole.
"""

import json
from dataclasses import dataclass

from tools import periode

from .grounding import getallen_in


@dataclass(frozen=True)
class Kpi:
    """Eén compute_kpi-resultaat zoals de controles het lezen."""

    waarde: str  # zoals compute_kpi hem toont: +29.040, −8.700, 9,6, +9,5%
    cijfers: str | None  # de cijfers van een gehele waarde, zonder teken of %: 29040; None bij 9,6
    bereik: tuple[int, int] | None  # startjaren van de eerste en laatste periode; None zonder schooljaren
    periode: dict | None  # {"van": "2019/20", "tot": "2025/26"}; None zonder periode
    bron: dict | None  # data_key, kolom, metric, …; None zonder bron


def kpis(tool_results: list[str]) -> list[Kpi]:
    """Elk toolresultaat dat een JSON-object met een `value` is; een fout of andere uitvoer telt niet."""
    gelezen = []
    for result in tool_results:
        try:
            data = json.loads(result)
        except (TypeError, ValueError):
            continue
        if isinstance(data, dict) and "value" in data:
            gelezen.append(_kpi(data))
    return gelezen


def _kpi(data: dict) -> Kpi:
    waarde = str(data["value"])
    jaren = data["periode"] if isinstance(data.get("periode"), dict) else None
    bron = data["bron"] if isinstance(data.get("bron"), dict) else None
    return Kpi(waarde, _cijfers(waarde), _bereik(jaren), jaren, bron)


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
    """Staat de KPI-waarde (zonder teken of %) als los getal in het segment?

    Geschreven zoals de waarde, met een punt of een (harde of smalle) spatie als duizendtalscheiding
    (#236): 2024 is geen KPI van 2.024. Volgt er een punt met een cijfer (12.5), dan is het een ander
    getal. Volgt er een komma, dan telt het ook niet; zo was het vóór #420, ook bij een komma als leesteken.
    """
    kaal = _kaal(kpi.waarde)
    return any(
        _met_punten(geschreven) == kaal and _los(segment[positie + len(geschreven) :])
        for geschreven, _, positie in getallen_in(segment)
    )


def _met_punten(geschreven: str) -> str:
    """Het getal met een punt als duizendtalscheiding, ook waar het een spatie had: 29 040 → 29.040."""
    return "".join(teken if teken.isdigit() or teken == "," else "." for teken in geschreven)


def _los(rest: str) -> bool:
    """Houdt het getal op voor `rest`: geen komma, en geen punt met een cijfer (12.5 is geen 12)."""
    return not rest.startswith(",") and not (rest[:1] == "." and rest[1:2].isdigit())
