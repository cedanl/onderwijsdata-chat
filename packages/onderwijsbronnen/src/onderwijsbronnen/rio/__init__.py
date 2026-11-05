"""RIO: het Register Instellingen en Opleidingen, via de RIO LOD API v3 (was het hart van `riodata`, #910).

    from onderwijsbronnen.rio import fetch, get, related, filtercontract, opvolgers, voorgangers

`client` praat met de API, `_filtercontract` kent de filters per resource uit de OpenAPI-spec, `overgangen` volgt
fusies en overgangen van instellingen, `aanbieders` de onderwijsaanbieders van een erkenning (#744).
"""

from .._kern import broncontract, verrijking
from . import aanbieders, client, overgangen
from .aanbieders import onderwijsaanbieders
from ._filtercontract import filtercontract, typewaarden, valideer_filters
from .client import fetch, get, related
from .overgangen import Stap, opvolgers, voorgangers

BRON = "rio"
_DATA = "onderwijsbronnen.rio.data"


def catalogusrecords(ai: bool = True) -> list[dict]:
    """De RIO-resources als catalogusrecords; `ai`: met de AI-verrijkte beschrijvingen (standaard)."""
    if ai:
        return verrijking.met_verrijking(_DATA, "rio_resources_ai.json", "rio_resources_enriched.json",
                                         verrijking.VERRIJKT_RIO)
    return verrijking.lees_json(_DATA, "rio_resources.json")


laad = fetch


def metadata(record: dict) -> dict:
    return broncontract.metadata(
        BRON,
        record["_rio_resource"],
        record.get("bron"),
        redenen={
            "peildatum_of_editie": "live API: de stand op het moment van opvragen (filter datumGeldigOp voor een peildatum)",
            "voorlopig": "een register kent geen voorlopige cijfers",
            "laatste_update": "live API, dagelijks bijgewerkt; geen wijzigingsdatum per resource",
        },
    )


__all__ = ["fetch", "get", "related", "client", "overgangen", "filtercontract", "typewaarden", "valideer_filters",
           "Stap", "opvolgers", "voorgangers", "aanbieders", "onderwijsaanbieders", "BRON", "catalogusrecords", "laad", "metadata"]
