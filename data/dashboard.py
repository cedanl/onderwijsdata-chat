from __future__ import annotations

import functools
import json
import logging
from dataclasses import dataclass
from pathlib import Path

_INSTROOM_MBO = "INSTROOM MBO"
_BOL_VOLTIJD = "BOL voltijd"
_BOL_DEELTIJD = "BOL deeltijd"

import pandas as pd
from riodata import duo

from .instellingen import get_adres_lookup, resolve_alias
from .instellingen import get_all as get_all_instellingen

logger = logging.getLogger(__name__)

_MAX_VACATURE_CLUSTERS = 8
_MAX_SUGGESTIONS = 20
_MBO_LEERWEG_COLS = ["BBL", "BOLDT", "BOLVT", "EX"]
_UWV_PEILDATUM = "mei 2023 (momentopname)"
_ROA_BRON = "ROA AIS2030 Schoolverlatersinformatie 2024 — nationale gemiddelden per opleidingsniveau, niet per instelling"
_MATCH_DREMPEL = 1.2  # verhouding vacatures/diploma's waarboven schaarste resp. overaanbod

# Approximate coordinates for Dutch educational cities (PLAATSNAAM uppercase → lat/lon).
_CITY_COORDS: dict[str, tuple[float, float]] = {
    "AMSTERDAM": (52.374, 4.899),
    "ROTTERDAM": (51.922, 4.480),
    "'S-GRAVENHAGE": (52.081, 4.313),
    "DEN HAAG": (52.081, 4.313),
    "HAAG": (52.081, 4.313),
    "UTRECHT": (52.091, 5.114),
    "EINDHOVEN": (51.438, 5.480),
    "GRONINGEN": (53.222, 6.568),
    "TILBURG": (51.560, 5.090),
    "ALMERE": (52.370, 5.215),
    "BREDA": (51.588, 4.776),
    "NIJMEGEN": (51.842, 5.853),
    "ENSCHEDE": (52.222, 6.897),
    "HAARLEM": (52.381, 4.637),
    "ARNHEM": (51.985, 5.899),
    "AMERSFOORT": (52.157, 5.389),
    "'S-HERTOGENBOSCH": (51.696, 5.304),
    "DEN BOSCH": (51.696, 5.304),
    "MAASTRICHT": (50.852, 5.691),
    "LEIDEN": (52.160, 4.494),
    "DORDRECHT": (51.810, 4.668),
    "ZWOLLE": (52.508, 6.090),
    "LEEUWARDEN": (53.201, 5.799),
    "ALKMAAR": (52.631, 4.750),
    "DELFT": (52.012, 4.357),
    "APELDOORN": (52.217, 5.967),
    "DEVENTER": (52.254, 6.163),
    "VENLO": (51.370, 6.173),
    "EDE": (52.048, 5.665),
    "ZAANDAM": (52.438, 4.819),
    "WAGENINGEN": (51.968, 5.665),
    "MEPPEL": (52.698, 6.196),
    "ROOSENDAAL": (51.530, 4.461),
    "DRACHTEN": (53.107, 6.099),
    "ROERMOND": (51.194, 5.987),
    "SITTARD": (51.001, 5.870),
    "HEERLEN": (50.889, 5.979),
    "MIDDELBURG": (51.499, 3.614),
    "VLISSINGEN": (51.453, 3.573),
    "LELYSTAD": (52.517, 5.469),
    "EMMEN": (52.785, 6.899),
    "ASSEN": (52.992, 6.563),
    "ZUTPHEN": (52.138, 6.197),
    "HELMOND": (51.482, 5.665),
    "DOETINCHEM": (51.963, 6.296),
    "HARDERWIJK": (52.340, 5.619),
    "KAMPEN": (52.554, 5.914),
    "ALMELO": (52.358, 6.664),
    "HENGELO": (52.265, 6.792),
    "ZOETERMEER": (52.059, 4.500),
    "ALPHEN AAN DEN RIJN": (52.132, 4.659),
    "PURMEREND": (52.503, 4.954),
    "SNEAK": (53.033, 5.659),
    "SNEEK": (53.033, 5.659),
    "VENRAY": (51.527, 5.978),
    "SITTARD-GELEEN": (51.001, 5.870),
    "GOES": (51.505, 3.889),
    "TERNEUZEN": (51.335, 3.830),
    "BERGEN OP ZOOM": (51.495, 4.287),
    "WOERDEN": (52.088, 4.887),
    "NIEUWEGEIN": (52.033, 5.083),
    "HOUTEN": (52.031, 5.168),
    "ZEIST": (52.088, 5.229),
    "BUSSUM": (52.274, 5.163),
    "HILVERSUM": (52.224, 5.179),
    "ZAANSTAD": (52.438, 4.819),
    "GOUDA": (52.017, 4.707),
    "SCHIEDAM": (51.916, 4.387),
    "SPIJKENISSE": (51.845, 4.331),
    "HOOFDDORP": (52.302, 4.692),
    "AMSTERDAM-ZUIDOOST": (52.317, 4.966),
    "DIEMEN": (52.336, 4.949),
    "WEESP": (52.308, 5.040),
}


# ─── Regio context ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RegioContext:
    """Benchmark regio voor een instelling: arbeidsmarktregio (voorkeur) of provincie (fallback)."""
    regio_naam: str        # Naam van de benchmark-regio
    regio_type: str        # "arbeidsmarktregio" | "provincie"
    provincie: str | None  # Altijd de provincie (voor UWV-data en display)
    self_code: str         # BRIN-code van de target-instelling
    peer_codes: frozenset  # BRIN-codes van peers in dezelfde regio (excl. zichzelf)


def _build_regio_context(instelling_naam: str, onderwijs_type: str) -> RegioContext | None:
    """
    Bouw een RegioContext voor benchmarking.

    onderwijs_type: "ho" (hbo + wo samen) of "mbo"

    Probeert arbeidsmarktregio; valt terug op provincie als er < 1 peer is.
    Retourneert None als er geen bruikbare context gevonden kan worden.
    """
    adres = get_adres_lookup()
    registry = get_all_instellingen()

    target = next(
        (i for i in registry if i["naam"].lower() == instelling_naam.lower()), None
    )
    if not target:
        return None

    self_code = target.get("instellingscode")
    if not self_code or self_code not in adres:
        return None

    self_info = adres[self_code]
    provincie = self_info.get("provincie")
    arbeidsmarktregio = self_info.get("arbeidsmarktregio")

    peer_types = {"hbo", "wo"} if onderwijs_type == "ho" else {"mbo"}
    code_to_type = {
        inst["instellingscode"]: inst["type"]
        for inst in registry
        if inst.get("instellingscode")
    }

    # WO research universities are distributed nationally, not clustered in one
    # arbeidsmarktregio. Use all WO institutions as peers for a meaningful benchmark.
    if target.get("type") == "wo":
        wo_peers = frozenset(
            inst["instellingscode"]
            for inst in registry
            if inst.get("type") == "wo"
            and inst.get("instellingscode") != self_code
            and inst.get("instellingscode") in adres
        )
        if wo_peers:
            return RegioContext(
                regio_naam="Nationaal (WO)",
                regio_type="nationaal",
                provincie=provincie,
                self_code=self_code,
                peer_codes=wo_peers,
            )

    def _peers_for_regio(regio_key: str, regio_value: str) -> frozenset:
        return frozenset(
            code for code, info in adres.items()
            if info.get(regio_key) == regio_value
            and code != self_code
            and code_to_type.get(code) in peer_types
        )

    if arbeidsmarktregio:
        peers = _peers_for_regio("arbeidsmarktregio", arbeidsmarktregio)
        if peers:
            return RegioContext(
                regio_naam=arbeidsmarktregio,
                regio_type="arbeidsmarktregio",
                provincie=provincie,
                self_code=self_code,
                peer_codes=peers,
            )

    if provincie:
        peers = _peers_for_regio("provincie", provincie)
        if peers:
            return RegioContext(
                regio_naam=provincie,
                regio_type="provincie",
                provincie=provincie,
                self_code=self_code,
                peer_codes=peers,
            )

    return None


