import difflib
import hashlib
import json

import pandas as pd
from riodata import duo as _duo

from core.config import DUO_ROW_LIMIT

from . import store
from .catalog import catalogus_titel, resource_titel
from .cbs import check_dimensions_pinned

_SAMPLE_ROWS = 3

_SUPPORTED_OPS = frozenset({"eq", "gte", "lte", "in"})

# Lokale glossary-correcties voor upstream fouten in riodata (zie #31, #23)
# Deze patches worden toegepast op column_definitions() om tot de upstream fix.
_GLOSSARY_PATCHES = {
    "STUDIEJAAR": "Startjaar van het studiejaar als geheel getal (2023 = studiejaar 2023/2024). Peildatum 1 oktober.",
    "LEERWEG": "Mbo-leerweg: BOL (beroepsopleidende leerweg) of BBL (beroepsbegeleidende leerweg).",
}


def _apply_glossary_patches(defs: dict[str, str]) -> dict[str, str]:
    """Pas lokale correcties toe op riodata glossary-definities.

    Zie #31, #23: upstream bugs in STUDIEJAAR en LEERWEG definities in riodata.
    Deze patches zorgen dat het schema correcte definities bevat totdat upstream dit
    adressen. Idempotent: kan veilig op al gepatched dicts worden toegepast.
    """
    return {**defs, **_GLOSSARY_PATCHES}

# Grenzen voor de suggesties bij een leeg filterresultaat. Het scannen van
# unieke waarden is lineair in de kolomlengte, vandaar een bovengrens.
_SUGGESTIE_MAX_UNIEK = 500
_SUGGESTIE_AANTAL = 3
_SUGGESTIE_DREMPEL = 0.6

_DUO_SENTINELS = (-1,)

# Kolommen waarin -1 een geldige meetwaarde kan zijn in plaats van een onderdrukte cel.
# Niet beperken tot AANTAL*-kolommen: DUO kent pivot-datasets waarin de telling in de
# kolomnaam zit (DIPMAN2023, JAAR_2022 — zie prompts/system.md), en die zouden dan
# ongemaskeerd blijven.
_SIGNED_HINTS = ("MUTATIE", "SALDO", "VERSCHIL", "GROEI", "DELTA")

# Per store-key: aantal gemaskeerde cellen per rij en kolom, alleen voor rijen met
# minstens één (sparse). Per rij en niet per key, zodat query_data de telling met
# dezelfde filter/selectie/groupby als de data kan meenemen: de melding hoort bij de
# geselecteerde rijen, niet bij de hele dataset (#171). Na maskering is het aantal
# niet meer uit de data af te leiden: de -1'en zijn dan weg.
_sentinel_cells: dict[str, pd.DataFrame] = {}
_EMPTY_CELLS = pd.DataFrame()


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


def _is_maskable(df, col) -> bool:
    if not pd.api.types.is_numeric_dtype(df[col]):
        return False
    return not any(hint in str(col).upper() for hint in _SIGNED_HINTS)


