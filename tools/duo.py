import difflib
import hashlib
import json

import pandas as pd
from riodata import duo as _duo

from core.config import DUO_ROW_LIMIT

from . import store
from .catalog import catalogus_titel, resource_titel

_SAMPLE_ROWS = 3

_SUPPORTED_OPS = frozenset({"eq", "gte", "lte", "in"})

# Grenzen voor de suggesties bij een leeg filterresultaat. Het scannen van
# unieke waarden is lineair in de kolomlengte, vandaar een bovengrens.
_SUGGESTIE_MAX_UNIEK = 500
_SUGGESTIE_AANTAL = 3
_SUGGESTIE_DREMPEL = 0.6

_DUO_SENTINELS = (-1,)


def _coerce_pair(a, b):
    """Coerce two values to a comparable pair (float preferred, str fallback)."""
    try:
        return float(a), float(b)
    except (ValueError, TypeError):
        return str(a).lower(), str(b).lower()


def _parse_filter_key(key: str) -> tuple[str, str]:
    if "__" in key:
        col, op = key.rsplit("__", 1)
    else:
        col, op = key, "eq"
    return col, op


def _mask_sentinels(df):
    """Replace DUO sentinels (-1) with pd.NA in numeric columns.

    DUO uses -1 to mark suppressed values (small counts). Replace with pd.NA
    so they're excluded from aggregations regardless of code path.
    """
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            mask = df[col].isin(_DUO_SENTINELS)
            if mask.any():
                df.loc[mask, col] = pd.NA
    return df


def _apply_filters(df, filters: dict):
    for key, val in filters.items():
        col, op = _parse_filter_key(key)

        if col not in df.columns:
            return None, f"Kolom '{col}' bestaat niet. Beschikbare kolommen: {list(df.columns)}"
        if op not in _SUPPORTED_OPS:
            return None, f"Onbekende operator '{op}' in filter '{key}'. Ondersteunde operatoren: gte, lte, in."

        series = df[col]

        if op in ("eq", "in"):
            vals = val if isinstance(val, list) else [val]
            vals_lower = {str(v).lower() for v in vals}
            df = df[series.astype(str).str.lower().isin(vals_lower)]
        elif op == "gte":
            df = df[series.apply(lambda v, t=val: _coerce_pair(v, t)[0] >= _coerce_pair(v, t)[1])]
        elif op == "lte":
            df = df[series.apply(lambda v, t=val: _coerce_pair(v, t)[0] <= _coerce_pair(v, t)[1])]

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
        df = _mask_sentinels(df)
        store.put(key, df)

    defs = _duo.column_definitions(list(df.columns))
    schema = [
        {
            "kolom": col,
            "type": str(df[col].dtype),
            "voorbeelden": df[col].dropna().unique()[:3].tolist(),
            **({"definitie": defs[col]} if col in defs else {}),
        }
        for col in df.columns
    ]
    preview = df.head(_SAMPLE_ROWS).to_dict(orient="records")

    return json.dumps(
        {
            "data_key": key,
            "catalogus_titel": catalogus_titel(dataset_id),
            "resource_titel": resource_titel(dataset_id, resource),
            "totaal_rijen": len(df),
            "kolommen": schema,
            "preview": preview,
        },
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


def _apply_aggregation(df, group_by, aggregate, source: str = ""):
    df = df.copy()
    for col in aggregate:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    out = df.groupby(group_by, dropna=False).agg(aggregate).reset_index()
    return out, []


def _filter_suggesties(origineel, filters: dict) -> dict:
    """Dichtstbijzijnde bestaande waarden per filterkolom, voor een leeg resultaat.

    Zonder deze hint krijgt het model alleen `0 rijen` terug en moet het zelf
    raden of de spelling, de kolom of de waarde zelf het probleem is.
    """
    hints: dict = {}
    for key, val in filters.items():
        col, op = _parse_filter_key(key)
        if col not in origineel.columns:
            continue
        kolom = origineel[col]
        if op in ("eq", "in"):
            aanwezig = [str(v) for v in kolom.dropna().unique()[:_SUGGESTIE_MAX_UNIEK]]
            gezocht = str(val[0] if isinstance(val, list) and val else val)
            dichtbij = difflib.get_close_matches(
                gezocht, aanwezig, n=_SUGGESTIE_AANTAL, cutoff=_SUGGESTIE_DREMPEL
            )
            hints[col] = dichtbij or aanwezig[:_SUGGESTIE_AANTAL]
        elif op in ("gte", "lte"):
            numeriek = pd.to_numeric(kolom, errors="coerce").dropna()
            if not numeriek.empty:
                hints[col] = f"bereik in de data: {numeriek.min()} t/m {numeriek.max()}"
    return hints


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
        origineel = df
        df, err = _apply_filters(df, filters)
        if err:
            return err
        if len(df) == 0:
            return json.dumps(
                {
                    "data_key": data_key,
                    "totaal_rijen": 0,
                    "rijen": [],
                    "melding": "Het filter leverde 0 rijen op. Controleer de waarden hieronder voor je concludeert dat de data ontbreekt.",
                    "suggesties": _filter_suggesties(origineel, filters),
                },
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )

    if columns:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            return f"Kolommen niet gevonden: {missing}. Beschikbaar: {list(df.columns)}"
        df = df[columns]

    notes = []
    if group_by or aggregate:
        err = _validate_aggregation(df, group_by, aggregate)
        if err:
            return err
        df, notes = _apply_aggregation(df, group_by, aggregate, source="duo")

    transformed = filters or columns or group_by
    if transformed:
        sig = json.dumps({"f": filters, "c": columns, "g": group_by, "a": aggregate}, sort_keys=True, default=str)
        suffix = hashlib.md5(sig.encode()).hexdigest()[:8]
        result_key = f"{data_key}:{suffix}"
        store.put(result_key, df)
    else:
        result_key = data_key

    n_cols = len(df.columns)
    adaptive_max = max(30, min(max_rows, 2000 // max(n_cols, 1)))
    total = len(df)
    rows = df.head(adaptive_max).to_dict(orient="records")
    result: dict = {"data_key": result_key, "totaal_rijen": total, "rijen": rows}
    if notes:
        result["databewerking"] = notes
    if total > adaptive_max:
        result["waarschuwing"] = (
            f"Eerste {adaptive_max} van {total} rijen teruggegeven "
            f"({n_cols} kolommen × {adaptive_max} rijen). Verfijn je filters of selecteer minder kolommen."
        )

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