# ─── Benchmark helpers ────────────────────────────────────────────────────────

def _gemiddelde_per_jaar(
    df: pd.DataFrame,
    code_col: str,
    peer_codes: frozenset,
    jaar_col: str,
    waarde_col: str,
) -> dict[int, float]:
    subset = df[df[code_col].isin(peer_codes)]
    if subset.empty:
        return {}
    per_inst = subset.groupby([code_col, jaar_col])[waarde_col].sum().reset_index()
    gem = per_inst.groupby(jaar_col)[waarde_col].mean()
    return {int(k): round(float(v), 1) for k, v in gem.items()}


def _per_peer(
    df: pd.DataFrame,
    code_col: str,
    inst_col: str,
    peer_codes: frozenset,
    jaar_col: str,
    waarde_col: str,
) -> dict[str, dict[int, int]]:
    """Return {naam: {jaar: waarde}} for each peer instelling."""
    subset = df[df[code_col].isin(peer_codes)]
    if subset.empty:
        return {}
    out: dict[str, dict[int, int]] = {}
    for _code, grp in subset.groupby(code_col):
        naam = grp[inst_col].iloc[0]
        series = grp.groupby(jaar_col)[waarde_col].sum().sort_index()
        out[naam] = {int(k): int(v) for k, v in series.items()}
    return out


def _per_peer_mbo_dipl(
    df: pd.DataFrame,
    code_col: str,
    inst_col: str,
    peer_codes: frozenset,
) -> dict[str, dict[int, int]]:
    """Return {naam: {jaar: gediplomeerden}} for MBO peers using wide DIP* column format."""
    subset = df[df[code_col].isin(peer_codes)]
    if subset.empty:
        return {}
    year_cols = [c for c in df.columns if c.startswith("DIP")]
    out: dict[str, dict[int, int]] = {}
    for _code, grp in subset.groupby(code_col):
        naam = grp[inst_col].iloc[0]
        jaardata: dict[int, int] = {}
        for col in year_cols:
            jaar = int(col[-4:])
            jaardata[jaar] = jaardata.get(jaar, 0) + int(grp[col].sum())
        out[naam] = dict(sorted(jaardata.items()))
    return out


def _per_peer_mbo(
    df: pd.DataFrame,
    code_col: str,
    inst_col: str,
    peer_codes: frozenset,
    jaar_col: str,
    leerweg_cols: list[str],
) -> dict[str, dict[int, int]]:
    """Return {naam: {jaar: totaal_ingeschrevenen}} for MBO peers."""
    subset = df[df[code_col].isin(peer_codes)]
    if subset.empty:
        return {}
    out: dict[str, dict[int, int]] = {}
    for _code, grp in subset.groupby(code_col):
        naam = grp[inst_col].iloc[0]
        per_jaar = grp.groupby(jaar_col)[leerweg_cols].sum().sum(axis=1)
        out[naam] = {int(k): int(v) for k, v in per_jaar.items()}
    return out


def _mbo_eerstejaars_from_df(df: pd.DataFrame | None, code: str) -> dict[int, int]:
    """Extract eerstejaars {jaar: aantal} from instromende dataframe for a given code."""
    if df is None or df.empty:
        return {}
    filtered = df[
        (df["INSTELLINGSCODE"] == code)
        & (df[_INSTROOM_MBO] == "J")
    ]
    if filtered.empty:
        return {}
    return filtered.groupby("JAAR")["AANTAL"].sum().sort_index().apply(int).to_dict()


def _mbo_peer_eerstejaars(
    df_instromende: pd.DataFrame | None,
    df_mbo: pd.DataFrame,
    code_col: str,
    inst_col: str,
    peer_codes: frozenset,
) -> tuple[dict[int, float], dict[str, dict[int, int]]]:
    """Return (benchmark_eerstejaars, peers_eerstejaars) for MBO peers."""
    if df_instromende is None or df_instromende.empty:
        return {}, {}
    peer_instromende = df_instromende[
        df_instromende["INSTELLINGSCODE"].isin(peer_codes)
        & (df_instromende[_INSTROOM_MBO] == "J")
    ]
    if peer_instromende.empty:
        return {}, {}
    gem_ej = (
        peer_instromende.groupby(["INSTELLINGSCODE", "JAAR"])["AANTAL"]
        .sum().reset_index()
    )
    gem_ej_per_jaar = gem_ej.groupby("JAAR")["AANTAL"].mean()
    bm = {int(k): round(float(v), 1) for k, v in gem_ej_per_jaar.items()}
    code_to_naam = (
        df_mbo.drop_duplicates(code_col).set_index(code_col)[inst_col].to_dict()
    )
    peers: dict[str, dict[int, int]] = {}
    for code, grp in peer_instromende.groupby("INSTELLINGSCODE"):
        naam = code_to_naam.get(str(code), str(code))
        ej_series = grp.groupby("JAAR")["AANTAL"].sum().sort_index()
        peers[naam] = {int(k): int(v) for k, v in ej_series.items()}
    return bm, peers


def _totaal_regio(
    df: pd.DataFrame,
    code_col: str,
    peer_codes: frozenset,
    jaar_col: str,
    waarde_col: str,
) -> dict[int, int]:
    subset = df[df[code_col].isin(peer_codes)]
    if subset.empty:
        return {}
    totaal = subset.groupby(jaar_col)[waarde_col].sum()
    return {int(k): int(v) for k, v in totaal.items()}


def _benchmark_label(ctx: RegioContext) -> str:
    if ctx.regio_type == "nationaal":
        return "Nationaal WO gemiddelde (excl. eigen instelling)"
    type_label = "Arbeidsmarktregio" if ctx.regio_type == "arbeidsmarktregio" else "Provincie"
    return f"{type_label} gemiddelde ({ctx.regio_naam}, excl. eigen instelling)"


# ─── Regiodashboard ──────────────────────────────────────────────────────────

