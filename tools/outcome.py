"""Uitkomst van een toolstap voor de redeneerkaart (#386).

Een stap die liep is nog geen stap die iets opleverde: een filter met 0 rijen
of een foutmelding stond als groen "Data gefilterd" in de kaart. De uitkomst
wordt hier uit het toolresultaat gelezen, niet aan het model gevraagd.

Een opvraag die de scopegrens weigerde (`buiten_scope`, #640) stond als groen
"CBS data opgehaald", alsof er data kwam: die stap heet nu naar zijn uitkomst.
"""

import json

from .schemas import (
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_RIO_DATA,
    TOOL_GET_RIO_INSTELLING,
    TOOL_QUERY_DATA,
)

_GEWEIGERD = {
    TOOL_GET_CBS_DATA: "CBS-opvraag geweigerd (buiten scope)",
    TOOL_GET_DUO_DATA: "DUO-opvraag geweigerd (buiten scope)",
    TOOL_GET_RIO_DATA: "RIO-opvraag geweigerd (buiten scope)",
    TOOL_GET_RIO_INSTELLING: "RIO-opvraag geweigerd (buiten scope)",
}
_GEWEIGERD_ANDERS = "Opvraag geweigerd (buiten scope)"


def _json_dict(result: str) -> dict | None:
    try:
        parsed = json.loads(result)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _buiten_scope(name: str, result: str) -> dict:
    """Weigerde de tool de opvraag op de scopegrens (`scopeprofiel.buiten_scope`)? Ook een RIO-register."""
    parsed = _json_dict(result)
    if parsed is None or parsed.get("buiten_scope") is not True:
        return {}
    return {"status": "buiten_scope", "status_label": _GEWEIGERD.get(name, _GEWEIGERD_ANDERS)}


def _query_data(result: str) -> dict:
    parsed = _json_dict(result)
    if parsed is None or "rijen" not in parsed:
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
    if geweigerd := _buiten_scope(name, result):
        return geweigerd
    reader = _READERS.get(name)
    return reader(result) if reader else {}
