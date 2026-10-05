"""Uitkomst van een toolstap voor de redeneerkaart (#386).

Een stap die liep is nog geen stap die iets opleverde: een filter met 0 rijen
of een foutmelding stond als groen "Data gefilterd" in de kaart. De uitkomst
wordt hier uit het toolresultaat gelezen, niet aan het model gevraagd.
"""

import json

from .schemas import TOOL_QUERY_DATA


def _query_data(result: str) -> dict:
    try:
        parsed = json.loads(result)
    except ValueError:
        parsed = None
    if not isinstance(parsed, dict) or "rijen" not in parsed:
        # query_data geeft bij succes altijd JSON met rijen; al het andere is een melding.
        return {"status": "error", "status_label": "Filter mislukt"}
    if parsed["rijen"]:
        return {}
    uit = {"status": "empty", "status_label": "Filter leverde 0 rijen op"}
    if parsed.get("suggesties"):
        uit["suggesties"] = parsed["suggesties"]
    return uit


_READERS = {TOOL_QUERY_DATA: _query_data}


def outcome(name: str, result: str) -> dict:
    """Velden voor het tool_end-event; leeg betekent: de stap slaagde."""
    reader = _READERS.get(name)
    return reader(result) if reader else {}