def _build_kaart_figure(ctx: RegioContext, instelling_naam: str) -> str | None:
    """Return Plotly Scattergeo figure JSON for instelling locations in the benchmark regio."""
    try:
        import plotly.graph_objects as go
        import plotly.io as pio

        adres = get_adres_lookup()
        registry = get_all_instellingen()
        code_to_naam = {
            inst["instellingscode"]: inst["naam"]
            for inst in registry
            if inst.get("instellingscode")
        }

        def _coords(code: str) -> tuple[float, float] | None:
            city = (adres.get(code, {}).get("plaatsnaam") or "").upper()
            return _CITY_COORDS.get(city)

        fig = go.Figure()

        peer_lons, peer_lats, peer_texts = [], [], []
        for code in ctx.peer_codes:
            c = _coords(code)
            if c:
                peer_lats.append(c[0])
                peer_lons.append(c[1])
                peer_texts.append(code_to_naam.get(code, code))

        if peer_lons:
            fig.add_trace(go.Scattergeo(
                lon=peer_lons, lat=peer_lats, text=peer_texts,
                mode="markers",
                marker={"size": 10, "color": "#94A3B8", "line": {"width": 1, "color": "white"}},
                hovertemplate="%{text}<extra></extra>",
                name="Concurrenten",
            ))

        own = _coords(ctx.self_code)
        if own:
            fig.add_trace(go.Scattergeo(
                lon=[own[1]], lat=[own[0]], text=[instelling_naam],
                mode="markers+text",
                textposition="top right",
                textfont={"size": 12, "color": "#1E40AF"},
                marker={"size": 16, "color": "#2563EB", "symbol": "star", "line": {"width": 1.5, "color": "white"}},
                hovertemplate="%{text}<extra></extra>",
                name=instelling_naam,
            ))

        # Dynamic bounding box: zoom to the actual cluster of locations
        all_lats = peer_lats + ([own[0]] if own else [])
        all_lons = peer_lons + ([own[1]] if own else [])
        if all_lats:
            lat_min, lat_max = min(all_lats), max(all_lats)
            lon_min, lon_max = min(all_lons), max(all_lons)
            lat_spread = max(lat_max - lat_min, 0.25)
            lon_spread = max(lon_max - lon_min, 0.35)
            lat_range = [lat_min - lat_spread * 0.65, lat_max + lat_spread * 0.65]
            lon_range = [lon_min - lon_spread * 0.65, lon_max + lon_spread * 0.65]
        else:
            lat_range = [50.3, 53.9]
            lon_range = [3.0, 7.8]

        fig.update_layout(
            showlegend=True,
            legend={
                "x": 0, "y": 1, "bgcolor": "rgba(255,255,255,0.9)",
                "bordercolor": "#E2E8F0", "borderwidth": 1, "font": {"size": 11},
            },
            margin={"t": 10, "b": 10, "l": 10, "r": 10},
            paper_bgcolor="rgba(0,0,0,0)",
            height=340,
            geo={
                "scope": "europe",
                "resolution": 50,
                "showcountries": True,
                "countrycolor": "#CBD5E1",
                "showcoastlines": False,
                "showland": True,
                "landcolor": "#F8FAFC",
                "showocean": True,
                "oceancolor": "#EFF6FF",
                "showlakes": False,
                "lataxis": {"range": lat_range},
                "lonaxis": {"range": lon_range},
                "bgcolor": "rgba(0,0,0,0)",
            },
        )
        return pio.to_json(fig)
    except Exception:
        logger.warning("kaart-figure: kon Plotly-kaart niet bouwen", exc_info=True)
        return None


@functools.lru_cache(maxsize=1)
def _load_mbo_studenten() -> pd.DataFrame:
    return duo.load("mbo-studenten-per-instelling", 0)


@functools.lru_cache(maxsize=1)
def _load_mbo_gediplomeerden() -> pd.DataFrame:
    return duo.load("gediplomeerde-mbo-studenten", 0)


@functools.lru_cache(maxsize=1)
def _load_instromende_mbo_historisch() -> pd.DataFrame:
    """Odd partitions (1,3,5,7): JAAR + INSTELLINGSCODE + INSTROOM MBO (J/N flag) + AANTAL."""
    dfs = []
    for i in [1, 3, 5, 7]:
        try:
            dfs.append(duo.load("instromende-mbo-studenten", i))
        except Exception:
            logger.warning("instromende-mbo: partitie %d niet beschikbaar", i, exc_info=True)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


@functools.lru_cache(maxsize=1)
def _load_instromende_mbo_snapshot() -> pd.DataFrame:
    """Partition 0: INSTELLINGSNAAM + HOOFDGROEP NAAM + TOTAAL MBO (latest year snapshot)."""
    return duo.load("instromende-mbo-studenten", 0)


def _mbo_sectorkamers(instelling: str) -> dict[str, int]:
    """Return {hoofdgroep: aantal} from instromende snapshot."""
    try:
        df = _load_instromende_mbo_snapshot()
        rows = df[df["INSTELLINGSNAAM"].str.lower() == instelling.lower()]
        if rows.empty:
            return {}
        counts = (
            rows.groupby("HOOFDGROEP NAAM")["TOTAAL MBO"].sum()
            .sort_values(ascending=False)
        )
        return {str(k): int(v) for k, v in counts.items() if v > 0}
    except Exception:
        logger.warning("mbo-sectorkamers: niet beschikbaar", exc_info=True)
        return {}


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


def _load_sector_cluster_map() -> dict[str, list[str]]:
    path = Path(__file__).parent / "sector_cluster_mapping.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            logger.warning("sector_cluster_mapping.json onleesbaar", exc_info=True)
    else:
        logger.warning("sector_cluster_mapping.json niet gevonden — run scripts/refresh_sector_mapping.py")
    return {}


_SECTOR_CLUSTER_MAP: dict[str, list[str]] = _load_sector_cluster_map()


@functools.cache
def _uwv_raw_clusters(provincie: str) -> tuple[int, str, dict[str, int]]:
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
        logger.warning("uwv: vacatureclusters voor %s niet beschikbaar", provincie, exc_info=True)
        return 0, "onbekend", {}


def _uwv_vacatures_provincie(provincie: str, sectoren: tuple[str, ...] = ()) -> dict:
    """Top-8 vacatures per provincie, optioneel gefilterd op instellingssectoren."""
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
                top = dict(sorted(gefilterd.items(), key=lambda x: -x[1])[:_MAX_VACATURE_CLUSTERS])
                return {
                    "totaal": totaal,
                    "peildatum": peildatum,
                    "clusters": top,
                    "gefilterd_op": sorted(sectoren),
                }

    top = dict(list(alle_clusters.items())[:_MAX_VACATURE_CLUSTERS])
    return {
        "totaal": totaal,
        "peildatum": peildatum,
        "clusters": top,
        "gefilterd_op": [],
    }


@functools.cache
def _roa_prognose(onderwijs_type: str) -> dict:
    """ROA arbeidsmarktprognoses tot 2030 per opleidingsniveau."""
    try:
        from riodata import roa
        df = roa.load("ais2030", "arbeidsmarkt")
        prog = df[df["thema"].str.contains("prognose", case=False, na=False)]
        niveaus = ["Bachelor", "Master, doctor"] if onderwijs_type == "ho" else ["Mbo4", "Mbo3", "Mbo2"]
        subset = prog[
            (prog["aggregatieniveau"] == "opleidingsniveau (ONR2019)")
            & (prog["detailniveau"].isin(niveaus))
        ]
        indicatoren = [
            "ITA toekomstige arbeidsmarktsituatie in 2030",
            "verwachte baanopeningen tot 2030",
            "verwachte instroom van schoolverlaters tot 2030",
        ]
        rows = subset[subset["onderwerp"].isin(indicatoren)][
            ["detailniveau", "onderwerp", "typering"]
        ].dropna(subset=["typering"])
        if rows.empty:
            return {}
        out: dict = {}
        for _, row in rows.iterrows():
            niveau = str(row["detailniveau"])
            onderwerp = str(row["onderwerp"])
            out.setdefault(niveau, {})[onderwerp] = str(row["typering"])
        return out
    except Exception:
        logger.warning("roa: prognose %s niet beschikbaar", onderwijs_type, exc_info=True)
        return {}


@functools.cache
def _roa_schoolverlaters(onderwijs_type: str) -> dict:
    try:
        from riodata import roa
        df = roa.load("ais2030", "arbeidsmarkt")
        sv = df[df["thema"] == "Schoolverlatersinformatie (SIS 2024)"]
        niveaus = ["Bachelor", "Master, doctor"] if onderwijs_type == "ho" else ["Mbo4", "Mbo3", "Mbo2"]
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
            out.setdefault(niveau, {})[indicator] = round(float(row["perc"]))
        return out
    except Exception:
        logger.warning("roa: schoolverlaters %s niet beschikbaar", onderwijs_type, exc_info=True)
        return {}


