"""Het label "Vaste maat" onder een antwoord: uit de stappen van de beurt en het recept, nooit uit de modeltekst (#1242).

Een antwoord dat alleen op `get_maat` rust, kreeg zijn getal langs een vaste route: de code koos bron, dataset,
bestand en codes (#188). Dat is te zien voor wie het antwoord leest, met de teldefinitie en waar en wanneer het recept
is vastgelegd. Het label zegt alleen welke vaste route het getal gaf, niet dat het gecontroleerd of juist is.

Elke andere datastap in dezelfde beurt (query_data, run_analysis, koppel_data, een lader als get_cbs_data, een KPI)
kan het getal veranderd of ernaast gezet hebben: dan geen label. Stappen die geen getal leveren (de catalogus doorzoeken,
de codes van een dimensie, een scopekaart, een grafiek van geladen data) tellen niet mee. Twee verschillende maten
geven ook geen label: één label noemt één maat.
"""

import json

from tools.maten import MATEN
from tools.schemas import (
    TOOL_CLARIFY_SCOPE,
    TOOL_CREATE_CHOROPLETH_MAP,
    TOOL_CREATE_PLOT,
    TOOL_DATASET_DETAILS,
    TOOL_GET_CBS_DIMENSION,
    TOOL_GET_MAAT,
    TOOL_SEARCH_CATALOG,
)

# Stappen zonder eigen getal: ze zoeken, beschrijven of tonen, maar leveren geen data waar het antwoord op kan rusten.
# Bewust smal: wat hier niet staat (ook dataset_counts, dataset_profiel en relatie) telt als datastap.
_GEEN_DATASTAP = frozenset(
    {
        TOOL_SEARCH_CATALOG,
        TOOL_DATASET_DETAILS,
        TOOL_GET_CBS_DIMENSION,
        TOOL_CLARIFY_SCOPE,
        TOOL_CREATE_PLOT,
        TOOL_CREATE_CHOROPLETH_MAP,
    }
)


def _maatresultaat(result: str) -> dict | None:
    """Het resultaat van een geslaagde get_maat: een JSON-object met `maat` en `data_key`; een melding is geen maat."""
    try:
        uit = json.loads(result)
    except (TypeError, ValueError):
        return None
    if not isinstance(uit, dict) or not isinstance(uit.get("maat"), str) or not uit.get("data_key"):
        return None
    return uit


def vaste_maat(steps: list[tuple[str, str]]) -> dict | None:
    """`{maat, teldefinitie, vastgelegd_in, vastgelegd_op}` als elke datastap van de beurt een get_maat is; anders None.

    De maat komt uit het resultaat van de stap (code, niet het model) en moet een recept in MATEN zijn; de vastlegging
    komt uit dat recept. De teldefinitie is die van de stap, met de telling die geladen is (bij CBS de vorm of de
    standaard); verschilt ze tussen de stappen, dan die van het recept.
    """
    datastappen = [(tool, result) for tool, result in steps if tool not in _GEEN_DATASTAP]
    if not datastappen or any(tool != TOOL_GET_MAAT for tool, _ in datastappen):
        return None
    resultaten = [uit for _, result in datastappen if (uit := _maatresultaat(result))]
    maten = {uit["maat"] for uit in resultaten}
    if len(maten) != 1 or (recept := MATEN.get(next(iter(maten)))) is None:
        return None
    definities = {uit.get("teldefinitie") for uit in resultaten}
    gekozen = definities.pop() if len(definities) == 1 else None
    return {
        "maat": recept.naam,
        "teldefinitie": gekozen if isinstance(gekozen, str) and gekozen else recept.teldefinitie,
        "vastgelegd_in": recept.vastgelegd_in,
        "vastgelegd_op": recept.vastgelegd_op,
    }
