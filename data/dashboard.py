from __future__ import annotations

import functools
import json
from pathlib import Path

import pandas as pd
from riodata import duo

from .instellingen import resolve_alias


# ─── Regiodashboard ──────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _load_mbo_studenten() -> pd.DataFrame:
    return duo.load("mbo-studenten-per-instelling", 0)


@functools.lru_cache(maxsize=1)
def _load_mbo_gediplomeerden() -> pd.DataFrame:
    return duo.load("gediplomeerde-mbo-studenten", 0)


@functools.lru_cache(maxsize=1)
def _load_ho_full() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inges = pd.concat([duo.load("p01hoinges", 0), duo.load("p01hoinges", 1)], ignore_index=True)
    eerstejaars = pd.concat([duo.load("p02ho1ejrs", 0), duo.load("p02ho1ejrs", 1)], ignore_index=True)
    dipl = pd.concat([duo.load("p04hogdipl", 0), duo.load("p04hogdipl", 1)], ignore_index=True)
    return inges, eerstejaars, dipl


def _mode_str(series: pd.Series) -> str | None:
    vals = series.dropna()
    if vals.empty:
        return None
    return str(vals.mode().iloc[0])


def _gemiddelde_per_jaar(
    df: pd.DataFrame,
    jaar_col: str,
    waarde_col: str,
    prov_col: str,
    provincie: str,
    inst_col: str,
    exclude_inst: str,
) -> dict[int, float]:
    subset = df[
        (df[prov_col].str.lower() == provincie.lower()) &
        (df[inst_col].str.lower() != exclude_inst.lower())
    ]
    if subset.empty:
        return {}
    per_inst_jaar = subset.groupby([inst_col, jaar_col])[waarde_col].sum().reset_index()
    gem = per_inst_jaar.groupby(jaar_col)[waarde_col].mean()
    return {int(k): round(float(v)) for k, v in gem.items()}


def _totaal_provincie(
    df: pd.DataFrame,
    jaar_col: str,
    waarde_col: str,
    prov_col: str,
    provincie: str,
    inst_col: str,
    exclude_inst: str,
) -> dict[int, int]:
    subset = df[
        (df[prov_col].str.lower() == provincie.lower()) &
        (df[inst_col].str.lower() != exclude_inst.lower())
    ]
    if subset.empty:
        return {}
    totaal = subset.groupby(jaar_col)[waarde_col].sum()
    return {int(k): int(v) for k, v in totaal.items()}


def _load_sector_cluster_map() -> dict[str, list[str]]:
    """Laad sector→cluster mapping uit JSON-bestand gegenereerd door refresh_sector_mapping.py."""
    path = Path(__file__).parent / "sector_cluster_mapping.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


_SECTOR_CLUSTER_MAP: dict[str, list[str]] = _load_sector_cluster_map()


@functools.lru_cache(maxsize=None)
def _uwv_raw_clusters(provincie: str) -> tuple[int, str, dict[str, int]]:
    """Alle UWV beroepencluster-aantallen voor de provincie, gesorteerd op grootte."""
    try:
        from riodata import uwv
        df = uwv.load("latest", rec_type="Vacature")
        if df.empty or "PROVINCIE" not in df.columns:
            return 0, "onbekend", {}
        subset = df[df["PROVINCIE"].str.lower() == provincie.lower()]
        if subset.empty:
            return 0, "onbekend", {}
        totaal = int(subset["AANTAL"].sum())
        per_cluster = (
            subset.groupby("BEROEPENCLUSTER")["AANTAL"]
            .sum().sort_values(ascending=False)
        )
        return totaal, "mei 2023", {str(k): int(v) for k, v in per_cluster.items()}
    except Exception:
        return 0, "onbekend", {}