def _load_dashboard_regio_ho(instelling: str) -> dict | None:
    try:
        df_inges, df_ej, df_dipl = _load_ho_full()
    except Exception:
        logger.warning("regio-ho: data laden mislukt voor %s", instelling, exc_info=True)
        return None

    inst_col = "INSTELLINGSNAAM_ACTUEEL"
    code_col = "INSTELLINGSCODE_ACTUEEL"

    hu_inges = df_inges[df_inges[inst_col].str.lower() == instelling.lower()]
    if hu_inges.empty:
        return None

    ctx = _build_regio_context(instelling, "ho")
    provincie = ctx.provincie if ctx else _mode_str(hu_inges["PROVINCIENAAM"])

    _self_code_ho = str(hu_inges[code_col].iloc[0])
    _self_amr = get_adres_lookup().get(_self_code_ho, {}).get("arbeidsmarktregio")

    result: dict = {"type": "ho"}
    result["provincie"] = provincie or "Onbekend"
    result["arbeidsmarktregio"] = _self_amr

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
    # Task 3: geslacht_trend per jaar
    geslacht_trend: dict[int, dict[str, int]] = {}
    for jaar, grp in hu_inges.groupby("STUDIEJAAR"):
        geslacht_trend[int(jaar)] = {
            "VROUW": int(grp[grp["GESLACHT"] == "VROUW"]["AANTAL_INGESCHREVENEN"].sum()),
            "MAN": int(grp[grp["GESLACHT"] == "MAN"]["AANTAL_INGESCHREVENEN"].sum()),
        }
    result["geslacht_trend"] = dict(sorted(geslacht_trend.items()))
    result["sectoren"] = (
        laatste.groupby("ONDERDEEL")["AANTAL_INGESCHREVENEN"].sum()
        .sort_values(ascending=False).apply(int).to_dict()
    )
    geslacht_per_sector: dict[str, dict[str, int]] = {}
    for onderdeel, grp in laatste.groupby("ONDERDEEL"):
        geslacht_per_sector[onderdeel] = {
            "VROUW": int(grp[grp["GESLACHT"] == "VROUW"]["AANTAL_INGESCHREVENEN"].sum()),
            "MAN": int(grp[grp["GESLACHT"] == "MAN"]["AANTAL_INGESCHREVENEN"].sum()),
        }
    result["geslacht_per_sector"] = geslacht_per_sector
    # Sector trend: per onderdeel per studiejaar (stacked area frontend)
    sector_pivot = (
        hu_inges.groupby(["STUDIEJAAR", "ONDERDEEL"])["AANTAL_INGESCHREVENEN"]
        .sum().unstack(fill_value=0)
    )
    result["sectoren_trend"] = {
        str(col): {int(j): int(v) for j, v in sector_pivot[col].items()}
        for col in sector_pivot.columns
    }

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

    if ctx:
        n = len(ctx.peer_codes)
        result["benchmark"] = {
            "label": _benchmark_label(ctx),
            "regio_type": ctx.regio_type,
            "n_instellingen": n,
            "ingeschrevenen": _gemiddelde_per_jaar(
                df_inges, code_col, ctx.peer_codes, "STUDIEJAAR", "AANTAL_INGESCHREVENEN"
            ),
            "eerstejaars": _gemiddelde_per_jaar(
                df_ej, code_col, ctx.peer_codes, "STUDIEJAAR", "AANTAL_EERSTEJAARS_INGESCHREVENEN"
            ),
            "gediplomeerden": _gemiddelde_per_jaar(
                df_dipl, code_col, ctx.peer_codes, "DIPLOMAJAAR", "AANTAL_GEDIPLOMEERDEN"
            ),
            "totaal_ingeschrevenen": _totaal_regio(
                df_inges, code_col, ctx.peer_codes, "STUDIEJAAR", "AANTAL_INGESCHREVENEN"
            ),
            "peers": {
                "ingeschrevenen": _per_peer(
                    df_inges, code_col, inst_col, ctx.peer_codes, "STUDIEJAAR", "AANTAL_INGESCHREVENEN"
                ),
                "gediplomeerden": _per_peer(
                    df_dipl, code_col, inst_col, ctx.peer_codes, "DIPLOMAJAAR", "AANTAL_GEDIPLOMEERDEN"
                ),
            },
        }
        result["kaart_figure_json"] = _build_kaart_figure(ctx, instelling)

    result["arbeidsmarkt_roa"] = _roa_schoolverlaters("ho")
    result["arbeidsmarkt_prognose"] = _roa_prognose("ho")
    ho_sectoren = tuple(sorted(result.get("sectoren", {}).keys()))
    result["vacatureaanbod"] = _uwv_vacatures_provincie(provincie, ho_sectoren) if provincie else {}
    result["methodologie"] = {
        "benchmark": (
            "Ongewogen gemiddelde per jaar over alle HO-instellingen in dezelfde "
            f"{ctx.regio_type if ctx else 'provincie'}, exclusief eigen instelling"
        ),
        "indexering": "% verandering t.o.v. het eerste beschikbare jaar (basisjaar = 0%)",
        "datasets": {
            "ingeschrevenen": "DUO p01hoinges partities 0 (HBO) en 1 (WO)",
            "eerstejaars": "DUO p02ho1ejrs partities 0 (HBO) en 1 (WO)",
            "gediplomeerden": "DUO p04hogdipl partities 0 (HBO) en 1 (WO)",
        },
        "uwv_peildatum": _UWV_PEILDATUM,
        "roa_bron": _ROA_BRON,
    }
    return result


def _mbo_regio_benchmark(ctx, df_mbo, df_instromende, df_dipl_mbo, code_col, inst_col):
    peer_codes = ctx.peer_codes
    peer_df = df_mbo[df_mbo[code_col].isin(peer_codes)]
    per_inst_jaar = peer_df.groupby([code_col, "JAAR"])[_MBO_LEERWEG_COLS].sum()
    per_inst_jaar["totaal"] = per_inst_jaar.sum(axis=1)
    gem = per_inst_jaar.reset_index().groupby("JAAR")["totaal"].mean()
    totaal_regio = peer_df.groupby("JAAR")[_MBO_LEERWEG_COLS].sum().sum(axis=1)
    bm_eerstejaars, peers_eerstejaars = _mbo_peer_eerstejaars(df_instromende, df_mbo, code_col, inst_col, peer_codes)
    peers: dict = {
        "ingeschrevenen": _per_peer_mbo(df_mbo, code_col, inst_col, peer_codes, "JAAR", _MBO_LEERWEG_COLS),
        "eerstejaars": peers_eerstejaars,
    }
    if df_dipl_mbo is not None:
        peers["gediplomeerden"] = _per_peer_mbo_dipl(df_dipl_mbo, code_col, inst_col, peer_codes)
    return {
        "label": _benchmark_label(ctx),
        "regio_type": ctx.regio_type,
        "n_instellingen": len(peer_codes),
        "ingeschrevenen": {int(k): round(float(v), 1) for k, v in gem.items()},
        "totaal_ingeschrevenen": {int(k): int(v) for k, v in totaal_regio.items()},
        "eerstejaars": bm_eerstejaars,
        "peers": peers,
    }


