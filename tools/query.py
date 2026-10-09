"""query_data: filteren, selecteren en aggregeren op een geladen dataset.

Eén tool voor CBS, DUO en RIO: de data_key uit get_cbs_data, get_duo_data of
get_rio_data wijst naar een DataFrame in de store. Bronspecifieke controles
komen van de bronmodules zelf: de CBS-dimensiecontrole (#162) en de DUO-
sentinelcellen die met de selectie meereizen (#171).
"""

import difflib
import hashlib
import json
from dataclasses import dataclass, field

import pandas as pd

from core.config import DUO_ROW_LIMIT

from . import afhankelijkheid, cbs_afronding, dekking, duo, fouten, instelling, kleine_aantallen, periode, store
from .catalog import resources_met_kolom
from .cbs import check_dimensions_known, check_dimensions_pinned
from .rio import rio_filters

_SUPPORTED_OPS = frozenset({"eq", "gte", "lte", "in"})
_ALLOWED_AGG = {"sum", "mean", "count", "nunique", "size", "min", "max"}
# Alleen deze rekenen met getallen. count, nunique en size tellen de oorspronkelijke
# waarden: een tekst- of UUID-kolom numeriek maken gaf overal 0 (#411).
NUMERIEKE_AGG = frozenset({"sum", "mean", "min", "max"})

# Grenzen voor de suggesties bij een leeg filterresultaat. Het scannen van
# unieke waarden is lineair in de kolomlengte, vandaar een bovengrens.
_SUGGESTIE_MAX_UNIEK = 500
_SUGGESTIE_AANTAL = 3
_SUGGESTIE_DREMPEL = 0.6
_MAX_INSTELLINGSLABELS = 5


def _coerce_pair(a, b):
    """Coerce two values to a comparable pair (float preferred, str fallback)."""
    try:
        return float(a), float(b)
    except (ValueError, TypeError):
        return str(a).lower(), str(b).lower()


def _stap(filters, columns, group_by, aggregate) -> str:
    """De selectie in woorden, met de argumenten zoals het model ze gaf (#118)."""
    delen = [("filters", filters), ("kolommen", columns), ("groepering", group_by), ("aggregatie", aggregate)]
    return "; ".join(
        f"{naam} {json.dumps(waarde, ensure_ascii=False, default=str)}" for naam, waarde in delen if waarde
    )


def _parse_filter_key(key: str) -> tuple[str, str]:
    if "__" in key:
        col, op = key.rsplit("__", 1)
    else:
        col, op = key, "eq"
    return col, op


def _resource_hint(known, col: str) -> str:
    """Wijs bij een kolom die in deze DUO-resource ontbreekt naar de resource die hem wel noemt (#173)."""
    if not known or known.bron != "duo":
        return ""
    andere = [(i, naam) for i, naam in resources_met_kolom(known.dataset, col) if i != known.resource]
    if not andere:
        return ""
    voorstellen = "; ".join(
        f"resource {i} ('{naam}'): get_duo_data('{known.dataset}', {i})" for i, naam in andere[:_SUGGESTIE_AANTAL]
    )
    return (
        f". Dat geldt alleen voor dit bestand: een andere resource van deze dataset heeft of noemt "
        f"'{col.lower()}': {voorstellen}."
    )


def _apply_filters(df, filters: dict, known=None):
    for key, val in filters.items():
        col, op = _parse_filter_key(key)

        if col not in df.columns:
            return (
                None,
                f"Kolom '{col}' bestaat niet. Beschikbare kolommen: {list(df.columns)}{_resource_hint(known, col)}",
            )
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


def _som_of_leeg(series):
    """Som, maar leeg als er geen enkele waarde is: onderdrukt is niet nul (#394)."""
    return series.sum(min_count=1)


def _apply_aggregation(df, group_by, aggregate):
    df = df.copy()
    for col, fn in aggregate.items():
        if fn in NUMERIEKE_AGG:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    fns = {col: _som_of_leeg if fn == "sum" else fn for col, fn in aggregate.items()}
    return df.groupby(group_by, dropna=False).agg(fns).reset_index()


