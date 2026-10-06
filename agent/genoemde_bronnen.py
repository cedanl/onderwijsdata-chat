"""Dataset-ID's die de gebruiker letterlijk noemt, opgelost vóór elke zoekactie (#334).

Een vraag met `mbo-studenten-per-instelling` leidde tot nieuwe zoekacties met andere
woorden en de conclusie dat de dataset niet bestaat. De code zoekt het ID in de
catalogus en geeft het model per ID de bron en de datatool mee.
"""

import re

from tools.catalog import CHAT_BRONNEN, catalogus_titel, genoemde_datasets, leverancier
from tools.schemas import (
    TOOL_DATASET_DETAILS,
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_RIO_DATA,
    TOOL_SEARCH_CATALOG,
)

_DATATOOL = {"CBS": TOOL_GET_CBS_DATA, "DUO": TOOL_GET_DUO_DATA, "RIO": TOOL_GET_RIO_DATA}
_GEWOON_WOORD = re.compile(r"[^\W\d_]+")  # RIO-ID's als 'erkenningen' zijn ook gewone woorden


def _regel(dataset_id: str) -> str:
    bron = leverancier(dataset_id) or "?"
    kop = f"- {dataset_id}: {catalogus_titel(dataset_id)} ({bron})."
    if bron not in CHAT_BRONNEN:
        return f"{kop} Staat in de catalogus, maar is in de chat niet op te vragen."
    return f"{kop} Haal de data met {_DATATOOL[bron]}('{dataset_id}'); ken je de kolommen nog niet, dan eerst {TOOL_DATASET_DETAILS}('{dataset_id}')."


def genoemde_bronnen(vraag: str) -> str:
    """Systeemtekst met de catalogus-ID's uit de vraag; leeg als de vraag er geen noemt."""
    ids = [d for d in genoemde_datasets(vraag) if not _GEWOON_WOORD.fullmatch(d)]
    if not ids:
        return ""
    return (
        "De vraag noemt deze dataset-ID's en de catalogus kent ze: ze bestaan. "
        f"Gebruik ze direct en zoek ze niet opnieuw op met {TOOL_SEARCH_CATALOG}.\n" + "\n".join(_regel(d) for d in ids)
    )
