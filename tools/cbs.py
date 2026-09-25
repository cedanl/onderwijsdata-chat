import hashlib
import json
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

import httpx
import pandas as pd
from onderwijsdata import data, definitions
from onderwijsdata.client import get

from core.config import CBS_ROW_LIMIT

from . import store
from .catalog import catalogus_laatste_update, catalogus_titel
from .columns import sample_values

_SAMPLE_ROWS = 5
_MAX_GENOEMDE_WAARDEN = 5

# Dimensiekolommen per CBS-dataset-ID, vastgelegd bij get_cbs_data. Per dataset en
# niet per key, zodat afgeleide keys (cbs:<id>:<hash>) ze zonder netwerk vinden.
_dimensies: dict[str, list[str]] = {}


def register_dimensions(dataset_id: str, columns: list[str]) -> None:
    _dimensies[dataset_id] = list(columns)


def clear_dimensions() -> None:
    _dimensies.clear()


def dimension_columns(data_key: str) -> list[str]:
    """Dimensiekolommen voor een `cbs:`-key; leeg als ze niet bekend zijn."""
    parts = data_key.split(":")
    if parts[0] != "cbs" or len(parts) < 2:
        return []
    return _dimensies.get(parts[1], [])


def check_dimensions_pinned(data_key: str, df: pd.DataFrame, keep: list[str]) -> str | None:
    """Weiger een CBS-selectie die een dimensie met meerdere waarden laat wegvallen.

    CBS-tabellen bevatten totaalrijen naast hun onderdelen ("Opleidingsfase totaal"
    naast bachelor en master), en die zijn niet aan hun code te herkennen. Een
    dimensie die niet in `keep` staat, moet daarom op één waarde vastliggen; anders
    telt een som dubbel (#162) of worden rijen ononderscheidbaar.
    """
    open_dims = {
        col: sorted(df[col].dropna().astype(str).unique())
        for col in dimension_columns(data_key)
        if col in df.columns and col not in keep and df[col].nunique() > 1
    }
    if not open_dims:
        return None
    details = "; ".join(
        f"{col} ({len(vals)} waarden: {', '.join(vals[:_MAX_GENOEMDE_WAARDEN])}"
        f"{', …' if len(vals) > _MAX_GENOEMDE_WAARDEN else ''})"
        for col, vals in open_dims.items()
    )
    return (
        f"Deze selectie telt meerdere categorieën van dezelfde dimensie samen: {details}. "
        "CBS-tabellen bevatten totaalrijen naast hun onderdelen, dus dat telt dubbel. "
        "Filter elke dimensie op één waarde (meestal de totaalcode, zie get_cbs_dimension) "
        "of neem hem op in group_by/columns."
    )


def _load_definitions(dataset_id: str) -> dict:
    try:
        return definitions(dataset_id)
    except Exception as e:
        logger.warning("CBS DataProperties ophalen mislukt voor %s: %s", dataset_id, e)
        return {}


def _dimension_names(col_defs: dict) -> list[str]:
    return [col for col, d in col_defs.items() if d.get("type", "").endswith("Dimension")]


def _select_with_dimensions(select: str, dims: list[str]) -> str:
    """Een $select zonder dimensies levert ononderscheidbare rijen op (#162)."""
    cols = [c.strip() for c in select.split(",") if c.strip()]
    return ",".join(cols + [d for d in dims if d not in cols])


_PERIODESTATUS = "Periodestatus"
_LABEL_SUFFIX = "_label"
_PERIODESTATUS_DEFINITIE = (
    "CBS-status van de periode uit Perioden.Status (bijv. Definitief, Voorlopig, "
    "Nader voorlopig). Gebruik deze kolom; leid de status niet af uit de periodecode. "
    "Groepeer je op de tijddimensie, neem Periodestatus dan mee in group_by."
)


@lru_cache(maxsize=256)
def _dimension_rows(dataset_id: str, dimension_name: str) -> tuple[dict, ...]:
    """Ruwe CBS-dimensierijen (Key, Title en waar de bron hem heeft Status).

    Eén bron voor labels, periodestatus en get_cbs_dimension. Een mislukte call
    wordt niet gecachet: lru_cache bewaart geen exceptions.
    """
    return tuple(
        {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}
        for row in get(dataset_id, dimension_name)
    )


