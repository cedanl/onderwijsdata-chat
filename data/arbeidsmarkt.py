"""Arbeidsmarktdata na mbo/hbo/wo: UWV-vacatures en ROA-schoolverlatersinformatie (#441, #435).

Eén plek voor de chattools (`tools/arbeidsmarkt.py`) en de dashboards (`data/dashboard.py`).
Tot CH-23 haalden de tools private functies uit dashboard.py, terwijl dashboards in alle
omgevingen uit staan.

- UWV: Open Match, een momentopname. De peildatum komt uit de kolom PEILDATUM, niet uit tekst.
- ROA: AIS 2030, landelijk (regionaam 'Nederland'). Prognoserijen bestaan ook per regio; zonder
  dat filter won de typering van de laatst gelezen regio.
"""

from __future__ import annotations

import functools
import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

SECTOR_CLUSTER_PATH = Path(__file__).parent / "sector_cluster_mapping.json"

# Niveaus binnen het chatprofiel; ROA kent ook basisonderwijs, vmbo en havo/vwo.
ROA_NIVEAUS: dict[str, tuple[str, ...]] = {"mbo": ("Mbo2", "Mbo3", "Mbo4"), "ho": ("Bachelor", "Master, doctor")}
ROA_LANDELIJK = "Nederland"
_ROA_NIVEAU = "opleidingsniveau (ONR2019)"
_ROA_SECTOR = "  opleidingssector (ONR2019)"
_ROA_SIS = "Schoolverlatersinformatie (SIS 2024)"
_ROA_PROGNOSE = "Risicoindicatoren en arbeidsmarktprognoses tot 2030"
ROA_SIS_INDICATOREN = ("werkloosheid", "vast dienstverband", "buiten de vakrichting")
ROA_PROGNOSE_INDICATOREN = (
    "ITA toekomstige arbeidsmarktsituatie in 2030",
    "verwachte baanopeningen tot 2030",
    "verwachte instroom van schoolverlaters tot 2030",
)


def load_sector_cluster_map(path: Path = SECTOR_CLUSTER_PATH) -> dict[str, list[str]]:
    """Sector → UWV-clusters; `_manifest` (peildatum en bron, #313) is geen sector."""
    if path.exists():
        try:
            return {k: v for k, v in json.loads(path.read_text()).items() if not k.startswith("_")}
        except Exception:
            logger.warning("sector_cluster_mapping.json onleesbaar", exc_info=True)
    else:
        logger.warning("sector_cluster_mapping.json niet gevonden — run scripts/refresh_sector_mapping.py")
    return {}


SECTOR_CLUSTER_MAP: dict[str, list[str]] = load_sector_cluster_map()


@dataclass(frozen=True)
class UwvStand:
    totaal: int
    peildatum: str  # ISO-datum(s) uit de data
    clusters: dict[str, int]  # beroepencluster → vacatures, aflopend


@functools.cache
def _uwv() -> pd.DataFrame:
    from riodata import uwv

    return uwv.load("latest", rec_type="Vacature")


def _peildatum(df: pd.DataFrame) -> str:
    waarden = sorted({datetime.strptime(str(d), "%d-%m-%Y").date().isoformat() for d in df["PEILDATUM"].dropna()})
    return ", ".join(waarden) or "onbekend"


def provincies() -> list[str]:
    return sorted(_uwv()["PROVINCIE"].dropna().unique())


def uwv_stand(provincie: str) -> UwvStand | None:
    """Vacatures per beroepencluster in een provincie; None als de provincie geen rijen heeft."""
    df = _uwv()
    subset = df[df["PROVINCIE"].str.lower() == provincie.lower()]
    if subset.empty:
        return None
    per_cluster = subset.groupby("BEROEPENCLUSTER")["AANTAL"].sum().sort_values(ascending=False)
    return UwvStand(
        totaal=int(subset["AANTAL"].sum()),
        peildatum=_peildatum(subset),
        clusters={str(k): int(v) for k, v in per_cluster.items()},
    )


def relevante_clusters(alle_clusters: dict[str, int], sectoren: tuple[str, ...]) -> dict[str, int]:
    """Filter clusters op sectoren via de mapping. Geeft lege dict als geen match."""
    if not sectoren or not SECTOR_CLUSTER_MAP:
        return {}
    relevant = {c for s in sectoren for c in SECTOR_CLUSTER_MAP.get(s, [])}
    return {naam: n for naam, n in alle_clusters.items() if naam in relevant}


def clusters_voor_sectoren(provincie: str, sectoren: tuple[str, ...]) -> dict[str, int]:
    """Alle vacatureclusters voor de gegeven sectoren, zonder top-N cap.

    Geen match is geen reden om alle clusters te nemen: dan kreeg elke sector
    vacature-aandeel 0 en dus "overaanbod" (#229). Leeg geeft match_score None.
    """
    stand = uwv_stand(provincie)
    return relevante_clusters(stand.clusters, sectoren) if stand else {}


@functools.cache
def _roa() -> pd.DataFrame:
    from riodata import roa

    return roa.load("ais2030", "arbeidsmarkt")


def roa_versie() -> str:
    return ", ".join(sorted(_roa()["versie"].dropna().astype(str).unique())) or "onbekend"


def _getal(waarde) -> float | int | None:
    try:
        getal = float(str(waarde).replace(",", "."))
    except ValueError:
        return None
    if not math.isfinite(getal):
        return None
    return int(getal) if getal.is_integer() else getal


def roa_waarden(
    detailniveaus: tuple[str, ...], onderwerpen: tuple[str, ...], thema: str, aggregatieniveau: str = _ROA_NIVEAU
) -> dict[str, dict[str, dict[str, float | int | str]]]:
    """Landelijke ROA-waarden: detailniveau → onderwerp → {perc, aantal, typering}, alleen wat er staat."""
    df = _roa()
    rijen = df[
        (df["regionaam"] == ROA_LANDELIJK)
        & (df["thema"] == thema)
        & (df["aggregatieniveau"] == aggregatieniveau)
        & df["detailniveau"].isin(detailniveaus)
        & df["onderwerp"].isin(onderwerpen)
    ]
    uit: dict[str, dict[str, dict[str, float | int | str]]] = {}
    for _, rij in rijen.iterrows():
        waarden: dict[str, float | int | str] = {
            k: g for k in ("perc", "aantal") if (g := _getal(rij.get(k))) is not None
        }
        if pd.notna(rij.get("typering")):
            waarden["typering"] = str(rij["typering"])
        if waarden:
            uit.setdefault(str(rij["detailniveau"]), {})[str(rij["onderwerp"])] = waarden
    return uit


def roa_sectoren() -> list[str]:
    """De opleidingssectoren van ROA binnen het profiel (mbo2-4, bachelor, master)."""
    df = _roa()
    niveaus = tuple(n for ns in ROA_NIVEAUS.values() for n in ns)
    sectoren = df.loc[df["aggregatieniveau"] == _ROA_SECTOR, "detailniveau"].dropna().astype(str).unique()
    return sorted(s for s in sectoren if s.startswith(niveaus))


def roa_schoolverlaters(detailniveaus: tuple[str, ...], sector: bool = False) -> dict:
    return roa_waarden(detailniveaus, ROA_SIS_INDICATOREN, _ROA_SIS, _ROA_SECTOR if sector else _ROA_NIVEAU)


def roa_prognose(detailniveaus: tuple[str, ...], sector: bool = False) -> dict:
    return roa_waarden(detailniveaus, ROA_PROGNOSE_INDICATOREN, _ROA_PROGNOSE, _ROA_SECTOR if sector else _ROA_NIVEAU)