def _lege_groepen_noten(agg, group_by, aggregate) -> list[str]:
    """Per som-kolom de groepen zonder één waarde: daar staat null, en dat is geen 0 (#394)."""
    noten = []
    for col, fn in aggregate.items():
        if fn != "sum" or not (leeg := agg[agg[col].isna()]).size:
            continue
        groepen = ", ".join(
            "/".join(f"{g}={rij[g]}" for g in group_by) for rij in leeg[group_by].to_dict(orient="records")
        )
        noten.append(
            f"'{col}' is voor {groepen} volledig onderdrukt of leeg (null): niet vast te stellen. "
            "Noem dit 'onderdrukt', nooit 0."
        )
    return noten


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
            dichtbij = difflib.get_close_matches(gezocht, aanwezig, n=_SUGGESTIE_AANTAL, cutoff=_SUGGESTIE_DREMPEL)
            hints[col] = dichtbij or aanwezig[:_SUGGESTIE_AANTAL]
        elif op in ("gte", "lte"):
            numeriek = pd.to_numeric(kolom, errors="coerce").dropna()
            if not numeriek.empty:
                hints[col] = f"bereik in de data: {numeriek.min()} t/m {numeriek.max()}"
    return hints


def _empty_melding(data_key: str, complete: bool) -> str:
    if complete:
        return (
            "Het filter leverde 0 rijen op. Controleer de waarden hieronder voor je concludeert dat de data ontbreekt."
        )
    melding = (
        "Het filter leverde 0 rijen op in deze pagina. Niet in deze pagina is niet hetzelfde als niet in de "
        "bron: de data is één afgekapte pagina."
    )
    known = store.meta(data_key)
    if known and known.bron == "rio" and (allowed := rio_filters(known.dataset)):
        melding += f" Filter op de server: get_rio_data('{known.dataset}', filters={{...}}) met een van {allowed}."
    return melding


_ONDERDRUKT = " (onderdrukte cellen)"
_GROEPSNOOT = (
    f"Een rij met '<kolom>{_ONDERDRUKT}' bevat in die groep cellen met -1: alleen dat totaal is een ondergrens, "
    "de andere totalen zijn exact. Noem niet elke groep een ondergrens."
)


def _met_onderdrukte_cellen(rows: list[dict], df: pd.DataFrame, cells: pd.DataFrame) -> bool:
    """Zet bij elk groepstotaal met onderdrukte cellen het aantal ernaast (CH-07); True als er een was.

    Zonder dit zei de melding 'totalen' en noemde het antwoord elke groep een ondergrens.
    Alleen in de tool-output: de store houdt de tabel van de bron.
    """
    gemarkeerd = False
    for row, index in zip(rows, df.index, strict=True):
        if index not in cells.index:
            continue
        for kolom, n in cells.loc[index].items():
            if n:
                row[f"{kolom}{_ONDERDRUKT}"] = int(n)
                gemarkeerd = True
    return gemarkeerd


def _met_ondergrens(rows: list[dict], df: pd.DataFrame, vier: pd.DataFrame) -> None:
    """Zet bij een som met als-4-cellen de ondergrens ernaast: het werkelijke totaal ligt ertussen (#406)."""
    for row, index in zip(rows, df.index, strict=True):
        if index not in vier.index:
            continue
        for kolom, n in vier.loc[index].items():
            if n and row.get(kolom) is not None:
                laag, _ = kleine_aantallen.bereik(row[kolom], int(n))
                row[f"{kolom} (ondergrens bij 1-4 als 4)"] = laag


@dataclass
class _Selectie:
    """De selectie tussen de stappen van query_data: de data, haar onderdrukte en als-4-cellen, en de noten."""

    df: pd.DataFrame
    cells: pd.DataFrame
    vier: pd.DataFrame | None
    vier_totaal: int | None
    notes: list[str] = field(default_factory=list)


