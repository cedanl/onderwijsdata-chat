import hashlib
import json
import logging
from functools import lru_cache

import pandas as pd

from onderwijsdata import data, dimension, definitions
from core.config import CBS_ROW_LIMIT
from . import store

_SAMPLE_ROWS = 5


def get_cbs_data(dataset_id: str, filters: dict | None = None) -> str:
    params = dict(filters or {})
    if "$top" not in params:
        params["$top"] = CBS_ROW_LIMIT
    try:
        rows = data(dataset_id, **params)
    except Exception as e:
        return f"Fout bij ophalen CBS data: {e}"
    if not rows:
        return (
            f"Geen rijen gevonden in dataset '{dataset_id}' met filters {filters or {}}. "
            "Controleer de filtercodes via get_cbs_dimension — CBS gebruikt interne codes, geen leesbare labels."
        )

    df = pd.DataFrame(rows[:CBS_ROW_LIMIT])
    filter_hash = hashlib.md5(json.dumps(filters or {}, sort_keys=True).encode()).hexdigest()[:8]
    key = f"cbs:{dataset_id}:{filter_hash}" if filters else f"cbs:{dataset_id}"
    store.put(key, df)

    try:
        col_defs = definitions(dataset_id)
    except Exception as e:
        logging.warning("CBS DataProperties ophalen mislukt voor %s: %s", dataset_id, e)
        col_defs = {}
    schema = [
        {
            "kolom": col,
            "type": str(df[col].dtype),
            "voorbeelden": [str(v) for v in df[col].dropna().unique()[:5]],
            **({"definitie": col_defs[col]["description"]} if col in col_defs and col_defs[col].get("description") else {}),
            **({"eenheid": col_defs[col]["unit"]} if col in col_defs and col_defs[col].get("unit") else {}),
        }
        for col in df.columns
    ]
    preview = df.head(_SAMPLE_ROWS).to_dict(orient="records")
    truncated = len(rows) >= CBS_ROW_LIMIT

    result = {"data_key": key, "totaal_rijen": len(df), "kolommen": schema, "preview": preview}
    if truncated:
        result["waarschuwing"] = f"Afgekapt op {CBS_ROW_LIMIT} rijen. Verfijn $filter of $select voor volledigere data."

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)


@lru_cache(maxsize=256)
def get_cbs_dimension(dataset_id: str, dimension_name: str) -> str:
    try:
        values = dimension(dataset_id, dimension_name)
        return json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    except Exception as e:
        return f"Fout bij ophalen dimensie: {e}"
