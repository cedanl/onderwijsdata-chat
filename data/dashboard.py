from __future__ import annotations

import pandas as pd
from riodata import duo

from .instellingen import resolve_alias


def _load_ho(instelling: str) -> pd.DataFrame:
    return pd.concat(
        [duo.load("p01hoinges", 0), duo.load("p01hoinges", 1)],
        ignore_index=True,
    )


def _filter_ho(df: pd.DataFrame, instelling: str) -> pd.DataFrame:
    col = "INSTELLINGSNAAM_ACTUEEL"
    if col not in df.columns:
        return df.iloc[0:0]
    return df[df[col].str.lower() == instelling.lower()]


def load_dashboard_ho(instelling: str) -> dict | None:
    try:
        df_inges = _load_ho(instelling)
        hu = _filter_ho(df_inges, instelling)
        if hu.empty:
            return None
    except Exception:
        return None

    result: dict = {}

    result["ingeschrevenen"] = (
        hu.groupby("STUDIEJAAR")["AANTAL_INGESCHREVENEN"].sum()
        .sort_index().to_dict()
    )

    laatste_jaar = hu["STUDIEJAAR"].max()
    result["geslacht"] = (
        hu[hu["STUDIEJAAR"] == laatste_jaar]
        .groupby("GESLACHT")["AANTAL_INGESCHREVENEN"].sum().to_dict()
    )
    result["laatste_jaar"] = int(laatste_jaar)

    result["sectoren"] = (
        hu[hu["STUDIEJAAR"] == laatste_jaar]
        .groupby("ONDERDEEL")["AANTAL_INGESCHREVENEN"].sum()
        .sort_values(ascending=False).to_dict()
    )

    try:
        df_1e = pd.concat(
            [duo.load("p02ho1ejrs", 0), duo.load("p02ho1ejrs", 1)],
            ignore_index=True,
        )
        hu1 = _filter_ho(df_1e, instelling)
        if not hu1.empty:
            result["eerstejaars"] = (
                hu1.groupby("STUDIEJAAR")["AANTAL_EERSTEJAARS_INGESCHREVENEN"].sum()
                .sort_index().to_dict()
            )
    except Exception:
        pass

    try:
        df_dipl = pd.concat(
            [duo.load("p04hogdipl", 0), duo.load("p04hogdipl", 1)],
            ignore_index=True,
        )
        hud = _filter_ho(df_dipl, instelling)
        if not hud.empty:
            result["gediplomeerden"] = (
                hud.groupby("DIPLOMAJAAR")["AANTAL_GEDIPLOMEERDEN"].sum()
                .sort_index().to_dict()
            )
    except Exception:
        pass

    return result


def load_dashboard_mbo(instelling: str) -> dict | None:
    try:
        df = duo.load("mbo-studenten-per-instelling", 0)
    except Exception:
        return None

    rows = df[df["INSTELLINGSNAAM"].str.lower() == instelling.lower()]
    if rows.empty:
        return None

    result: dict = {}

    per_jaar = rows.groupby("JAAR")[["BBL", "BOLDT", "BOLVT", "EX"]].sum()
    totals = per_jaar.sum(axis=1).astype(int)
    result["ingeschrevenen"] = totals.sort_index().to_dict()

    laatste_jaar = int(totals.index.max())
    result["laatste_jaar"] = laatste_jaar

    laatste = per_jaar.loc[laatste_jaar]
    sectoren = {
        "BBL": int(laatste["BBL"]),
        "BOL deeltijd": int(laatste["BOLDT"]),
        "BOL voltijd": int(laatste["BOLVT"]),
        "Extraneus": int(laatste["EX"]),
    }
    result["sectoren"] = {k: v for k, v in sorted(sectoren.items(), key=lambda x: -x[1]) if v > 0}

    try:
        df_dipl = duo.load("gediplomeerde-mbo-studenten", 0)
        dipl_rows = df_dipl[df_dipl["INSTELLINGSNAAM"].str.lower() == instelling.lower()]
        if not dipl_rows.empty:
            year_cols = [c for c in dipl_rows.columns if c.startswith("DIP")]
            gediplomeerden: dict[int, int] = {}
            for col in year_cols:
                jaar = int(col[-4:])
                gediplomeerden[jaar] = gediplomeerden.get(jaar, 0) + int(dipl_rows[col].sum())
            result["gediplomeerden"] = dict(sorted(gediplomeerden.items()))
    except Exception:
        pass

    return result


def load_dashboard(instelling: str) -> dict:
    instelling = resolve_alias(instelling)
    result: dict = {"instelling": instelling, "gevonden": False}

    ho = load_dashboard_ho(instelling)
    if ho:
        result["gevonden"] = True
        result.update(ho)
        return result

    mbo = load_dashboard_mbo(instelling)
    if mbo:
        result["gevonden"] = True
        result.update(mbo)
        return result

    try:
        df_ho = _load_ho(instelling)
        df_mbo = duo.load("mbo-studenten-per-instelling", 0)
        alle = sorted(set(
            df_ho["INSTELLINGSNAAM_ACTUEEL"].dropna().unique().tolist()
            + df_mbo["INSTELLINGSNAAM"].dropna().unique().tolist()
        ))
        result["beschikbare_instellingen"] = alle[:20]
    except Exception:
        pass

    return result
