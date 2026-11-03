__version__ = "0.2.2"

from .client import data, dimension, properties, definitions
from .contract import catalog_records, get_dataset, catalog_manifest, scope_review
from .validatie import validate_selection, resolve_dimensiewaarde, prepare_query

def catalog(ai=True):
    import json
    from importlib.resources import files
    data_dir = files("onderwijsdata.data")
    if ai:
        try:
            return json.loads(data_dir.joinpath("cbs_datasets_enriched.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            pass
    filename = "cbs_datasets_ai.json" if ai else "cbs_datasets.json"
    return json.loads(data_dir.joinpath(filename).read_text(encoding="utf-8"))

__all__ = ["data", "dimension", "properties", "definitions", "catalog", "catalog_records", "get_dataset",
           "catalog_manifest", "scope_review", "validate_selection", "resolve_dimensiewaarde",
           "prepare_query", "__version__"]
