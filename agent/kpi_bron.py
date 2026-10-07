"""compute_kpi-resultaten met de periode waarover ze rekenen (#235, #409).

Een KPI is een afgeleide waarde (verschil, som, gemiddelde) met een eigen bron:
de jaren in `periode`. Zowel de periodecontrole als de bindingscontrole lezen die.
"""

import json

from tools import periode


def met_periode(tool_results: list[str]) -> list[dict]:
    """De compute_kpi-resultaten die een `periode` meegeven."""
    kpis = []
    for result in tool_results:
        try:
            data = json.loads(result)
        except (TypeError, ValueError):
            continue
        if isinstance(data, dict) and "periode" in data and "value" in data:
            kpis.append(data)
    return kpis


def bereik(kpi: dict) -> tuple[int, int] | None:
    """Startjaren van de eerste en laatste periode van de KPI; None als die geen schooljaren zijn."""
    return periode.schooljaarbereik(kpi["periode"]["van"], kpi["periode"]["tot"])
