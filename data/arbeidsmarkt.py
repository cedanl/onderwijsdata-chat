"""Arbeidsmarktdata na mbo/hbo/wo: UWV-vacatures en ROA-schoolverlatersinformatie (#441, #435).

Eén plek voor de chattools (`tools/arbeidsmarkt.py`) en de dashboards (`data/dashboard.py`).
Tot CH-23 haalden de tools private functies uit dashboard.py, terwijl dashboards in alle
omgevingen uit staan.

- UWV: Open Match, een momentopname. De peildatum komt uit de kolom PEILDATUM, niet uit tekst.
  Vacatures hebben geen opleidingsniveau: de kolommen AANT_OPLNIV_* zijn alleen bij werkzoekenden
  gevuld (nagekeken voor de snapshots van 2021 en 2023, #449).
- ROA: AIS 2030, landelijk (regionaam 'Nederland') tenzij een regio gevraagd is; zonder dat filter
  won de typering van de laatst gelezen regio. De prognose staat er ook per arbeidsmarktregio (35)
  en provincie (12, als 'provincie Utrecht'), alleen als typering; de schoolverlatersinformatie
  alleen landelijk (#450).
"""

from __future__ import annotations

import functools
import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

SECTOR_CLUSTER_PATH = Path(__file__).parent / "sector_cluster_mapping.json"
# Wie de clusters aan sectoren toewees: een taalmodel via scripts/refresh_sector_mapping.py, niet UWV (#460).
MAPPING_HERKOMST = "LLM-classificatie, niet van UWV"
_ONBEKEND = "onbekend"

# Niveaus binnen het chatprofiel; ROA kent ook basisonderwijs, vmbo en havo/vwo.
ROA_NIVEAUS: dict[str, tuple[str, ...]] = {"mbo": ("Mbo2", "Mbo3", "Mbo4"), "ho": ("Bachelor", "Master, doctor")}
ROA_LANDELIJK = "Nederland"
_ROA_PROVINCIE = "provincie "
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


