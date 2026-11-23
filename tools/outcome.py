"""Uitkomst van een toolstap voor de redeneerkaart (#386).

Een stap die liep is nog geen stap die iets opleverde: een filter met 0 rijen
of een foutmelding stond als groen "Data gefilterd" in de kaart. De uitkomst
wordt hier uit het toolresultaat gelezen, niet aan het model gevraagd.

Een opvraag die de scopegrens weigerde (`buiten_scope`, #640) stond als groen
"CBS data opgehaald", alsof er data kwam: die stap heet nu naar zijn uitkomst.

Hetzelfde gold voor een opvraag, maat, KPI of analyse die niets opleverde (#1072): een onbekende tabel, een onbekende
instelling, een kolom die niet bestaat of een script dat de tijdgrens haalde stonden groen in de kaart. Een laadtool
geeft bij succes JSON met een `data_key`, `compute_kpi` JSON zonder `fout` en `run_analysis` JSON; al het andere is een
melding. Een tool zonder eigen lezer telt alleen een gecodeerde fout (`fouten.code`) als mislukt.
"""

import json

from . import fouten
from .schemas import (
    TOOL_COMPUTE_KPI,
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_MAAT,
    TOOL_GET_RIO_DATA,
    TOOL_GET_RIO_INSTELLING,
    TOOL_KOPPEL_DATA,
    TOOL_QUERY_DATA,
    TOOL_RUN_ANALYSIS,
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


def _koppel_data(result: str) -> dict:
    """koppel_data geeft bij succes JSON met rijen (#988); een melding (onbekende sleutel, dubbelzinnige kolom) niet."""
    parsed = _json_dict(result)
    if parsed is None or "rijen" not in parsed:
        return {"status": "error", "status_label": "Koppeling mislukt"}
    return {}


def _mislukt(label: str) -> dict:
    return {"status": "error", "status_label": label}


def _laadtool(label: str):
    """Lezer voor een tool die data laadt: bij succes JSON met een `data_key`, anders een melding (#1072)."""

    def lees(result: str) -> dict:
        parsed = _json_dict(result)
        return {} if parsed is not None and isinstance(parsed.get("data_key"), str) else _mislukt(label)

    return lees


def _compute_kpi(result: str) -> dict:
    """compute_kpi verpakt een fout als {"fout": ...}; zonder JSON-object is het ook geen KPI."""
    parsed = _json_dict(result)
    return _mislukt("KPI-berekening mislukt") if parsed is None or "fout" in parsed else {}


def _run_analysis(result: str) -> dict:
    """run_analysis geeft bij succes JSON; een foutmelding van het script, de tijdgrens of de koppelguard is tekst."""
    try:
        json.loads(result)
    except ValueError:
        return _mislukt("Analyse mislukt")
    return {}


_READERS = {
    TOOL_QUERY_DATA: _query_data,
    TOOL_KOPPEL_DATA: _koppel_data,
    TOOL_GET_CBS_DATA: _laadtool("CBS-opvraag mislukt"),
    TOOL_GET_DUO_DATA: _laadtool("DUO-opvraag mislukt"),
    TOOL_GET_MAAT: _laadtool("Vaste maat niet opgehaald"),
    TOOL_COMPUTE_KPI: _compute_kpi,
    TOOL_RUN_ANALYSIS: _run_analysis,
}


def outcome(name: str, result: str) -> dict:
    """Velden voor het tool_end-event; leeg betekent: de stap slaagde."""
    if geweigerd := _buiten_scope(name, result):
        return geweigerd
    if reader := _READERS.get(name):
        return reader(result)
    return _mislukt("Stap mislukt") if fouten.code(result) else {}
