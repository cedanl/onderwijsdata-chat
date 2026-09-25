import json

import httpx
import pandas as pd
from riodata import fetch

from core.config import RIO_PAGE_SIZE

from . import store
from .catalog import catalogus_titel, rio_filters
from .columns import sample_values

_SAMPLE_ROWS = 5
_PAGING = frozenset({"page", "pageSize"})


def _filter_hint(allowed: list[str]) -> str:
    return f" Toegestane filters: {allowed} (exacte waarden, geen operatoren als __contains)." if allowed else ""


def get_rio_data(resource: str, filters: dict | None = None) -> str:
    # Een onbekend filter kost anders een HTTP 400, waarna het model in een
    # ongefilterde eerste pagina gaat zoeken (#186). De catalogus weet welke kan.
    allowed = rio_filters(resource)
    unknown = [k for k in (filters or {}) if allowed and k not in allowed and k not in _PAGING]
    if unknown:
        return f"RIO-resource '{resource}' kent de filters {unknown} niet.{_filter_hint(allowed)}"

    # Eén pagina van RIO_PAGE_SIZE-rijen: volledige paginatie blokkeert bij
    # upstream 4xx op een late pagina (#159). Een grotere pageSize uit filters
    # zou onderstaande slice toch weer afkappen.
    params = {**(filters or {}), "page": 0, "pageSize": RIO_PAGE_SIZE}
    try:
        results = fetch(resource, **params)
    except httpx.HTTPStatusError as e:
        return (
            f"Fout bij ophalen RIO data: HTTP {e.response.status_code} voor "
            f"resource '{resource}' met filters {filters or {}}.{_filter_hint(allowed)}"
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
    # RIO levert geen totaal-aantal (#170): een volle pagina betekent dat er
    # waarschijnlijk meer rijen zijn. Geen "totaal_rijen" zoals bij CBS/DUO: die
    # naam las het model als registertotaal (#177).
    meer_beschikbaar = len(results) >= RIO_PAGE_SIZE
    # Pas cachen als de beschrijving gelukt is: een mislukte tool mag geen data achterlaten.
    store.put(key, df, store.KeyMeta(bron="rio", dataset=resource, volledig=not meer_beschikbaar))
    result = {
        "data_key": key,
        "catalogus_titel": catalogus_titel(resource),
        "opgehaalde_rijen": len(df),
        "meer_beschikbaar": meer_beschikbaar,
        "kolommen": schema,
        "preview": preview,
    }
    if meer_beschikbaar:
        result["waarschuwing"] = (
            f"Afgekapt op {RIO_PAGE_SIZE} rijen (één pagina); dit is geen telling. "
            "RIO levert geen totaal-aantal: beantwoord 'hoeveel'-vragen over het "
            "register niet met deze data. Verfijn met filters of gebruik DUO/CBS voor aantallen."
        )

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