def _add_dimension_context(df: pd.DataFrame, dataset_id: str, col_defs: dict) -> pd.DataFrame:
    """Zet naast elke dimensiecode het officiële label en de periodestatus.

    Het label ("Voltijd" naast A028666) voorkomt dat een model een code zelf
    vertaalt (#163); de status reist met de rij mee naar query_data, grafiek en
    rapport (#180). Levert CBS een dimensie niet, dan geen kolom: niets raden.
    """
    extra: dict[str, pd.Series] = {}
    for dim in _dimension_names(col_defs):
        if dim not in df.columns:
            continue
        try:
            rows = _dimension_rows(dataset_id, dim)
        except Exception as e:
            logger.warning("CBS-dimensie %s ophalen mislukt voor %s: %s", dim, dataset_id, e)
            continue
        titles = {r["Key"]: r["Title"] for r in rows if r.get("Title")}
        if titles:
            extra[dim + _LABEL_SUFFIX] = df[dim].map(titles)
        statuses = {r["Key"]: r["Status"] for r in rows if r.get("Status")}
        if statuses:
            extra[_PERIODESTATUS] = df[dim].map(statuses)
    return df.assign(**extra)


def _column_definition(col: str, col_defs: dict) -> str | None:
    if col == _PERIODESTATUS:
        return _PERIODESTATUS_DEFINITIE
    if col.endswith(_LABEL_SUFFIX) and col.removesuffix(_LABEL_SUFFIX) in col_defs:
        return (
            f"Officiële CBS-titel van de code in {col.removesuffix(_LABEL_SUFFIX)}. "
            "Gebruik dit label in tekst en grafieken; vertaal codes niet zelf. "
            "Groepeer je op de code, neem het label dan mee in group_by."
        )
    return col_defs.get(col, {}).get("description") or None


def get_cbs_data(dataset_id: str, filters: dict | None = None) -> str:
    params = dict(filters or {})
    if "$top" not in params:
        params["$top"] = CBS_ROW_LIMIT
    if "$select" in params:
        params["$select"] = _select_with_dimensions(
            params["$select"], _dimension_names(_load_definitions(dataset_id))
        )
    try:
        rows = data(dataset_id, **params)
    except Exception as e:
        return f"Fout bij ophalen CBS data: {e}"
    if not rows:
        return (
            f"Geen rijen gevonden in dataset '{dataset_id}' met filters {filters or {}}. "
            "Controleer de filtercodes via get_cbs_dimension — CBS gebruikt interne codes, geen leesbare labels."
        )

    col_defs = _load_definitions(dataset_id)
    df = _add_dimension_context(pd.DataFrame(rows[:CBS_ROW_LIMIT]), dataset_id, col_defs)
    filter_hash = hashlib.md5(json.dumps(filters or {}, sort_keys=True).encode()).hexdigest()[:8]
    key = f"cbs:{dataset_id}:{filter_hash}" if filters else f"cbs:{dataset_id}"
    store.put(key, df)

    dims = _dimension_names(col_defs)
    if dims:  # een mislukte DataProperties-call mag een eerdere registratie niet wissen
        register_dimensions(dataset_id, dims)
    schema = [
        {
            "kolom": col,
            "type": str(df[col].dtype),
            "voorbeelden": sample_values(df[col], 5),
            **({"definitie": d} if (d := _column_definition(col, col_defs)) else {}),
            **({"eenheid": col_defs[col]["unit"]} if col in col_defs and col_defs[col].get("unit") else {}),
        }
        for col in df.columns
    ]
    preview = df.head(_SAMPLE_ROWS).to_dict(orient="records")
    truncated = len(rows) >= CBS_ROW_LIMIT

    result = {
        "data_key": key,
        "catalogus_titel": catalogus_titel(dataset_id),
        "totaal_rijen": len(df),
        "kolommen": schema,
        "preview": preview,
    }

    # Include data actuality timestamp
    laatste_update = catalogus_laatste_update(dataset_id)
    if laatste_update:
        result["laatste_update"] = laatste_update

    if truncated:
        result["waarschuwing"] = f"Afgekapt op {CBS_ROW_LIMIT} rijen. Verfijn $filter of $select voor volledigere data."

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)


def get_cbs_dimension(dataset_id: str, dimension_name: str) -> str:
    """Code → titel; bij een dimensie met status (Perioden) code → {titel, status} (#180)."""
    try:
        rows = _dimension_rows(dataset_id, dimension_name)
    except Exception as e:
        reason = f"HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else str(e)
        return (
            f"Dimensie '{dimension_name}' niet gevonden in {dataset_id} ({reason}). "
            f"Beschikbare dimensies: {_dimension_names(_load_definitions(dataset_id))}. "
            "De status van een periode is geen dimensie: die staat bij Perioden en als "
            f"kolom {_PERIODESTATUS} in get_cbs_data."
        )
    values = {
        r["Key"]: {"titel": r["Title"], "status": r["Status"]} if r.get("Status") else r["Title"]
        for r in rows
    }
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))
