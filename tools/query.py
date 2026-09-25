"""query_data: filteren, selecteren en aggregeren op een geladen dataset.

Eén tool voor CBS, DUO en RIO: de data_key uit get_cbs_data, get_duo_data of
get_rio_data wijst naar een DataFrame in de store. Bronspecifieke controles
komen van de bronmodules zelf: de CBS-dimensiecontrole (#162) en de DUO-
sentinelcellen die met de selectie meereizen (#171).
"""

import difflib
import hashlib
import json

import pandas as pd

from core.config import DUO_ROW_LIMIT

from . import duo, periode, store
from .catalog import rio_filters
from .cbs import check_dimensions_pinned

_SUPPORTED_OPS = frozenset({"eq", "gte", "lte", "in"})
_ALLOWED_AGG = {"sum", "mean", "count", "min", "max"}

# Grenzen voor de suggesties bij een leeg filterresultaat. Het scannen van
# unieke waarden is lineair in de kolomlengte, vandaar een bovengrens.
_SUGGESTIE_MAX_UNIEK = 500
_SUGGESTIE_AANTAL = 3
_SUGGESTIE_DREMPEL = 0.6


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
    df = df.copy()
    for col in aggregate:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.groupby(group_by, dropna=False).agg(aggregate).reset_index()


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


def _row_count(n: int, complete: bool) -> dict:
    """Rijtelling onder een naam die past: een afgekapte pagina heeft geen totaal (#177, #186)."""
    return {"totaal_rijen": n} if complete else {"opgehaalde_rijen": n, "volledig": False}


def _empty_melding(data_key: str, complete: bool) -> str:
    if complete:
        return "Het filter leverde 0 rijen op. Controleer de waarden hieronder voor je concludeert dat de data ontbreekt."
    melding = (
        "Het filter leverde 0 rijen op in deze pagina. Niet in deze pagina is niet hetzelfde als niet in de "
        "bron: de data is één afgekapte pagina."
    )
    known = store.meta(data_key)
    if known and known.bron == "rio" and (allowed := rio_filters(known.dataset)):
        melding += f" Filter op de server: get_rio_data('{known.dataset}', filters={{...}}) met een van {allowed}."
    return melding


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

    complete = store.volledig(data_key)
    if not complete and (group_by or aggregate):
        return store.ONVOLLEDIG

    if filters:
        origineel = df
        df, err = _apply_filters(df, filters)
        if err:
            return err
        if len(df) == 0:
            return json.dumps(
                {
                    "data_key": data_key,
                    **_row_count(0, complete),
                    "rijen": [],
                    "melding": _empty_melding(data_key, complete),
                    "suggesties": _filter_suggesties(origineel, filters),
                },
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )

    # De schooljaren van de selectie, vóór kolomkeuze en aggregatie: daarna kan de
    # periodekolom weg zijn terwijl de selectie wel op één jaar staat (#187).
    known = store.meta(data_key)
    schooljaren = periode.dekking(df, known.bron, known.periodekolom) if known else None

    if columns:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            return f"Kolommen niet gevonden: {missing}. Beschikbaar: {list(df.columns)}"

    # Vóór de kolomselectie: daarna zijn weggeselecteerde dimensies onzichtbaar.
    if aggregate or columns:
        err = check_dimensions_pinned(data_key, df, keep=(group_by or []) if aggregate else columns)
        if err:
            return err

    if columns:
        df = df[columns]

    cells = duo.select_cells(duo.sentinel_cells(data_key), df)
    notes = []
    if group_by or aggregate:
        err = _validate_aggregation(df, group_by, aggregate)
        if err:
            return err
        agg = _apply_aggregation(df, group_by, aggregate)
        # Juist hier telt de melding: dit is waar het getal ontstaat dat de gebruiker
        # leest, en onderdrukte cellen in de selectie maken dat totaal een ondergrens.
        notes = duo.sentinel_notes(duo.count_cells(cells))
        cells = duo.aggregate_cells(cells, df, group_by, agg)
        df = agg

    transformed = filters or columns or group_by
    if transformed:
        sig = json.dumps({"f": filters, "c": columns, "g": group_by, "a": aggregate}, sort_keys=True, default=str)
        suffix = hashlib.md5(sig.encode()).hexdigest()[:8]
        result_key = f"{data_key}:{suffix}"
        store.derive(data_key, result_key, df, schooljaren=schooljaren)
        # De afgeleide data is al gemaskeerd, dus put() vindt hier niets. De cellen
        # van de selectie reizen wel mee: het totaal blijft een ondergrens.
        duo.record_sentinel_cells(result_key, cells)
    else:
        result_key = data_key

    n_cols = len(df.columns)
    adaptive_max = max(30, min(max_rows, 2000 // max(n_cols, 1)))
    total = len(df)
    rows = df.head(adaptive_max).to_dict(orient="records")
    result: dict = {"data_key": result_key, **_row_count(total, complete), "rijen": rows}
    if notes:
        result["databewerking"] = notes
    warnings = [] if complete else [store.ONVOLLEDIG]
    if total > adaptive_max:
        warnings.append(
            f"Eerste {adaptive_max} van {total} rijen teruggegeven "
            f"({n_cols} kolommen × {adaptive_max} rijen). Verfijn je filters of selecteer minder kolommen."
        )
    if warnings:
        result["waarschuwing"] = " ".join(warnings)

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