def mask_sentinels(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Vervang DUO-sentinels (-1) door pd.NA en geef per rij aan welke cellen dat waren.

    DUO markeert onderdrukte waarden (kleine aantallen) met -1. Die mogen nooit als
    telwaarde meedoen. De cellen worden bijgehouden omdat een onderdrukte cel betekent
    dat een totaal een ondergrens is: bij 2 onderdrukte cellen kan 300 in werkelijkheid
    hoger liggen, en dat moet de gebruiker kunnen zien.

    Geeft (gemaskeerde df, cellen) terug; `cellen` heeft de index van df, alleen rijen
    met minstens één sentinel, en per maskeerbare kolom het aantal (0/1).

    Wordt aangeroepen vanuit store.put() voor elke `duo:`-key, dus ook voor data die
    niet via get_duo_data binnenkomt. Idempotent: al gemaskeerde data levert niets op.
    """
    masks = {}
    for col in df.columns:
        if _is_maskable(df, col):
            mask = df[col].isin(_DUO_SENTINELS)
            if mask.any():
                masks[col] = mask
    if not masks:
        return df, _EMPTY_CELLS
    # Pas kopiëren als er echt iets te maskeren valt: put() draait dit op elke
    # DataFrame die de store in gaat, ook de al gemaskeerde.
    out = df.copy()
    for col, mask in masks.items():
        out.loc[mask, col] = pd.NA
    cells = pd.DataFrame(masks).astype(int)
    return out, cells[cells.any(axis=1)]


def count_cells(cells: pd.DataFrame | None) -> dict[str, int]:
    """Aantal gemaskeerde cellen per kolom; kolommen zonder cellen vallen weg."""
    if cells is None or cells.empty:
        return {}
    return {col: int(n) for col, n in cells.sum().items() if n}


def record_sentinel_cells(key: str, cells: pd.DataFrame) -> None:
    """Leg vast welke cellen er voor deze key gemaskeerd zijn.

    Wordt door store.put() aangeroepen, zodat de telling er is ongeacht via welke route
    de data binnenkwam — niet alleen bij get_duo_data.
    """
    _sentinel_cells[key] = cells


def clear_sentinel_cells() -> None:
    """Hoort bij store.clear(): zonder dit blijven tellingen achter voor keys die weg zijn."""
    _sentinel_cells.clear()


def _select_cells(cells: pd.DataFrame | None, df: pd.DataFrame) -> pd.DataFrame:
    """Beperk de cellen tot de rijen en kolommen die in de selectie `df` zitten."""
    if cells is None or cells.empty:
        return _EMPTY_CELLS
    return cells.loc[cells.index.intersection(df.index), [c for c in cells.columns if c in df.columns]]


def _aggregate_cells(cells: pd.DataFrame, df: pd.DataFrame, group_by: list[str], agg: pd.DataFrame) -> pd.DataFrame:
    """Tel de cellen per groep op, uitgelijnd op de rijen van het aggregaat `agg`."""
    # Alleen geaggregeerde waardekolommen; een groepeerkolom zit al in df[group_by].
    cells = cells[[c for c in cells.columns if c in agg.columns and c not in group_by]]
    if cells.empty:
        return _EMPTY_CELLS
    per_group = cells.join(df[group_by]).groupby(group_by, dropna=False).sum().reset_index()
    rows = agg[group_by].reset_index().merge(per_group, on=group_by).set_index("index")
    rows.index.name = None
    return rows[list(cells.columns)]


def sentinel_notes(counts: dict[str, int]) -> list[str]:
    """Leesbare melding per kolom met onderdrukte cellen, voor in de tool-output."""
    return [
        f"{n} cellen met DUO-sentinel -1 in '{col}' uitgesloten "
        f"(betekent leeg/n.v.t., geen telwaarde) — totalen zijn hierdoor een ondergrens"
        for col, n in counts.items()
    ]


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
        store.put(key, df)
        # put() maskeert een kopie, dus de lokale df is nog ongemaskeerd: schema en
        # preview moeten van de versie komen die daadwerkelijk is opgeslagen.
        df = store.get(key)

    defs = _apply_glossary_patches(_duo.column_definitions(list(df.columns)))
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

    result = {
        "data_key": key,
        "catalogus_titel": catalogus_titel(dataset_id),
        "resource_titel": resource_titel(dataset_id, resource),
        "totaal_rijen": len(df),
        "kolommen": schema,
        "preview": preview,
    }
    notes = sentinel_notes(count_cells(_sentinel_cells.get(key)))
    if notes:
        result["databewerking"] = notes

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)


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

    # Vóór de kolomselectie: daarna zijn weggeselecteerde dimensies onzichtbaar.
    if aggregate or columns:
        err = check_dimensions_pinned(data_key, df, keep=(group_by or []) if aggregate else columns)
        if err:
            return err

    if columns:
        df = df[columns]

    cells = _select_cells(_sentinel_cells.get(data_key), df)
    notes = []
    if group_by or aggregate:
        err = _validate_aggregation(df, group_by, aggregate)
        if err:
            return err
        agg = _apply_aggregation(df, group_by, aggregate)
        # Juist hier telt de melding: dit is waar het getal ontstaat dat de gebruiker
        # leest, en onderdrukte cellen in de selectie maken dat totaal een ondergrens.
        notes = sentinel_notes(count_cells(cells))
        cells = _aggregate_cells(cells, df, group_by, agg)
        df = agg

    transformed = filters or columns or group_by
    if transformed:
        sig = json.dumps({"f": filters, "c": columns, "g": group_by, "a": aggregate}, sort_keys=True, default=str)
        suffix = hashlib.md5(sig.encode()).hexdigest()[:8]
        result_key = f"{data_key}:{suffix}"
        store.put(result_key, df)
        # De afgeleide data is al gemaskeerd, dus put() vindt hier niets. De cellen
        # van de selectie reizen wel mee: het totaal blijft een ondergrens.
        _sentinel_cells[result_key] = cells
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