def _lees_mapping(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            logger.warning("sector_cluster_mapping.json onleesbaar", exc_info=True)
    else:
        logger.warning("sector_cluster_mapping.json niet gevonden — run scripts/refresh_sector_mapping.py")
    return {}


def load_sector_cluster_map(path: Path = SECTOR_CLUSTER_PATH) -> dict[str, list[str]]:
    """Sector → UWV-clusters; `_manifest` (peildatum en bron, #313) is geen sector."""
    return {k: v for k, v in _lees_mapping(path).items() if not k.startswith("_")}


def load_sector_indeling(path: Path = SECTOR_CLUSTER_PATH) -> dict[str, str]:
    """Sector → indeling uit `_indelingen`: hbo/wo-onderdelen en mbo-sectoren delen dezelfde vacatures elk in."""
    return {s: indeling for indeling, sectoren in _lees_mapping(path).get("_indelingen", {}).items() for s in sectoren}


def sector_mapping_manifest(path: Path = SECTOR_CLUSTER_PATH) -> dict[str, str]:
    """Herkomst, versie (`bijgewerkt`) en model van de mapping uit `_manifest` (#460); ontbreekt een veld,
    dan 'onbekend'. De herkomst is altijd een LLM-classificatie: zo maakt het refresh-script de mapping."""
    manifest = _lees_mapping(path).get("_manifest")
    velden = manifest if isinstance(manifest, dict) else {}
    return {
        "herkomst": str(velden.get("herkomst") or MAPPING_HERKOMST),
        "mapping_versie": str(velden.get("bijgewerkt") or _ONBEKEND),
        "model": str(velden.get("model") or _ONBEKEND),
    }


SECTOR_CLUSTER_MAP: dict[str, list[str]] = load_sector_cluster_map()
SECTOR_INDELING: dict[str, str] = load_sector_indeling()
SECTOR_MANIFEST: dict[str, str] = sector_mapping_manifest()


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


def _in_provincie(df: pd.DataFrame, provincie: str) -> pd.DataFrame:
    return df[df["PROVINCIE"].str.lower() == provincie.lower()]


def gemeenten(provincie: str) -> list[str]:
    return sorted(_in_provincie(_uwv(), provincie)["GEMEENTE"].dropna().unique())


def uwv_stand(provincie: str, gemeente: str | None = None) -> UwvStand | None:
    """Vacatures per beroepencluster in een provincie of een gemeente daarin; None zonder rijen.

    Elke gemeente ligt in de data in één provincie. Een arbeidsmarktregio kent UWV niet; de enige
    gemeente-naar-regio-koppeling in de app (DUO-adressen) dekt alleen gemeenten met een instelling.
    """
    subset = _in_provincie(_uwv(), provincie)
    if gemeente:
        subset = subset[subset["GEMEENTE"].str.lower() == gemeente.lower()]
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


@dataclass(frozen=True)
class SectorVacatures:
    totaal: int  # gewogen naar het aantal sectoren per cluster, zie sector_vacatures
    clusters: dict[str, int]  # beroepencluster → vacatures, ongewogen en aflopend
    gedeeld: dict[str, list[str]]  # beroepencluster → de andere sectoren van dezelfde indeling


def _indelingsgenoten(sector: str) -> list[str]:
    """De andere sectoren uit de indeling van `sector`; zonder indeling staat een sector alleen."""
    indeling = SECTOR_INDELING.get(sector)
    return [s for s, i in SECTOR_INDELING.items() if indeling and i == indeling and s != sector]


def sector_vacatures(alle_clusters: dict[str, int], sector: str) -> SectorVacatures:
    """Vacatures van één sector zonder dubbeltelling (#449).

    De mapping hangt een cluster soms aan meer sectoren (chauffeurs bij TECHNIEK én ECONOMIE). Opgeteld
    kwamen TECHNIEK en ECONOMIE in Utrecht op 21.027 van de 25.225 vacatures. Nu telt zo'n cluster
    naar rato: bij k sectoren van dezelfde indeling voor 1/k. Het totaal wordt naar beneden afgerond,
    zodat de sectoren van één indeling samen nooit meer vacatures hebben dan er zijn. Tussen de
    indelingen (hbo/wo en mbo) wordt niet gewogen: dat zijn twee indelingen van dezelfde vacatures.
    """
    clusters = relevante_clusters(alle_clusters, (sector,))
    genoten = _indelingsgenoten(sector)
    gedeeld = {c: andere for c in clusters if (andere := [s for s in genoten if c in SECTOR_CLUSTER_MAP.get(s, ())])}
    totaal = sum(Fraction(n, 1 + len(gedeeld.get(c, ()))) for c, n in clusters.items())
    return SectorVacatures(totaal=math.floor(totaal), clusters=clusters, gedeeld=gedeeld)


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


def roa_regios() -> list[str]:
    """Alle ROA-regionamen: Nederland, de arbeidsmarktregio's en de provincies ('provincie Utrecht')."""
    return sorted(_roa()["regionaam"].dropna().astype(str).unique())


def roa_regio(naam: str) -> str | None:
    """De ROA-regionaam bij een naam, hoofdletterongevoelig; None als ROA hem niet kent.

    Exact, zonder te raden. Een provincie mag ook op haar eigen naam ('Utrecht' → 'provincie Utrecht').
    Groningen, Drenthe, Friesland, Flevoland en Zeeland zijn ook arbeidsmarktregio's: dan wint die.
    """
    namen = {r.lower(): r for r in roa_regios()}
    sleutel = naam.strip().lower()
    return namen.get(sleutel) or namen.get(_ROA_PROVINCIE + sleutel)


def roa_regiotype(regionaam: str) -> str:
    if regionaam == ROA_LANDELIJK:
        return "landelijk"
    return "provincie" if regionaam.startswith(_ROA_PROVINCIE) else "arbeidsmarktregio"


def roa_waarden(
    detailniveaus: tuple[str, ...],
    onderwerpen: tuple[str, ...],
    thema: str,
    aggregatieniveau: str = _ROA_NIVEAU,
    regio: str = ROA_LANDELIJK,
) -> dict[str, dict[str, dict[str, float | int | str]]]:
    """ROA-waarden van één regio: detailniveau → onderwerp → {perc, aantal, typering}, alleen wat er staat."""
    df = _roa()
    rijen = df[
        (df["regionaam"] == regio)
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
    """De opleidingssectoren van ROA binnen het profiel (mbo2-4, bachelor, master).

    ROA noemt het niveau 'Master, doctor', maar de sectoren 'Master - …'; met het niveau als prefix
    vielen de mastersectoren weg en heette 'Master - techniek en ict' onbekend (#450).
    """
    df = _roa()
    prefixen = tuple(f"{n.split(',')[0]} - " for ns in ROA_NIVEAUS.values() for n in ns)
    sectoren = df.loc[df["aggregatieniveau"] == _ROA_SECTOR, "detailniveau"].dropna().astype(str).unique()
    return sorted(s for s in sectoren if s.startswith(prefixen))


def roa_schoolverlaters(detailniveaus: tuple[str, ...], sector: bool = False, regio: str = ROA_LANDELIJK) -> dict:
    niveau = _ROA_SECTOR if sector else _ROA_NIVEAU
    return roa_waarden(detailniveaus, ROA_SIS_INDICATOREN, _ROA_SIS, niveau, regio)


def roa_prognose(detailniveaus: tuple[str, ...], sector: bool = False, regio: str = ROA_LANDELIJK) -> dict:
    niveau = _ROA_SECTOR if sector else _ROA_NIVEAU
    return roa_waarden(detailniveaus, ROA_PROGNOSE_INDICATOREN, _ROA_PROGNOSE, niveau, regio)
