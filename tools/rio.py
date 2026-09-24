import json

import pandas as pd
from riodata import fetch

from core.config import RIO_PAGE_SIZE

from . import store
from .catalog import catalogus_titel
from .columns import sample_values

_SAMPLE_ROWS = 5


def get_rio_data(resource: str, filters: dict | None = None) -> str:
    params = dict(filters or {})
    if "pageSize" not in params:
        params["pageSize"] = RIO_PAGE_SIZE
    try:
        results = fetch(resource, **params)
    except Exception as e:
        return f"Fout bij ophalen RIO data: {e}"

    if not results:
        return f"Geen resultaten voor RIO resource '{resource}' met filters {filters or {}}."

    df = pd.DataFrame(results[:RIO_PAGE_SIZE])
    filter_suffix = "_".join(f"{k}={v}" for k, v in sorted((filters or {}).items()) if k != "pageSize")
    key = f"rio:{resource}:{filter_suffix}" if filter_suffix else f"rio:{resource}"

    schema = [
        {
            "kolom": col,
            "type": str(df[col].dtype),
            "voorbeelden": sample_values(df[col], 5),
        }
        for col in df.columns
    ]
    preview = df.head(_SAMPLE_ROWS).to_dict(orient="records")
    # Pas cachen als de beschrijving gelukt is: een mislukte tool mag geen data achterlaten.
    store.put(key, df)

    return json.dumps(
        {
            "data_key": key,
            "catalogus_titel": catalogus_titel(resource),
            "totaal_rijen": len(df),
            "kolommen": schema,
            "preview": preview,
        },
        ensure_ascii=False, separators=(",", ":"), default=str,
    )
