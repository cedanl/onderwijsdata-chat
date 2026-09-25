"""Server-side KPI-berekening.

De LLM mag geen getallen produceren die niet uit een tool komen. Voor KPI's in
een dashboard betekent dat: het model levert alleen de *verwijzing* (welke
data_key, welke kolom, welke maat) en deze module rekent. De waarde die
terugkomt is de waarde die in het dashboard hoort te staan — letterlijk over te
nemen, niet na te rekenen.
"""

import json

import pandas as pd

from . import store

# Toegestane maten. Gesloten set: een onbekende maat is een fout, geen
# aanleiding om iets anders te proberen.
_ALLOWED_METRICS = frozenset({
    "last", "first", "sum", "mean", "min", "max", "delta", "pct_change", "index",
})

# Maten waarvan de uitkomst een verandering is; die krijgen een trendlabel.
_TREND_METRICS = frozenset({"delta", "pct_change"})

# Maten met een relatieve uitkomst worden op één decimaal getoond.
_DECIMAL_METRICS = frozenset({"pct_change", "index", "mean"})

_DECIMALS = 1


def _nl_format(value: float, decimals: int = 0) -> str:
    """Nederlandse notatie: punt als duizendtalscheiding, komma als decimaalteken."""
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _error(message: str) -> str:
    return json.dumps({"fout": message}, ensure_ascii=False)


def compute_kpi(
    data_key: str,
    value_column: str,
    metric: str,
    sort_column: str | None = None,
    label: str = "",
) -> str:
    """Bereken één KPI over data uit de store.

    Geeft JSON terug met de waarde in Nederlandse notatie, de ruwe waarde voor
    de frontend, en een `bron`-blok dat vastlegt waar het getal vandaan komt.
    """
    if metric not in _ALLOWED_METRICS:
        return _error(f"Onbekende metric '{metric}'. Toegestaan: {sorted(_ALLOWED_METRICS)}.")

    df = store.get(data_key)
    if df is None:
        beschikbaar = store.list_keys()
        hint = f" Beschikbare datasets: {beschikbaar}." if beschikbaar else ""
        return _error(f"Geen data gevonden voor '{data_key}'.{hint}")

    if not store.volledig(data_key):
        return _error(store.ONVOLLEDIG)

    if value_column not in df.columns:
        return _error(f"Kolom '{value_column}' niet gevonden. Beschikbaar: {list(df.columns)}.")
    if sort_column and sort_column not in df.columns:
        return _error(f"Sorteerkolom '{sort_column}' niet gevonden. Beschikbaar: {list(df.columns)}.")

    if sort_column:
        df = df.sort_values(sort_column)

    series = pd.to_numeric(df[value_column], errors="coerce").dropna()
    if series.empty:
        return _error(f"Kolom '{value_column}' bevat geen numerieke waarden.")

    first, last = float(series.iloc[0]), float(series.iloc[-1])

    if metric in ("pct_change", "index") and first == 0:
        return _error(
            f"Kan '{metric}' niet berekenen: de eerste waarde in '{value_column}' is 0. "
            "Gebruik een andere maat of een ander startpunt."
        )

    waarden = {
        "last": last,
        "first": first,
        "sum": float(series.sum()),
        "mean": float(series.mean()),
        "min": float(series.min()),
        "max": float(series.max()),
        "delta": last - first,
        "pct_change": (last / first - 1) * 100 if first else 0.0,
        "index": last / first * 100 if first else 0.0,
    }
    value = waarden[metric]

    decimals = _DECIMALS if metric in _DECIMAL_METRICS else 0
    formatted = _nl_format(value, decimals)
    if metric in _TREND_METRICS and value > 0:
        formatted = f"+{formatted}"

    trend = None
    trend_direction = None
    if metric in _TREND_METRICS:
        trend = f"{formatted}%" if metric == "pct_change" else formatted
        trend_direction = "up" if value > 0 else "down" if value < 0 else None

    return json.dumps(
        {
            "label": label,
            "value": f"{formatted}%" if metric == "pct_change" else formatted,
            "raw": value,
            "trend": trend,
            "trendDirection": trend_direction,
            "bron": {
                "data_key": data_key,
                "kolom": value_column,
                "metric": metric,
                "sort_column": sort_column,
                "aantal_waarden": int(series.size),
            },
        },
        ensure_ascii=False,
    )
