"""CBS: publieke onderwijstabellen via de OData API van StatLine (was het pakket `onderwijsdata`, #910).

    from onderwijsbronnen.cbs import data, dimension, properties

Let op: `data` is de functie, en `cbs.data` is ook de naam van de datamap met de catalogus. Na de eerste catalogus-
aanroep in een proces wijst het attribuut `cbs.data` naar die map; `from onderwijsbronnen.cbs import data` vóór die
aanroep (zoals in een snippet) en `cbs.client.data` geven altijd de functie (tests/test_bron_id_vormen.py in de chat).
"""

from .._kern import broncontract
from .._kern.versie import VERSIE as __version__
from .client import data, dimension, properties, definitions
from .contract import catalog_records, get_dataset, catalog_manifest, scope_review
from .validatie import validate_selection, resolve_dimensiewaarde, prepare_query

BRON = "cbs"


def catalog(ai=True):
    import json
    from importlib.resources import files
    data_dir = files("onderwijsbronnen.cbs.data")
    if ai:
        try:
            return json.loads(data_dir.joinpath("cbs_datasets_enriched.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            pass
    filename = "cbs_datasets_ai.json" if ai else "cbs_datasets.json"
    return json.loads(data_dir.joinpath(filename).read_text(encoding="utf-8"))


# Het broncontract (#911): dezelfde interface als de andere bronnen.
catalogusrecords = catalog
laad = data


def metadata(record: dict) -> dict:
    return broncontract.metadata(
        BRON,
        record["_cbs_id"],
        record.get("bron"),
        laatste_update=record.get("_laatste_update"),
        redenen={
            "peildatum_of_editie": "een CBS-tabel heeft geen editie; de perioden staan per rij in de data (Perioden)",
            "voorlopig": "CBS markeert voorlopige cijfers per periode in de data, niet per tabel",
            "laatste_update": "geen Modified in de CBS-catalogus",
        },
    )


__all__ = ["data", "dimension", "properties", "definitions", "catalog", "catalog_records", "get_dataset",
           "catalog_manifest", "scope_review", "validate_selection", "resolve_dimensiewaarde",
           "prepare_query", "BRON", "catalogusrecords", "laad", "metadata", "__version__"]