def _mbo_load_gediplomeerden(inst_col: str, instelling: str) -> tuple[pd.DataFrame | None, dict[int, int]]:
    try:
        df = _load_mbo_gediplomeerden()
        return df, _mbo_dipl_per_jaar(df, inst_col, instelling)
    except Exception:
        logger.warning("regio-mbo: gediplomeerden niet beschikbaar", exc_info=True)
        return None, {}


def _mbo_load_eerstejaars(self_code: str) -> tuple[pd.DataFrame | None, dict[int, int]]:
    try:
        df = _load_instromende_mbo_historisch()
        return df, _mbo_eerstejaars_from_df(df, self_code)
    except Exception:
        logger.warning("regio-mbo: eerstejaars niet beschikbaar", exc_info=True)
        return None, {}


def _load_dashboard_regio_mbo(instelling: str) -> dict | None:
    try:
        df_mbo = _load_mbo_studenten()
    except Exception:
        logger.warning("regio-mbo: data laden mislukt voor %s", instelling, exc_info=True)
        return None

    inst_col = "INSTELLINGSNAAM"
    code_col = "INSTELLINGSCODE"
    rows = df_mbo[df_mbo[inst_col].str.lower() == instelling.lower()]
    if rows.empty:
        return None

    ctx = _build_regio_context(instelling, "mbo")
    provincie = ctx.provincie if ctx else _mode_str(rows["PROVINCIE INSTELLING"])
    self_code = str(rows[code_col].iloc[0])
    self_amr = get_adres_lookup().get(self_code, {}).get("arbeidsmarktregio")

    result: dict = {
        "type": "mbo",
        "provincie": provincie or "Onbekend",
        "arbeidsmarktregio": self_amr,
    }

    per_jaar = rows.groupby("JAAR")[_MBO_LEERWEG_COLS].sum()
    totals = per_jaar.sum(axis=1).astype(int)
    result["ingeschrevenen"] = totals.sort_index().to_dict()
    laatste_jaar = int(totals.index.max())
    result["laatste_jaar"] = laatste_jaar

    result["leerwegen"] = {
        int(jaar): {
            "BBL": int(row["BBL"]),
            _BOL_VOLTIJD: int(row["BOLVT"]),
            _BOL_DEELTIJD: int(row["BOLDT"]),
        }
        for jaar, row in per_jaar.sort_index().iterrows()
    }

    laatste = rows[rows["JAAR"] == laatste_jaar]
    sectoren = {
        "BBL": int(laatste["BBL"].sum()),
        _BOL_DEELTIJD: int(laatste["BOLDT"].sum()),
        _BOL_VOLTIJD: int(laatste["BOLVT"].sum()),
    }
    result["sectoren"] = {k: v for k, v in sorted(sectoren.items(), key=lambda x: -x[1]) if v > 0}

    sectorkamers = _mbo_sectorkamers(instelling)
    if sectorkamers:
        result["sectorkamers"] = sectorkamers

    df_dipl_mbo, dipl = _mbo_load_gediplomeerden(inst_col, instelling)
    if dipl:
        result["gediplomeerden"] = dipl

    df_instromende, eerstejaars = _mbo_load_eerstejaars(self_code)
    if eerstejaars:
        result["eerstejaars"] = eerstejaars

    if ctx:
        result["benchmark"] = _mbo_regio_benchmark(ctx, df_mbo, df_instromende, df_dipl_mbo, code_col, inst_col)
        result["kaart_figure_json"] = _build_kaart_figure(ctx, instelling)

    result["arbeidsmarkt_roa"] = _roa_schoolverlaters("mbo")
    result["arbeidsmarkt_prognose"] = _roa_prognose("mbo")
    result["vacatureaanbod"] = _uwv_vacatures_provincie(provincie) if provincie else {}
    regio_type = ctx.regio_type if ctx else "provincie"
    result["methodologie"] = {
        "benchmark": f"Ongewogen gemiddelde per jaar over alle MBO-instellingen in dezelfde {regio_type}, exclusief eigen instelling",
        "indexering": "% verandering t.o.v. het eerste beschikbare jaar (basisjaar = 0%)",
        "datasets": {
            "ingeschrevenen": "DUO mbo-studenten-per-instelling",
            "gediplomeerden": "DUO gediplomeerde-mbo-studenten",
        },
        "uwv_peildatum": _UWV_PEILDATUM,
        "roa_bron": _ROA_BRON,
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

    try:
        df_ho, _, _ = _load_ho_full()
        df_mbo = _load_mbo_studenten()
        alle = sorted(set(
            df_ho["INSTELLINGSNAAM_ACTUEEL"].dropna().unique().tolist()
            + df_mbo["INSTELLINGSNAAM"].dropna().unique().tolist()
        ))
        result["beschikbare_instellingen"] = alle[:_MAX_SUGGESTIONS]
    except Exception:
        logger.warning("load_dashboard_regio: beschikbare instellingen niet laden", exc_info=True)

    return result


# ─── Instroom dashboard (zonder benchmark) ───────────────────────────────────

def _load_ho(_instelling: str) -> pd.DataFrame:
    return _load_ho_full()[0]


def _filter_ho(df: pd.DataFrame, instelling: str) -> pd.DataFrame:
    col = "INSTELLINGSNAAM_ACTUEEL"
    if col not in df.columns:
        return df.iloc[0:0]
    return df[df[col].str.lower() == instelling.lower()]


def _ho_load_eerstejaars(instelling: str) -> dict[int, int] | None:
    try:
        _, df_1e, _ = _load_ho_full()
        hu1 = _filter_ho(df_1e, instelling)
        if hu1.empty:
            return None
        return hu1.groupby("STUDIEJAAR")["AANTAL_EERSTEJAARS_INGESCHREVENEN"].sum().sort_index().to_dict()
    except Exception:
        logger.warning("dashboard-ho: eerstejaars niet beschikbaar voor %s", instelling, exc_info=True)
        return None


def _ho_load_gediplomeerden(instelling: str) -> dict[int, int] | None:
    try:
        _, _, df_dipl = _load_ho_full()
        hud = _filter_ho(df_dipl, instelling)
        if hud.empty:
            return None
        return hud.groupby("DIPLOMAJAAR")["AANTAL_GEDIPLOMEERDEN"].sum().sort_index().to_dict()
    except Exception:
        logger.warning("dashboard-ho: gediplomeerden niet beschikbaar voor %s", instelling, exc_info=True)
        return None


def load_dashboard_ho(instelling: str) -> dict | None:
    try:
        df_inges = _load_ho(instelling)
        hu = _filter_ho(df_inges, instelling)
        if hu.empty:
            return None
    except Exception:
        logger.warning("dashboard-ho: data laden mislukt voor %s", instelling, exc_info=True)
        return None

    result: dict = {}
    result["ingeschrevenen"] = (
        hu.groupby("STUDIEJAAR")["AANTAL_INGESCHREVENEN"].sum().sort_index().to_dict()
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

    eerstejaars = _ho_load_eerstejaars(instelling)
    if eerstejaars:
        result["eerstejaars"] = eerstejaars

    gediplomeerden = _ho_load_gediplomeerden(instelling)
    if gediplomeerden:
        result["gediplomeerden"] = gediplomeerden

    return result


def load_dashboard_mbo(instelling: str) -> dict | None:
    try:
        df = _load_mbo_studenten()
    except Exception:
        logger.warning("dashboard-mbo: data laden mislukt voor %s", instelling, exc_info=True)
        return None

    rows = df[df["INSTELLINGSNAAM"].str.lower() == instelling.lower()]
    if rows.empty:
        return None

    result: dict = {}

    per_jaar = rows.groupby("JAAR")[_MBO_LEERWEG_COLS].sum()
    totals = per_jaar.sum(axis=1).astype(int)
    result["ingeschrevenen"] = totals.sort_index().to_dict()

    laatste_jaar = int(totals.index.max())
    result["laatste_jaar"] = laatste_jaar

    laatste = per_jaar.loc[laatste_jaar]
    sectoren = {
        "BBL": int(laatste["BBL"]),
        _BOL_DEELTIJD: int(laatste["BOLDT"]),
        _BOL_VOLTIJD: int(laatste["BOLVT"]),
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
        logger.warning("dashboard-mbo: gediplomeerden niet beschikbaar voor %s", instelling, exc_info=True)

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
        result["beschikbare_instellingen"] = alle[:_MAX_SUGGESTIONS]
    except Exception:
        logger.warning("load_dashboard: beschikbare instellingen niet laden", exc_info=True)

    return result


# ─── Nationaal Marktaandeel ───────────────────────────────────────────────────

def _nationaal_ho(instelling: str, result: dict) -> dict | None:
    try:
        df_inges, _, _ = _load_ho_full()
    except Exception:
        logger.warning("nationaal-ho: ranking niet beschikbaar voor %s", instelling, exc_info=True)
        return None

    inst_col = "INSTELLINGSNAAM_ACTUEEL"
    hu = df_inges[df_inges[inst_col].str.lower() == instelling.lower()]
    if hu.empty:
        return None

    result["gevonden"] = True
    result["type"] = "ho"
    laatste_jaar = int(hu["STUDIEJAAR"].max())
    result["laatste_jaar"] = laatste_jaar

    sectoren_landelijk: dict[str, dict[int, int]] = {}
    for (onderdeel, jaar), waarde in (
        df_inges.groupby(["ONDERDEEL", "STUDIEJAAR"])["AANTAL_INGESCHREVENEN"].sum().items()
    ):
        sectoren_landelijk.setdefault(onderdeel, {})[int(jaar)] = int(waarde)
    result["sectoren_landelijk"] = sectoren_landelijk

    eigen_sectoren: dict[str, dict[int, int]] = {}
    for (onderdeel, jaar), waarde in (
        hu.groupby(["ONDERDEEL", "STUDIEJAAR"])["AANTAL_INGESCHREVENEN"].sum().items()
    ):
        eigen_sectoren.setdefault(onderdeel, {})[int(jaar)] = int(waarde)
    result["eigen_sectoren"] = eigen_sectoren

    registry = get_all_instellingen()
    naam_to_type = {i["naam"].lower(): i["type"] for i in registry}
    laatste = df_inges[df_inges["STUDIEJAAR"] == laatste_jaar]
    per_inst = (
        laatste.groupby(inst_col)["AANTAL_INGESCHREVENEN"].sum()
        .sort_values(ascending=False)
    )
    result["alle_instellingen"] = [
        {"naam": naam, "ingeschrevenen": int(aant), "type": naam_to_type.get(naam.lower(), "ho")}
        for naam, aant in per_inst.items()
    ]

    eigen_naam = hu[inst_col].iloc[0]
    eigen_positie: dict[str, int] = {}
    for onderdeel in eigen_sectoren:
        df_ond = laatste[laatste["ONDERDEEL"] == onderdeel]
        lw_namen = list(
            df_ond.groupby(inst_col)["AANTAL_INGESCHREVENEN"]
            .sum().sort_values(ascending=False).index
        )
        if eigen_naam in lw_namen:
            eigen_positie[onderdeel] = lw_namen.index(eigen_naam) + 1
    result["eigen_positie"] = eigen_positie
    return result


def _nationaal_mbo(instelling: str, result: dict) -> dict | None:
    try:
        df_mbo = _load_mbo_studenten()
    except Exception:
        logger.warning("nationaal-mbo: ranking niet beschikbaar voor %s", instelling, exc_info=True)
        return None

    inst_col_mbo = "INSTELLINGSNAAM"
    rows = df_mbo[df_mbo[inst_col_mbo].str.lower() == instelling.lower()]
    if rows.empty:
        return None

    result["gevonden"] = True
    result["type"] = "mbo"
    laatste_jaar = int(df_mbo["JAAR"].max())
    result["laatste_jaar"] = laatste_jaar

    landelijk_per_jaar = df_mbo.groupby("JAAR")[_MBO_LEERWEG_COLS].sum()
    result["sectoren_landelijk"] = {
        lw: {int(j): int(v) for j, v in landelijk_per_jaar[lw].items()}
        for lw in _MBO_LEERWEG_COLS
    }

    eigen_per_jaar = rows.groupby("JAAR")[_MBO_LEERWEG_COLS].sum()
    result["eigen_sectoren"] = {
        lw: {int(j): int(v) for j, v in eigen_per_jaar[lw].items()}
        for lw in _MBO_LEERWEG_COLS
    }

    laatste = df_mbo[df_mbo["JAAR"] == laatste_jaar]
    per_inst = (
        laatste.groupby(inst_col_mbo)[_MBO_LEERWEG_COLS].sum()
        .sum(axis=1).sort_values(ascending=False)
    )
    result["alle_instellingen"] = [
        {"naam": naam, "ingeschrevenen": int(aant), "type": "mbo"}
        for naam, aant in per_inst.items()
    ]

    eigen_naam = rows[inst_col_mbo].iloc[0]
    eigen_positie_mbo: dict[str, int] = {}
    for lw in _MBO_LEERWEG_COLS:
        lw_per_inst = laatste.groupby(inst_col_mbo)[lw].sum().sort_values(ascending=False)
        lw_namen = list(lw_per_inst.index)
        if eigen_naam in lw_namen:
            eigen_positie_mbo[lw] = lw_namen.index(eigen_naam) + 1
    result["eigen_positie"] = eigen_positie_mbo
    return result


def load_dashboard_nationaal(instelling: str) -> dict:
    instelling = resolve_alias(instelling)
    result: dict = {"instelling": instelling, "gevonden": False}
    return _nationaal_ho(instelling, result) or _nationaal_mbo(instelling, result) or result


# ─── Rendementsmonitor ────────────────────────────────────────────────────────


def _pseudo_cohorten(instroom: dict[int, int], dipl: dict[int, int]) -> list[dict]:
    return [
        {
            "instroom_jaar": int(jaar),
            "instroom": instroom[jaar],
            "gediplomeerden_t3": dipl.get(jaar + 3, 0),
            "gediplomeerden_t4": dipl.get(jaar + 4, 0),
            "gediplomeerden_t5": dipl.get(jaar + 5, 0),
        }
        for jaar in sorted(instroom)
    ]


def _rendement_per_jaar(cohorten: list[dict]) -> dict[int, float]:
    # Ratio > 1 indicates total-diplomas-per-year vs eerstejaars mismatch (common at WO
    # with many masters graduates); skip those cohorts as the value is not meaningful.
    return {
        c["instroom_jaar"]: round(c["gediplomeerden_t3"] / c["instroom"], 4)
        for c in cohorten
        if c["instroom"] > 0 and 0 < c["gediplomeerden_t3"] <= c["instroom"]
    }


def _benchmark_from_peer_rendements(peer_lists: list[dict[int, float]]) -> dict[int, float]:
    if not peer_lists:
        return {}
    all_jaren: set[int] = set().union(*[set(r.keys()) for r in peer_lists])
    bm: dict[int, float] = {}
    for jaar in sorted(all_jaren):
        vals = [r[jaar] for r in peer_lists if jaar in r]
        if vals:
            bm[jaar] = round(sum(vals) / len(vals), 4)
    return bm


def _mbo_dipl_per_jaar(df_dipl: pd.DataFrame, filter_col: str, filter_val: str) -> dict[int, int]:
    rows = df_dipl[df_dipl[filter_col].str.lower() == filter_val.lower()]
    if rows.empty:
        return {}
    result: dict[int, int] = {}
    for col in [c for c in rows.columns if c.startswith("DIP")]:
        jaar = int(col[-4:])
        result[jaar] = result.get(jaar, 0) + int(rows[col].sum())
    return result



def load_dashboard_rendement(instelling: str) -> dict:
    instelling = resolve_alias(instelling)
    result: dict = {"instelling": instelling, "gevonden": False}

    ho_result = _rendement_ho(instelling)
    if ho_result:
        return ho_result

    mbo_result = _rendement_mbo(instelling)
    if mbo_result:
        return mbo_result

    return result


def _sector_rendement_ho(df_inges: pd.DataFrame, df_dipl: pd.DataFrame, inst_col: str, instelling: str) -> dict[str, float]:
    hu_dipl = df_dipl[df_dipl[inst_col].str.lower() == instelling.lower()]
    if hu_dipl.empty or "ONDERDEEL" not in hu_dipl.columns:
        return {}
    hu_inges = df_inges[df_inges[inst_col].str.lower() == instelling.lower()]
    out: dict[str, float] = {}
    for onderdeel in hu_inges["ONDERDEEL"].unique():
        d = int(hu_dipl[hu_dipl["ONDERDEEL"] == onderdeel]["AANTAL_GEDIPLOMEERDEN"].sum())
        i = int(hu_inges[hu_inges["ONDERDEEL"] == onderdeel]["AANTAL_INGESCHREVENEN"].sum())
        if i > 0 and d > 0:
            out[onderdeel] = round(d / i, 4)
    return out


def _ho_peer_rendement(df_ej: pd.DataFrame, df_dipl: pd.DataFrame, code_col: str, inst_col: str, code: str) -> dict[int, float]:
    p_ej = df_ej[df_ej[code_col] == code]
    if p_ej.empty:
        return {}
    p_dipl = df_dipl[df_dipl[code_col] == code]
    p_instroom = p_ej.groupby("STUDIEJAAR")["AANTAL_EERSTEJAARS_INGESCHREVENEN"].sum()
    p_dipl_series = p_dipl.groupby("DIPLOMAJAAR")["AANTAL_GEDIPLOMEERDEN"].sum() if not p_dipl.empty else pd.Series(dtype=int)
    rend: dict[int, float] = {}
    for jaar in p_instroom.index:
        iv = int(p_instroom[jaar])
        dt3 = int(p_dipl_series.get(jaar + 3, 0))
        if iv > 0 and dt3 > 0:
            rend[int(jaar)] = round(dt3 / iv, 4)
    return rend


def _rendement_ho(instelling: str) -> dict | None:
    try:
        df_inges, df_ej, df_dipl = _load_ho_full()
    except Exception:
        logger.warning("rendement-ho: niet beschikbaar voor %s", instelling, exc_info=True)
        return None

    inst_col = "INSTELLINGSNAAM_ACTUEEL"
    code_col = "INSTELLINGSCODE_ACTUEEL"
    hu_ej = df_ej[df_ej[inst_col].str.lower() == instelling.lower()]
    if hu_ej.empty:
        return None

    result: dict = {"instelling": instelling, "gevonden": True, "type": "ho"}
    result["laatste_jaar"] = int(df_ej["STUDIEJAAR"].max())

    instroom_series = hu_ej.groupby("STUDIEJAAR")["AANTAL_EERSTEJAARS_INGESCHREVENEN"].sum()
    instroom = {int(k): int(v) for k, v in instroom_series.items()}

    hu_dipl = df_dipl[df_dipl[inst_col].str.lower() == instelling.lower()]
    dipl_series = hu_dipl.groupby("DIPLOMAJAAR")["AANTAL_GEDIPLOMEERDEN"].sum() if not hu_dipl.empty else pd.Series(dtype=int)
    dipl = {int(k): int(v) for k, v in dipl_series.items()}  # ty: ignore[invalid-argument-type]

    cohorten = _pseudo_cohorten(instroom, dipl)
    result["pseudo_cohorten"] = cohorten
    result["rendement_per_jaar"] = _rendement_per_jaar(cohorten)

    result["sector_rendement"] = _sector_rendement_ho(df_inges, df_dipl, inst_col, instelling)

    # benchmark & peers
    ctx = _build_regio_context(instelling, "ho")
    peers_rendement: dict[str, dict[int, float]] = {}
    peer_rend_lists: list[dict[int, float]] = []
    if ctx:
        for code in ctx.peer_codes:
            rend = _ho_peer_rendement(df_ej, df_dipl, code_col, inst_col, code)
            if rend:
                naam = df_ej[df_ej[code_col] == code][inst_col].iloc[0]
                peers_rendement[naam] = rend
                peer_rend_lists.append(rend)

    result["benchmark_rendement"] = _benchmark_from_peer_rendements(peer_rend_lists)
    result["peers_rendement"] = peers_rendement
    return result


def _mbo_peer_rendement_for_code(df_instromende_all, df_mbo, df_dipl_mbo, code, code_col, inst_col):
    p_instr = df_instromende_all[
        (df_instromende_all["INSTELLINGSCODE"] == code)
        & (df_instromende_all[_INSTROOM_MBO] == "J")
    ]
    p_instroom = p_instr.groupby("JAAR")["AANTAL"].sum().apply(int).to_dict()
    p_dipl = _mbo_dipl_per_jaar(df_dipl_mbo, "INSTELLINGSCODE", code) if df_dipl_mbo is not None else {}
    peer_rend: dict[int, float] = {}
    for jaar in p_instroom:
        iv = p_instroom[jaar]
        dt3 = p_dipl.get(jaar + 3, 0)
        if iv > 0 and dt3 > 0:
            peer_rend[jaar] = round(dt3 / iv, 4)
    if not peer_rend:
        return None, None
    p_rows = df_mbo[df_mbo[code_col] == code]
    peer_naam = p_rows[inst_col].iloc[0] if not p_rows.empty else code
    return peer_naam, peer_rend


def _mbo_peers_rendement(ctx, df_mbo, df_dipl_mbo, inst_col, code_col):
    if not ctx:
        return {}, []
    try:
        df_instromende_all = _load_instromende_mbo_historisch()
    except Exception:
        logger.warning("rendement-mbo: peer rendement niet beschikbaar", exc_info=True)
        return {}, []
    peers_rendement: dict[str, dict[int, float]] = {}
    peer_rend_lists: list[dict[int, float]] = []
    for code in ctx.peer_codes:
        peer_naam, peer_rend = _mbo_peer_rendement_for_code(
            df_instromende_all, df_mbo, df_dipl_mbo, code, code_col, inst_col,
        )
        if peer_rend:
            peers_rendement[peer_naam] = peer_rend
            peer_rend_lists.append(peer_rend)
    return peers_rendement, peer_rend_lists


def _rendement_mbo(instelling: str) -> dict | None:
    try:
        df_mbo = _load_mbo_studenten()
        df_dipl_mbo = _load_mbo_gediplomeerden()
    except Exception:
        logger.warning("rendement-mbo: niet beschikbaar voor %s", instelling, exc_info=True)
        return None

    inst_col = "INSTELLINGSNAAM"
    code_col = "INSTELLINGSCODE"
    rows = df_mbo[df_mbo[inst_col].str.lower() == instelling.lower()]
    if rows.empty:
        return None

    result: dict = {"instelling": instelling, "gevonden": True, "type": "mbo"}
    result["laatste_jaar"] = int(rows["JAAR"].max())
    self_code = str(rows[code_col].iloc[0])

    # instroom
    instroom_per_jaar: dict[int, int] = {}
    try:
        df_instromende = _load_instromende_mbo_historisch()
        if not df_instromende.empty:
            self_instr = df_instromende[
                (df_instromende["INSTELLINGSCODE"] == self_code)
                & (df_instromende[_INSTROOM_MBO] == "J")
            ]
            instroom_per_jaar = self_instr.groupby("JAAR")["AANTAL"].sum().apply(int).to_dict()
    except Exception:
        logger.warning("rendement-mbo: instroom per jaar niet beschikbaar", exc_info=True)

    dipl_per_jaar = _mbo_dipl_per_jaar(df_dipl_mbo, inst_col, instelling) if df_dipl_mbo is not None else {}

    cohorten = _pseudo_cohorten(instroom_per_jaar, dipl_per_jaar)
    result["pseudo_cohorten"] = cohorten
    result["rendement_per_jaar"] = _rendement_per_jaar(cohorten)
    result["sector_rendement"] = {}

    # benchmark & peers
    ctx = _build_regio_context(instelling, "mbo")
    peers_rendement, peer_rend_lists = _mbo_peers_rendement(
        ctx, df_mbo, df_dipl_mbo, inst_col, code_col
    )
    result["benchmark_rendement"] = _benchmark_from_peer_rendements(peer_rend_lists)
    result["peers_rendement"] = peers_rendement
    return result


# ─── Arbeidsmarktmatch ────────────────────────────────────────────────────────

def _arbeidsmarktmatch_ho(instelling: str) -> dict | None:
    try:
        df_inges, _, df_dipl = _load_ho_full()
    except Exception:
        logger.warning("arbeidsmarktmatch-ho: niet beschikbaar voor %s", instelling, exc_info=True)
        return None

    inst_col = "INSTELLINGSNAAM_ACTUEEL"
    hu = df_inges[df_inges[inst_col].str.lower() == instelling.lower()]
    if hu.empty:
        return None

    ctx = _build_regio_context(instelling, "ho")
    self_code = str(hu["INSTELLINGSCODE_ACTUEEL"].iloc[0])
    provincie = ctx.provincie if ctx else _mode_str(hu["PROVINCIENAAM"])

    gps: dict[str, int] = {}
    hu_dipl = df_dipl[df_dipl[inst_col].str.lower() == instelling.lower()]
    if not hu_dipl.empty and "ONDERDEEL" in hu_dipl.columns:
        jaren = sorted(hu_dipl["DIPLOMAJAAR"].unique())[-3:]
        recent = hu_dipl[hu_dipl["DIPLOMAJAAR"].isin(jaren)]
        gem = recent.groupby(["DIPLOMAJAAR", "ONDERDEEL"])["AANTAL_GEDIPLOMEERDEN"].sum().groupby("ONDERDEEL").mean()
        gps = {str(k): int(round(v)) for k, v in gem.items() if v > 0}  # noqa: RUF046 — round(numpy.float64) returns numpy scalar, not Python int

    return {
        "type": "ho", "provincie": provincie or "Onbekend",
        "arbeidsmarktregio": get_adres_lookup().get(self_code, {}).get("arbeidsmarktregio"),
        "laatste_jaar": int(hu["STUDIEJAAR"].max()),
        "gediplomeerden_per_sector": gps,
    }


def _arbeidsmarktmatch_mbo(instelling: str) -> dict | None:
    try:
        df_mbo = _load_mbo_studenten()
    except Exception:
        logger.warning("arbeidsmarktmatch-mbo: niet beschikbaar voor %s", instelling, exc_info=True)
        return None

    rows = df_mbo[df_mbo["INSTELLINGSNAAM"].str.lower() == instelling.lower()]
    if rows.empty:
        return None

    ctx = _build_regio_context(instelling, "mbo")
    self_code = str(rows["INSTELLINGSCODE"].iloc[0])
    provincie = ctx.provincie if ctx else _mode_str(rows["PROVINCIE INSTELLING"])

    gps: dict[str, int] = {}
    try:
        df_snapshot = _load_instromende_mbo_snapshot()
        snap = df_snapshot[df_snapshot["INSTELLINGSNAAM"].str.lower() == instelling.lower()]
        if not snap.empty:
            gps = {str(k): int(v) for k, v in snap.groupby("HOOFDGROEP NAAM")["TOTAAL MBO"].sum().items() if v > 0}
    except Exception:
        logger.warning("arbeidsmarktmatch-mbo: sectorkamers niet beschikbaar", exc_info=True)

    return {
        "type": "mbo", "provincie": provincie or "Onbekend",
        "arbeidsmarktregio": get_adres_lookup().get(self_code, {}).get("arbeidsmarktregio"),
        "laatste_jaar": int(rows["JAAR"].max()),
        "gediplomeerden_per_sector": gps,
    }


def load_dashboard_arbeidsmarktmatch(instelling: str) -> dict:
    instelling = resolve_alias(instelling)
    result: dict = {"instelling": instelling, "gevonden": False}

    detect = _arbeidsmarktmatch_ho(instelling) or _arbeidsmarktmatch_mbo(instelling)
    if not detect:
        return result

    result["gevonden"] = True
    result.update(detect)
    onderwijs_type = detect["type"]
    provincie = detect["provincie"]
    sectoren_tuple = tuple(sorted(detect["gediplomeerden_per_sector"].keys()))

    # vacatures_per_cluster
    uwv_data = _uwv_vacatures_provincie(provincie, sectoren_tuple) if provincie else {}
    result["vacatures_per_cluster"] = uwv_data.get("clusters", {})

    # roa_per_niveau
    roa_raw = _roa_schoolverlaters(onderwijs_type)
    result["roa_per_niveau"] = {
        niveau: {
            "werkloosheid": data.get("werkloosheid"),
            "vast_dienstverband": data.get("vast dienstverband"),
            "buiten_vakrichting": data.get("buiten de vakrichting"),
        }
        for niveau, data in roa_raw.items()
    }

    # sector_cluster_mapping
    gps_final = result.get("gediplomeerden_per_sector", {})
    result["sector_cluster_mapping"] = {
        s: _SECTOR_CLUSTER_MAP.get(s, [])
        for s in gps_final
    }

    # match_score: schaarste if vac-aandeel > dipl-aandeel * 1.2
    vpc = result["vacatures_per_cluster"]
    scm = result["sector_cluster_mapping"]
    totaal_dipl = sum(gps_final.values())
    totaal_vac = sum(vpc.values())

    if not totaal_dipl or not totaal_vac:
        result["match_score"] = dict.fromkeys(gps_final)
        return result

    match_score: dict[str, str | None] = {}
    for sector, dipl_count in gps_final.items():
        dipl_aandeel = dipl_count / totaal_dipl
        clusters = scm.get(sector, [])
        if clusters:
            vac_count = sum(vpc.get(cl, 0) for cl in clusters)
            vac_aandeel = vac_count / totaal_vac
            if vac_aandeel > dipl_aandeel * _MATCH_DREMPEL:
                match_score[sector] = "schaarste"
            elif dipl_aandeel > vac_aandeel * _MATCH_DREMPEL:
                match_score[sector] = "overaanbod"
            else:
                match_score[sector] = "evenwicht"
        else:
            match_score[sector] = None
    result["match_score"] = match_score

    return result