def _leeg_resultaat(data_key: str, complete: bool, origineel: pd.DataFrame, filters: dict) -> str:
    return json.dumps(
        {
            "data_key": data_key,
            **store.rijtelling(0, complete),
            "rijen": [],
            "melding": _empty_melding(data_key, complete),
            "suggesties": _filter_suggesties(origineel, filters),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _instellingslabels(df: pd.DataFrame, known, gedekt: dict) -> dict | None:
    """Bij een paar instellingen de naam naast de code: 30TX is Aeres, niet de HU (#143)."""
    if known and 0 < len(gedekt.get("instellingen") or ()) <= _MAX_INSTELLINGSLABELS:
        return instelling.namen(df, known.instellingskolom)
    return None


def _kolomfout(data_key: str, df: pd.DataFrame, columns, group_by, aggregate) -> str | None:
    """Ontbrekende kolommen en de CBS-dimensiecontrole (#162), vóór de kolomselectie:
    daarna zijn weggeselecteerde dimensies onzichtbaar."""
    if columns and (missing := [c for c in columns if c not in df.columns]):
        return f"Kolommen niet gevonden: {missing}. Beschikbaar: {list(df.columns)}"
    if aggregate and (err := check_dimensions_known(data_key)):
        return err
    if aggregate or columns:
        return check_dimensions_pinned(data_key, df, keep=(group_by or []) if aggregate else columns)
    return None


def _per_jaar(data_key: str, df: pd.DataFrame, columns, known, kolom: str | None) -> dict:
    """Onderdrukte cellen per jaar, vóór kolomkeuze en aggregatie: daarna is de periodekolom er
    misschien niet meer (CH-07)."""
    if not known or kolom not in df.columns:
        return {}
    cellen = duo.select_cells(duo.sentinel_cells(data_key), df[columns] if columns else df)
    return duo.per_periode(cellen, df[kolom], known.bron)


def _selectie(data_key: str, df: pd.DataFrame, known) -> _Selectie:
    vier = kleine_aantallen.vier_cellen(df) if known and known.vier_regel else None
    return _Selectie(
        df=df,
        cells=duo.select_cells(duo.sentinel_cells(data_key), df),
        vier=vier,
        vier_totaal=int(vier.to_numpy().sum()) if vier is not None else None,
    )


def _aggregeer(sel: _Selectie, data_key: str, group_by: list[str] | None, aggregate) -> _Selectie | str:
    """De groepering, met de cellen die meegaan naar elke groep; een foutmelding als ze niet kan."""
    if err := _validate_aggregation(sel.df, group_by, aggregate):
        return err
    group_by = group_by or []  # na de validatie niet leeg: group_by en aggregate komen samen
    agg = _apply_aggregation(sel.df, group_by, aggregate)
    # Juist hier telt de melding: dit is waar het getal ontstaat dat de gebruiker
    # leest, en onderdrukte cellen in de selectie maken dat totaal een ondergrens.
    notes = duo.sentinel_notes(duo.count_cells(sel.cells)) + _lege_groepen_noten(agg, group_by, aggregate)
    if noot := cbs_afronding.van_key(data_key):
        notes.append(noot)
    vier = sel.vier
    if vier is not None and sel.vier_totaal:
        notes += kleine_aantallen.noten({str(c): int(n) for c, n in vier.sum().items() if n})
        vier = duo.aggregate_cells(vier, sel.df, group_by, agg)
    cells = duo.aggregate_cells(sel.cells, sel.df, group_by, agg)
    return _Selectie(df=agg, cells=cells, vier=vier, vier_totaal=sel.vier_totaal, notes=notes)


def _bewaar(data_key: str, sel: _Selectie, filters, columns, group_by, aggregate, gedekt: dict) -> str:
    """De afgeleide key van een selectie; de key zelf als er niets gekozen is."""
    if not (filters or columns or group_by):
        return data_key
    sig = json.dumps({"f": filters, "c": columns, "g": group_by, "a": aggregate}, sort_keys=True, default=str)
    result_key = f"{data_key}:{hashlib.md5(sig.encode()).hexdigest()[:8]}"
    store.derive(
        data_key,
        result_key,
        sel.df,
        stap=_stap(filters, columns, group_by, aggregate),
        vier_cellen=sel.vier_totaal,
        **gedekt,
    )
    # De afgeleide data is al gemaskeerd, dus put() vindt hier niets. De cellen
    # van de selectie reizen wel mee: het totaal blijft een ondergrens.
    duo.record_sentinel_cells(result_key, sel.cells, groepen=bool(group_by or aggregate))
    return result_key


def _rijen(sel: _Selectie, known, maximum: int, gegroepeerd: bool) -> list[dict]:
    """De rijen voor het model, met de grenzen per groep ernaast; de noten erbij in `sel`."""
    afronden = duo.is_prognose(known)
    if afronden:
        sel.notes.append(duo.PROGNOSE_NOOT)
    getoond = sel.df.head(maximum)
    rows = [{k: duo.json_waarde(v, afronden) for k, v in row.items()} for row in getoond.to_dict(orient="records")]
    if sel.vier is not None and sel.vier_totaal and gegroepeerd:
        _met_ondergrens(rows, getoond, sel.vier)
    if gegroepeerd and _met_onderdrukte_cellen(rows, getoond, sel.cells):
        sel.notes.append(_GROEPSNOOT)
    return rows


def _waarschuwing(complete: bool, total: int, maximum: int, n_cols: int) -> str | None:
    warnings = [] if complete else [store.ONVOLLEDIG]
    if total > maximum:
        warnings.append(
            f"Eerste {maximum} van {total} rijen teruggegeven "
            f"({n_cols} kolommen × {maximum} rijen). Verfijn je filters of selecteer minder kolommen."
        )
    return " ".join(warnings) or None


def _resultaat(result_key: str, sel: _Selectie, known, labels, complete: bool, max_rows: int, gegroepeerd: bool) -> str:
    n_cols = len(sel.df.columns)
    maximum = max(30, min(max_rows, 2000 // max(n_cols, 1)))
    total = len(sel.df)
    rows = _rijen(sel, known, maximum, gegroepeerd)
    result: dict = {"data_key": result_key, **store.rijtelling(total, complete), "rijen": rows}
    if known and known.scriptconstanten:
        # Een eigen berekening maakte deze getallen; ook hier zijn ze geen bron (CH-27, #456).
        result[afhankelijkheid.SCRIPTCONSTANTEN] = list(known.scriptconstanten)
    if labels:
        result["instellingen"] = labels
    if sel.notes:
        result["databewerking"] = sel.notes
    if waarschuwing := _waarschuwing(complete, total, maximum, n_cols):
        result["waarschuwing"] = waarschuwing
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)


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
        return fouten.onbekende_key(data_key)

    complete = store.volledig(data_key)
    if not complete and (group_by or aggregate):
        return store.ONVOLLEDIG

    if filters:
        gefilterd, err = _apply_filters(df, filters, store.meta(data_key))
        if err:
            return err
        if len(gefilterd) == 0:
            return _leeg_resultaat(data_key, complete, df, filters)
        df = gefilterd

    # Wat de selectie bevat, vóór kolomkeuze en aggregatie (#187, #143).
    known = store.meta(data_key)
    gedekt = dekking.van(df, known)
    labels = _instellingslabels(df, known, gedekt)
    if err := _kolomfout(data_key, df, columns, group_by, aggregate):
        return err
    kolom = known.periodekolom if known else None
    per_jaar = _per_jaar(data_key, df, columns, known, kolom)

    sel = _selectie(data_key, df[columns] if columns else df, known)
    cellen_noot = duo.cellen_noot(sel.cells)
    gegroepeerd = bool(group_by or aggregate)
    if gegroepeerd:
        group_by = periode.met_labelkolom_in_groep(sel.df, group_by)
        geaggregeerd = _aggregeer(sel, data_key, group_by, aggregate)
        if isinstance(geaggregeerd, str):
            return geaggregeerd
        sel = geaggregeerd
    sel.notes += cellen_noot + duo.periode_noot(per_jaar, kolom or "")

    result_key = _bewaar(data_key, sel, filters, columns, group_by, aggregate, gedekt)
    return _resultaat(result_key, sel, known, labels, complete, max_rows, gegroepeerd)