def _uwv_vacatures_provincie(provincie: str, sectoren: tuple[str, ...] = ()) -> dict:
    """Top-8 vacatures, gefilterd op instellingssectoren indien opgegeven."""
    totaal, peildatum, alle_clusters = _uwv_raw_clusters(provincie)
    if not alle_clusters:
        return {}

    if sectoren and _SECTOR_CLUSTER_MAP:
        clusters_voor_sectoren = {
            cluster
            for s in sectoren
            for cluster in _SECTOR_CLUSTER_MAP.get(s, [])
        }
        if clusters_voor_sectoren:
            gefilterd = {
                naam: aantal for naam, aantal in alle_clusters.items()
                if naam in clusters_voor_sectoren
            }
            if gefilterd:
                top = dict(sorted(gefilterd.items(), key=lambda x: -x[1])[:8])
                return {
                    "totaal": totaal,
                    "peildatum": peildatum,
                    "clusters": top,
                    "gefilterd_op": sorted(sectoren),
                }

    top = dict(list(alle_clusters.items())[:8])
    return {
        "totaal": totaal,
        "peildatum": peildatum,
        "clusters": top,
        "gefilterd_op": [],
    }


@functools.lru_cache(maxsize=None)
def _roa_schoolverlaters(onderwijs_type: str) -> dict:
    """Return ROA schoolverlaters metrics for 'ho' or 'mbo'."""
    try:
        from riodata import roa
        df = roa.load("ais2030", "arbeidsmarkt")
        sv = df[df["thema"] == "Schoolverlatersinformatie (SIS 2024)"]
        if onderwijs_type == "ho":
            niveaus = ["Bachelor", "Master, doctor"]
        else:
            niveaus = ["Mbo4", "Mbo3", "Mbo2"]
        subset = sv[
            (sv["aggregatieniveau"] == "opleidingsniveau (ONR2019)") &
            (sv["detailniveau"].isin(niveaus))
        ]
        indicatoren = ["werkloosheid", "vast dienstverband", "buiten de vakrichting"]
        rows = subset[subset["onderwerp"].isin(indicatoren)][["detailniveau", "onderwerp", "perc"]]
        rows = rows.dropna(subset=["perc"])
        if rows.empty:
            return {}
        out: dict = {}
        for _, row in rows.iterrows():
            niveau = str(row["detailniveau"])
            indicator = str(row["onderwerp"])
            out.setdefault(niveau, {})[indicator] = int(row["perc"])
        return out
    except Exception:
        return {}


