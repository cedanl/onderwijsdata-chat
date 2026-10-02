"""Server-side KPI-berekening.

De LLM mag geen getallen produceren die niet uit een tool komen. Voor KPI's in
een dashboard betekent dat: het model levert alleen de *verwijzing* (welke
data_key, welke kolom, welke maat) en deze module rekent. De waarde die
terugkomt is de waarde die in het dashboard hoort te staan — letterlijk over te
nemen, niet na te rekenen.
"""

import json

import pandas as pd

from . import periode, store

# Toegestane maten. Gesloten set: een onbekende maat is een fout, geen
# aanleiding om iets anders te proberen.
_ALLOWED_METRICS = frozenset(
    {
        "last",
        "first",
        "sum",
        "mean",
        "min",
        "max",
        "delta",
        "pct_change",
        "index",
        "max_drop",
        "max_rise",
    }
)

# Grootste stap tussen twee opeenvolgende waarden: de uitkomst is een verschil, met de twee
# rijen waartussen het zit (#116). Het model zoekt dat niet zelf in een tabel.
_STEP_METRICS = {"max_drop": "daling", "max_rise": "stijging"}

# Maten waarvan de uitkomst een verandering is; die krijgen een trendlabel.
_TREND_METRICS = frozenset({"delta", "pct_change", "max_drop", "max_rise"})

# Maten met een relatieve uitkomst worden op één decimaal getoond.
_DECIMAL_METRICS = frozenset({"pct_change", "index", "mean"})

_DECIMALS = 1


def _nl_format(value: float, decimals: int = 0) -> str:
    """Nederlandse notatie: punt als duizendtalscheiding, komma als decimaalteken."""
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _error(message: str) -> str:
    return json.dumps({"fout": message}, ensure_ascii=False)


def _largest_step(df: pd.DataFrame, value_column: str, sort_column: str | None, metric: str):
    """(verschil, van, naar) van de grootste daling of stijging tussen opeenvolgende rijen, of None."""
    numeric = pd.to_numeric(df[value_column], errors="coerce")
    # Positional index: a stored frame may repeat index labels (a concat), and a label lookup
    # then returns several rows instead of one step.
    rows = df.assign(_waarde=numeric).dropna(subset=["_waarde"]).reset_index(drop=True)
    steps = rows["_waarde"].diff().iloc[1:]
    steps = steps[steps < 0] if metric == "max_drop" else steps[steps > 0]
    if steps.empty:
        return None
    at = int(steps.idxmin() if metric == "max_drop" else steps.idxmax())
    label = (lambda i: rows.at[i, sort_column]) if sort_column else (lambda i: i + 1)
    return float(steps[at]), label(at - 1), label(at)


def _periodelabel(bron: str, waarde) -> str:
    """2021 → 2021/22, 2019SJ00 → 2019/20; wat geen schooljaar is blijft zoals de bron het noemt."""
    startjaar = periode.startjaar(bron, waarde)
    return periode.label(startjaar) if startjaar is not None else str(waarde)


def _periode(df: pd.DataFrame, value_column: str, sort_column: str | None, step, bron: str) -> dict:
    """Over welke periode de KPI gaat (#235): de eerste en laatste meegetelde rij, of de stap."""
    if not sort_column:
        return {}
    if step:
        van, tot = step[1], step[2]
    else:
        meegeteld = df.loc[pd.to_numeric(df[value_column], errors="coerce").notna(), sort_column]
        van, tot = meegeteld.iloc[0], meegeteld.iloc[-1]
    return {"periode": {"van": _periodelabel(bron, van), "tot": _periodelabel(bron, tot)}}


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

    step = None
    if metric in _STEP_METRICS:
        step = _largest_step(df, value_column, sort_column, metric)
        if step is None:
            return _error(
                f"Geen {_STEP_METRICS[metric]} in '{value_column}': geen enkele opeenvolgende waarde verandert die kant op."
            )

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
        "max_drop": step[0] if step else 0.0,
        "max_rise": step[0] if step else 0.0,
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

    tussen = {"tussen": [str(step[1]), str(step[2])]} if step else {}
    known = store.meta(data_key)
    periode_van_kpi = _periode(df, value_column, sort_column, step, known.bron if known else "")
    return json.dumps(
        {
            "label": label,
            "value": f"{formatted}%" if metric == "pct_change" else formatted,
            "raw": value,
            "trend": trend,
            "trendDirection": trend_direction,
            **tussen,
            **periode_van_kpi,
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
