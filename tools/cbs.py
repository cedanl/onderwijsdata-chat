import json
from functools import lru_cache

import pandas as pd

from onderwijsdata import data, dimension
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
    filter_suffix = "_".join(f"{k}={v}" for k, v in sorted((filters or {}).items()) if not k.startswith("$"))
    key = f"cbs:{dataset_id}:{filter_suffix}" if filter_suffix else f"cbs:{dataset_id}"
    store.put(key, df)

    schema = [
        {
            "kolom": col,
            "type": str(df[col].dtype),
            "voorbeelden": [str(v) for v in df[col].dropna().unique()[:5]],
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
