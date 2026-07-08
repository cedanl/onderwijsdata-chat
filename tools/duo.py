import json

from riodata import duo as _duo
from core.config import DUO_ROW_LIMIT
from . import store

_SAMPLE_ROWS = 3


def _apply_filters(df, filters: dict):
    for key, val in filters.items():
        if "__" in key:
            col, op = key.rsplit("__", 1)
        else:
            col, op = key, "eq"

        if col not in df.columns:
            return None, f"Kolom '{col}' bestaat niet. Beschikbare kolommen: {list(df.columns)}"

        series = df[col]

        def _coerce(a, b):
            try:
                return float(a), float(b)
            except (ValueError, TypeError):
                return str(a).lower(), str(b).lower()

        if op == "eq":
            df = df[series.astype(str).str.lower() == str(val).lower()]
        elif op == "gte":
            df = df[series.apply(lambda v: _coerce(v, val)[0] >= _coerce(v, val)[1])]
        elif op == "lte":
            df = df[series.apply(lambda v: _coerce(v, val)[0] <= _coerce(v, val)[1])]
        elif op == "in":
            vals_lower = {str(v).lower() for v in val}
            df = df[series.astype(str).str.lower().isin(vals_lower)]
        else:
            return None, f"Onbekende operator '{op}' in filter '{key}'. Ondersteunde operatoren: gte, lte, in."

    return df, None


def get_duo_data(dataset_id: str, resource: int | str = 0) -> str:
    key = f"duo:{dataset_id}:{resource}"

    df = store.get(key)
    if df is None:
        try:
            df = _duo.load(dataset_id, resource)
        except Exception as e:
            try:
                cats = _duo.catalog()
                matches = [c for c in cats if dataset_id.lower() in json.dumps(c, ensure_ascii=False).lower()]
                hint = f" Vergelijkbare datasets: {[c.get('_ckan_id') for c in matches[:3]]}" if matches else ""
            except Exception:
                hint = ""
            return f"Fout bij laden DUO dataset '{dataset_id}': {e}.{hint}"
        store.put(key, df)

    schema = [
        {
            "kolom": col,
            "type": str(df[col].dtype),
            "voorbeelden": df[col].dropna().unique()[:3].tolist(),
        }
        for col in df.columns
    ]
    preview = df.head(_SAMPLE_ROWS).to_dict(orient="records")

    return json.dumps(
        {"data_key": key, "totaal_rijen": len(df), "kolommen": schema, "preview": preview},
        ensure_ascii=False, separators=(",", ":"), default=str,
    )


_ALLOWED_AGG = {"sum", "mean", "count", "min", "max"}


def _validate_aggregation(df, group_by, aggregate):
    if bool(group_by) != bool(aggregate):
        return "group_by en aggregate moeten samen worden meegegeven."
    missing_gb = [c for c in group_by if c not in df.columns]
    if missing_gb:
        return f"group_by kolommen niet gevonden: {missing_gb}. Beschikbaar: {list(df.columns)}"
    missing_agg = [c for c in aggregate if c not in df.columns]
    if missing_agg:
        return f"aggregate kolommen niet gevonden: {missing_agg}. Beschikbaar: {list(df.columns)}"
    bad_fns = {f for f in aggregate.values() if f not in _ALLOWED_AGG}
    if bad_fns:
        return f"Ongeldige aggregatiefuncties: {bad_fns}. Toegestaan: {sorted(_ALLOWED_AGG)}"
    return None


def _apply_aggregation(df, group_by, aggregate):
    import pandas as pd
    for col in aggregate:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.groupby(group_by, dropna=False).agg(aggregate).reset_index()


def query_data(
    data_key: str,
    filters: dict | None = None,
    columns: list[str] | None = None,
    max_rows: int = DUO_ROW_LIMIT,
    group_by: list[str] | None = None,
    aggregate: dict[str, str] | None = None,
) -> str:
    df = store.get(data_key)
    if df is None:
        available = store.list_keys()
        hint = f" Beschikbare datasets: {available}" if available else ""
        return f"Geen data gevonden voor '{data_key}'.{hint} Laad eerst data via get_duo_data, get_cbs_data of get_rio_data."

    if filters:
        df, err = _apply_filters(df, filters)
        if err:
            return err

    if columns:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            return f"Kolommen niet gevonden: {missing}. Beschikbaar: {list(df.columns)}"
        df = df[columns]

    if group_by or aggregate:
        err = _validate_aggregation(df, group_by, aggregate)
        if err:
            return err
        df = _apply_aggregation(df, group_by, aggregate)

    transformed = filters or columns or group_by
    result_key = f"{data_key}:result" if transformed else data_key
    if transformed:
        store.put(result_key, df)

    n_cols = len(df.columns)
    adaptive_max = max(30, min(max_rows, 2000 // max(n_cols, 1)))
    total = len(df)
    rows = df.head(adaptive_max).to_dict(orient="records")
    result: dict = {"data_key": result_key, "totaal_rijen": total, "rijen": rows}
    if total > adaptive_max:
        result["waarschuwing"] = (
            f"Eerste {adaptive_max} van {total} rijen teruggegeven "
            f"({n_cols} kolommen × {adaptive_max} rijen). Verfijn je filters of selecteer minder kolommen."
        )

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