def _load_dashboard_regio_ho(instelling: str) -> dict | None:
    try:
        df_inges, df_ej, df_dipl = _load_ho_full()
    except Exception:
        return None

    inst_col = "INSTELLINGSNAAM_ACTUEEL"
    prov_col = "PROVINCIENAAM"

    hu_inges = df_inges[df_inges[inst_col].str.lower() == instelling.lower()]
    if hu_inges.empty:
        return None

    result: dict = {"type": "ho"}
    provincie = _mode_str(hu_inges[prov_col])
    result["provincie"] = provincie or "Onbekend"

    laatste_jaar = int(hu_inges["STUDIEJAAR"].max())
    result["laatste_jaar"] = laatste_jaar

    result["ingeschrevenen"] = (
        hu_inges.groupby("STUDIEJAAR")["AANTAL_INGESCHREVENEN"].sum()
        .sort_index().apply(int).to_dict()
    )

    laatste = hu_inges[hu_inges["STUDIEJAAR"] == laatste_jaar]
    result["geslacht"] = {
        "VROUW": int(laatste[laatste["GESLACHT"] == "VROUW"]["AANTAL_INGESCHREVENEN"].sum()),
        "MAN": int(laatste[laatste["GESLACHT"] == "MAN"]["AANTAL_INGESCHREVENEN"].sum()),
    }
    result["sectoren"] = (
        laatste.groupby("ONDERDEEL")["AANTAL_INGESCHREVENEN"].sum()
        .sort_values(ascending=False).apply(int).to_dict()
    )

    hu_ej = df_ej[df_ej[inst_col].str.lower() == instelling.lower()]
    if not hu_ej.empty:
        result["eerstejaars"] = (
            hu_ej.groupby("STUDIEJAAR")["AANTAL_EERSTEJAARS_INGESCHREVENEN"].sum()
            .sort_index().apply(int).to_dict()
        )

    hu_dipl = df_dipl[df_dipl[inst_col].str.lower() == instelling.lower()]
    if not hu_dipl.empty:
        result["gediplomeerden"] = (
            hu_dipl.groupby("DIPLOMAJAAR")["AANTAL_GEDIPLOMEERDEN"].sum()
            .sort_index().apply(int).to_dict()
        )

    if provincie:
        n = int(
            df_inges[
                (df_inges[prov_col].str.lower() == provincie.lower()) &
                (df_inges[inst_col].str.lower() != instelling.lower())
            ][inst_col].nunique()
        )
        result["benchmark"] = {
            "label": f"Provinciaal gemiddelde ({provincie}, excl. eigen instelling)",
            "n_instellingen": n,
            "ingeschrevenen": _gemiddelde_per_jaar(
                df_inges, "STUDIEJAAR", "AANTAL_INGESCHREVENEN", prov_col, provincie, inst_col, instelling
            ),
            "eerstejaars": _gemiddelde_per_jaar(
                df_ej, "STUDIEJAAR", "AANTAL_EERSTEJAARS_INGESCHREVENEN", prov_col, provincie, inst_col, instelling
            ),
            "gediplomeerden": _gemiddelde_per_jaar(
                df_dipl, "DIPLOMAJAAR", "AANTAL_GEDIPLOMEERDEN", prov_col, provincie, inst_col, instelling
            ),
            "totaal_ingeschrevenen": _totaal_provincie(
                df_inges, "STUDIEJAAR", "AANTAL_INGESCHREVENEN", prov_col, provincie, inst_col, instelling
            ),
        }

    result["arbeidsmarkt_roa"] = _roa_schoolverlaters("ho")
    if provincie:
        ho_sectoren = tuple(sorted(result.get("sectoren", {}).keys()))
        result["vacatureaanbod"] = _uwv_vacatures_provincie(provincie, ho_sectoren)
    else:
        result["vacatureaanbod"] = {}
    result["methodologie"] = {
        "benchmark": "Ongewogen gemiddelde per jaar over alle HO-instellingen in dezelfde provincie, exclusief eigen instelling",
        "indexering": "% verandering t.o.v. het eerste beschikbare jaar (basisjaar = 0%)",
        "datasets": {
            "ingeschrevenen": "DUO p01hoinges partities 0 (HBO) en 1 (WO)",
            "eerstejaars": "DUO p02ho1ejrs partities 0 (HBO) en 1 (WO)",
            "gediplomeerden": "DUO p04hogdipl partities 0 (HBO) en 1 (WO)",
        },
        "uwv_peildatum": "mei 2023 (momentopname)",
        "roa_bron": "ROA AIS2030 Schoolverlatersinformatie 2024 — nationale gemiddelden per opleidingsniveau, niet per instelling",
    }
    return result


