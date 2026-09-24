import json

import httpx
import pandas as pd
from riodata import fetch

from core.config import RIO_PAGE_SIZE

from . import store
from .catalog import catalogus_titel
from .columns import sample_values

_SAMPLE_ROWS = 5


def get_rio_data(resource: str, filters: dict | None = None) -> str:
    # Eén pagina van RIO_PAGE_SIZE-rijen: volledige paginatie blokkeert bij
    # upstream 4xx op een late pagina (#159). Een grotere pageSize uit filters
    # zou onderstaande slice toch weer afkappen.
    params = {**(filters or {}), "page": 0, "pageSize": RIO_PAGE_SIZE}
    try:
        results = fetch(resource, **params)
    except httpx.HTTPStatusError as e:
        return (
            f"Fout bij ophalen RIO data: HTTP {e.response.status_code} voor "
            f"resource '{resource}' met filters {filters or {}}."
        )
    except Exception as e:
        return f"Fout bij ophalen RIO data: {e}"

    if not results:
        return f"Geen resultaten voor RIO resource '{resource}' met filters {filters or {}}."

    df = pd.DataFrame(results[:RIO_PAGE_SIZE])
    filter_suffix = "_".join(f"{k}={v}" for k, v in sorted((filters or {}).items()) if k not in ("page", "pageSize"))
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

    result = {
        "data_key": key,
        "catalogus_titel": catalogus_titel(resource),
        "totaal_rijen": len(df),
        "kolommen": schema,
        "preview": preview,
    }
    # RIO levert geen totaal-aantal (#170): een volle pagina betekent dat er
    # waarschijnlijk meer rijen zijn, dus dit is een steekproef.
    if len(results) >= RIO_PAGE_SIZE:
        result["waarschuwing"] = (
            f"Afgekapt op {RIO_PAGE_SIZE} rijen (één pagina); dit is geen telling. "
            "RIO levert geen totaal-aantal: beantwoord 'hoeveel'-vragen over het "
            "register niet met deze data. Verfijn met filters of gebruik DUO/CBS voor aantallen."
        )

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
