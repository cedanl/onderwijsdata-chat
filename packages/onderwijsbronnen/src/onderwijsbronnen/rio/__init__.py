"""RIO: het Register Instellingen en Opleidingen, via de RIO LOD API v3 (was het hart van `riodata`, #910).

    from onderwijsbronnen.rio import fetch, get, related, filtercontract, opvolgers, voorgangers

`client` praat met de API, `_filtercontract` kent de filters per resource uit de OpenAPI-spec, `overgangen` volgt
fusies en overgangen van instellingen, `aanbieders` de onderwijsaanbieders van een erkenning (#744), `licenties` de
onderwijslicenties van een instelling op een peildatum (#1060).
"""

from .._kern import broncontract, sleutels, verrijking
from . import aanbieders, client, licenties, overgangen
from .aanbieders import onderwijsaanbieders
from .licenties import Licentie, met_erkenning, onderwijslicenties
from ._filtercontract import filtercontract, typewaarden, valideer_filters
from .client import fetch, get, related
from .overgangen import Stap, opvolgers, voorgangers

BRON = "rio"
_DATA = "onderwijsbronnen.rio.data"


def catalogusrecords(ai: bool = True) -> list[dict]:
    """De RIO-resources als catalogusrecords; `ai`: met de AI-verrijkte beschrijvingen (standaard)."""
    if ai:
        records = verrijking.met_verrijking(_DATA, "rio_resources_ai.json", "rio_resources_enriched.json",
                                            verrijking.VERRIJKT_RIO)
    else:
        records = verrijking.lees_json(_DATA, "rio_resources.json")
    return [sleutels.uit_kolommen(r, r.get("_kolommen") or [], _ZONDER_SLEUTEL) for r in records]


# Een register zonder sleutelkolom (licenties, locaties, erkenningen) koppelt binnen RIO via zijn eigen ID's.
_ZONDER_SLEUTEL = (
    "Dit RIO-register koppelt via zijn eigen RIO-ID's (id, code, licentiecode) binnen RIO, niet via een sleutel die "
    "een andere bron deelt."
)


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
           "Stap", "opvolgers", "voorgangers", "aanbieders", "onderwijsaanbieders", "licenties", "Licentie",
           "onderwijslicenties", "met_erkenning", "BRON", "catalogusrecords", "laad", "metadata"]