def _load_dashboard_regio_mbo(instelling: str) -> dict | None:
    try:
        df_mbo = _load_mbo_studenten()
    except Exception:
        return None

    inst_col = "INSTELLINGSNAAM"
    prov_col = "PROVINCIE INSTELLING"

    rows = df_mbo[df_mbo[inst_col].str.lower() == instelling.lower()]
    if rows.empty:
        return None

    result: dict = {"type": "mbo"}
    provincie = _mode_str(rows[prov_col])
    result["provincie"] = provincie or "Onbekend"

    per_jaar = rows.groupby("JAAR")[["BBL", "BOLDT", "BOLVT", "EX"]].sum()
    totals = per_jaar.sum(axis=1).astype(int)
    result["ingeschrevenen"] = totals.sort_index().to_dict()

    laatste_jaar = int(totals.index.max())
    result["laatste_jaar"] = laatste_jaar

    laatste = rows[rows["JAAR"] == laatste_jaar]
    sectoren = {
        "BBL": int(laatste["BBL"].sum()),
        "BOL deeltijd": int(laatste["BOLDT"].sum()),
        "BOL voltijd": int(laatste["BOLVT"].sum()),
    }
    result["sectoren"] = {k: v for k, v in sorted(sectoren.items(), key=lambda x: -x[1]) if v > 0}

    try:
        df_dipl = _load_mbo_gediplomeerden()
        dipl_rows = df_dipl[df_dipl[inst_col].str.lower() == instelling.lower()]
        if not dipl_rows.empty:
            year_cols = [c for c in dipl_rows.columns if c.startswith("DIP")]
            gediplomeerden: dict[int, int] = {}
            for col in year_cols:
                jaar = int(col[-4:])
                gediplomeerden[jaar] = gediplomeerden.get(jaar, 0) + int(dipl_rows[col].sum())
            result["gediplomeerden"] = dict(sorted(gediplomeerden.items()))
    except Exception:
        pass

    if provincie:
        overige = df_mbo[
            (df_mbo[prov_col].str.lower() == provincie.lower()) &
            (df_mbo[inst_col].str.lower() != instelling.lower())
        ]
        n = int(overige[inst_col].nunique())
        if n > 0:
            per_inst_jaar = overige.groupby([inst_col, "JAAR"])[["BBL", "BOLDT", "BOLVT", "EX"]].sum()
            per_inst_jaar["totaal"] = per_inst_jaar.sum(axis=1)
            gem = per_inst_jaar.reset_index().groupby("JAAR")["totaal"].mean()
            totaal_prov = overige.groupby("JAAR")[["BBL", "BOLDT", "BOLVT", "EX"]].sum().sum(axis=1)
            result["benchmark"] = {
                "label": f"Provinciaal gemiddelde ({provincie}, excl. eigen instelling)",
                "n_instellingen": n,
                "ingeschrevenen": {int(k): round(float(v)) for k, v in gem.items()},
                "totaal_ingeschrevenen": {int(k): int(v) for k, v in totaal_prov.items()},
            }

    result["arbeidsmarkt_roa"] = _roa_schoolverlaters("mbo")
    # MBO sectoren zijn leerwegen (BBL/BOLVT) — geen inhoudsfilter mogelijk
    result["vacatureaanbod"] = _uwv_vacatures_provincie(provincie) if provincie else {}
    result["methodologie"] = {
        "benchmark": "Ongewogen gemiddelde per jaar over alle MBO-instellingen in dezelfde provincie, exclusief eigen instelling",
        "indexering": "% verandering t.o.v. het eerste beschikbare jaar (basisjaar = 0%)",
        "datasets": {
            "ingeschrevenen": "DUO mbo-studenten-per-instelling",
            "gediplomeerden": "DUO gediplomeerde-mbo-studenten",
        },
        "uwv_peildatum": "mei 2023 (momentopname)",
        "roa_bron": "ROA AIS2030 Schoolverlatersinformatie 2024 — nationale gemiddelden per opleidingsniveau, niet per instelling",
    }
    return result


def load_dashboard_regio(instelling: str) -> dict:
    instelling = resolve_alias(instelling)
    result: dict = {"instelling": instelling, "gevonden": False}

    ho = _load_dashboard_regio_ho(instelling)
    if ho:
        result["gevonden"] = True
        result.update(ho)
        return result

    mbo = _load_dashboard_regio_mbo(instelling)
    if mbo:
        result["gevonden"] = True
        result.update(mbo)
        return result

    # Suggesties
    try:
        df_ho, _, _ = _load_ho_full()
        df_mbo = _load_mbo_studenten()
        alle = sorted(set(
            df_ho["INSTELLINGSNAAM_ACTUEEL"].dropna().unique().tolist()
            + df_mbo["INSTELLINGSNAAM"].dropna().unique().tolist()
        ))
        result["beschikbare_instellingen"] = alle[:20]
    except Exception:
        pass

    return result


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
        df = _load_mbo_studenten()
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
        df_dipl = _load_mbo_gediplomeerden()
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
        df_mbo = _load_mbo_studenten()
        alle = sorted(set(
            df_ho["INSTELLINGSNAAM_ACTUEEL"].dropna().unique().tolist()
            + df_mbo["INSTELLINGSNAAM"].dropna().unique().tolist()
        ))
        result["beschikbare_instellingen"] = alle[:20]
    except Exception:
        pass

    return result
