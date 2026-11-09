"""CBS: publieke onderwijstabellen via de OData API van StatLine (was het pakket `onderwijsdata`, #910).

    from onderwijsbronnen.cbs import data, dimension, properties

Let op: `data` is de functie, en `cbs.data` is ook de naam van de datamap met de catalogus. Na de eerste catalogus-
aanroep in een proces wijst het attribuut `cbs.data` naar die map; `from onderwijsbronnen.cbs import data` vóór die
aanroep (zoals in een snippet) en `cbs.client.data` geven altijd de functie (tests/test_bron_id_vormen.py in de chat).
"""

from .._kern import broncontract, sleutels
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
            records = json.loads(data_dir.joinpath("cbs_datasets_enriched.json").read_text(encoding="utf-8"))
            return [_met_sleutels(r) for r in records]
        except FileNotFoundError:
            pass
    filename = "cbs_datasets_ai.json" if ai else "cbs_datasets.json"
    return [_met_sleutels(r) for r in json.loads(data_dir.joinpath(filename).read_text(encoding="utf-8"))]


# De regio-indelingen van CBS die een andere bron als sleutel heeft (`_geo_niveau`); landsdeel, COROP en landelijk niet.
_REGIOSLEUTELS = ("gemeente", "provincie", "arbeidsmarktregio")
_ZONDER_SLEUTEL = (
    "Geen regio-indeling naar gemeente, provincie of arbeidsmarktregio en geen schooljaren in Perioden (kalenderjaren "
    "of overgangen tussen twee schooljaren); de andere dimensies zijn indelingen van CBS die geen andere bron deelt."
)


def _met_sleutels(record: dict) -> dict:
    """Het record met `_sleutels` (#958), uit de dimensies: de regiokolom met de regio-indelingen uit `_geo_niveau`
    (een gemengde kolom draagt er meer), en Perioden als schooljaar alleen bij schooljaarcodes (`SJ`)."""
    titels = record.get("_dimensie_sleutels") or {}
    soorten = record.get("_kolomtypes") or {}
    niveaus = set(record.get("_geo_niveau") or ())
    paren = []
    for titel, kolom in titels.items():
        if soorten.get(titel) == "geo-dimensie" or "regio" in kolom.lower():
            paren += [{"kolom": kolom, "sleutel": s} for s in _REGIOSLEUTELS if s in niveaus]
        elif soorten.get(titel) == "tijd-dimensie" and "SJ" in (record.get("_perioden_formaat") or ()):
            paren.append({"kolom": kolom, "sleutel": "schooljaar"})
    return sleutels.in_record(record, paren, _ZONDER_SLEUTEL)


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
