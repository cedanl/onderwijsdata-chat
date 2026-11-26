"""Arbeidsmarktdata na mbo/hbo/wo: UWV-vacatures en ROA-schoolverlatersinformatie (#441, #435).

Eén plek voor de chattools (`tools/arbeidsmarkt.py`) en de dashboards (`data/dashboard.py`).
Tot CH-23 haalden de tools private functies uit dashboard.py, terwijl dashboards in alle
omgevingen uit staan.

- UWV: Open Match, een momentopname. De peildatum komt uit de kolom PEILDATUM, niet uit tekst.
  Alleen de chat (`get_uwv_vacatures`) gebruikt UWV nog; de dashboards lezen hun vacatures sinds #1225 uit
  CBS 83599NED (data/vacatures_cbs.py). `ouderdom` geldt voor beide.
  Vacatures hebben geen opleidingsniveau: de kolommen AANT_OPLNIV_* zijn alleen bij werkzoekenden
  gevuld (nagekeken voor de snapshots van 2021 en 2023, #449).
- ROA: AIS 2030, landelijk (regionaam 'Nederland') tenzij een regio gevraagd is; zonder dat filter
  won de typering van de laatst gelezen regio. De prognose staat er ook per arbeidsmarktregio (35)
  en provincie (12, als 'provincie Utrecht'), alleen als typering; de schoolverlatersinformatie
  alleen landelijk (#450). Onder het niveau deelt ROA in naar sector en subsector (ook regionaal) en
  opleidingstype (alleen landelijk); de code in de kolom `waarde` geeft die hiërarchie (#745).
  Het bestand is de editie die de catalogus de nieuwste noemt (`roa_bestand`, #1091), en de thema's van
  schoolverlaters en prognose komen uit dat bestand.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path

import pandas as pd

from core import actualiteit, brongebruik
from core.logging_util import foutkenmerk

logger = logging.getLogger(__name__)

SECTOR_CLUSTER_PATH = Path(__file__).parent / "sector_cluster_mapping.json"
# Wie de clusters aan sectoren toewees: een taalmodel via scripts/refresh_sector_mapping.py, niet UWV (#460).
MAPPING_HERKOMST = "LLM-classificatie, niet van UWV"
ONBEKEND = "onbekend"  # een veld van het mappingmanifest dat niet is vastgelegd

# Niveaus binnen het chatprofiel; ROA kent ook basisonderwijs, vmbo en havo/vwo.
ROA_NIVEAUS: dict[str, tuple[str, ...]] = {"mbo": ("Mbo2", "Mbo3", "Mbo4"), "ho": ("Bachelor", "Master, doctor")}
ROA_LANDELIJK = "Nederland"
_ROA_PROVINCIE = "provincie "
_ROA_NIVEAU = "opleidingsniveau (ONR2019)"
_ROA_SECTOR = "  opleidingssector (ONR2019)"
# De opleidingsindeling van ROA (ONR2019) in vier lagen, met de inspringing zoals in de kolom `aggregatieniveau`.
# Sector en subsector staan er per arbeidsmarktregio en provincie, het opleidingstype alleen landelijk (#745).
ROA_AGGREGATIE = {
    "niveau": _ROA_NIVEAU,
    "sector": _ROA_SECTOR,
    "subsector": "    opleidingssubsector (ONR2019)",
    "type": "      opleidingstype (ONR2019)",
}
# De thema's van de schoolverlatersinformatie en de prognose, zoals elke editie ze spelt: "Schoolverlatersinformatie
# (SIS 2024)" en "Risicoindicatoren en arbeidsmarktprognoses tot 2030" in editie 2025, "(SIS 2025)" en "…tot 2030,
# actualisering" in editie 2026 (#1091). Het thema komt uit het geladen bestand, niet uit vaste tekst: een vaste tekst
# gaf bij een nieuwe editie een lege tabel.
_ROA_SIS_PATROON = re.compile(r"^Schoolverlatersinformatie \((SIS \d{4})\)$")
_ROA_PROGNOSE_PATROON = re.compile(r"^Risicoindicatoren en arbeidsmarktprognoses tot 2030(?:, actualisering)?$")
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
        except Exception as e:
            logger.warning("sector_cluster_mapping.json onleesbaar: %s", foutkenmerk(e))
            logger.debug("sector_cluster_mapping.json onleesbaar", exc_info=True)
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
        "mapping_versie": str(velden.get("bijgewerkt") or ONBEKEND),
        "model": str(velden.get("model") or ONBEKEND),
    }


SECTOR_CLUSTER_MAP: dict[str, list[str]] = load_sector_cluster_map()
SECTOR_INDELING: dict[str, str] = load_sector_indeling()
SECTOR_MANIFEST: dict[str, str] = sector_mapping_manifest()


@dataclass(frozen=True)
class UwvStand:
    totaal: int
    peildatum: str  # ISO-datum(s) uit de data
    clusters: dict[str, int]  # beroepencluster → vacatures, aflopend
    provincie: str = ""  # de plaats zoals de data haar spelt, niet zoals de vraag haar schreef (#577)
    gemeente: str | None = None


# UWV en ROA na actualiteit.TTL opnieuw van de bron, zoals de rest van de app (#901); tot dan één download, ook als
# chat en dashboards tegelijk vragen. Met functools.cache bleef de eerste download tot de pod herstartte. Elke lading
# meldt haar bestand met peildatum of editie voor het bronblok van de dashboards (#904, data/bronblok.py).
@actualiteit.Lading
def _uwv() -> pd.DataFrame:
    from onderwijsbronnen import uwv

    df = uwv.load("latest", rec_type="Vacature")
    brongebruik.meld(
        {
            "bron": "UWV",
            "dataset": uwv.DATASET_ID,
            "peildatum": _peildatum(df),
            "opgehaald_op": actualiteit.nu().isoformat(),
        }
    )
    return df


def _peildatum(df: pd.DataFrame) -> str:
    waarden = sorted({datetime.strptime(str(d), "%d-%m-%Y").date().isoformat() for d in df["PEILDATUM"].dropna()})
    return ", ".join(waarden) or "onbekend"


# UWV kent de Friese provincie als "Friesland"; CBS en de vraag van een gebruiker zeggen ook "Fryslân".
_PROVINCIE_ALIAS = {"fryslân": "friesland", "fryslan": "friesland"}
# Rijen zonder plaats dragen "Onbekend" als provincie: geen keuze om een gebruiker voor te leggen (#631).
_GEEN_PROVINCIE = "onbekend"


def _provincienaam(provincie: str) -> str:
    naam = " ".join(provincie.split()).lower()
    return _PROVINCIE_ALIAS.get(naam, naam)


def provincies() -> list[str]:
    return sorted(p for p in _uwv()["PROVINCIE"].dropna().unique() if str(p).lower() != _GEEN_PROVINCIE)


def uwv_peildatum() -> str:
    """De peildatum van de hele UWV-momentopname, voor een bronregel zonder selectie (#577)."""
    return _peildatum(_uwv())


# Een vacaturestand van meer hele maanden oud dan dit heet verouderd (#1219): UWV en CBS publiceren de vacatures per
# kwartaal, dus een stand van meer dan een jaar oud is geen beeld van nu. Eén grens voor dashboards (het laatste
# kwartaal van CBS 83599NED, #1225) en chat (de UWV-peildatum).
VACATURES_VEROUDERD_MAANDEN = 12
_MAANDNAMEN = (
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
)


def _peildata(peildatum: str | None) -> list[date]:
    """De ISO-datums in een peildatum zoals `_peildatum` hem geeft ("2023-05-16" of "2023-05-09, 2023-05-16")."""
    datums = []
    for deel in (peildatum or "").split(","):
        try:
            datums.append(date.fromisoformat(deel.strip()))
        except ValueError:
            continue
    return datums


def peildatum_ouderdom_maanden(peildatum: str | None) -> int | None:
    """Hoeveel hele maanden de (jongste) peildatum voor nu ligt, met de klok van `actualiteit.nu`; None zonder datum.

    Een maand is vol op dezelfde dag van de maand: 16 mei 2023 is op 15 juni 2023 nul maanden oud, op 16 juni één.
    Een peildatum na nu is nul maanden oud, niet negatief."""
    datums = _peildata(peildatum)
    if not datums:
        return None
    jongste, vandaag = max(datums), actualiteit.nu().date()
    maanden = (vandaag.year - jongste.year) * 12 + vandaag.month - jongste.month - (vandaag.day < jongste.day)
    return max(maanden, 0)


def ouderdom(peildatum: str | None) -> dict:
    """`peildatum_ouderdom_maanden` en `verouderd` voor een payload of toolresultaat (#1219); zo rekent de frontend
    niet zelf. Verouderd is een stand van meer dan `VACATURES_VEROUDERD_MAANDEN` hele maanden oud."""
    maanden = peildatum_ouderdom_maanden(peildatum)
    return {
        "peildatum_ouderdom_maanden": maanden,
        "verouderd": maanden is not None and maanden > VACATURES_VEROUDERD_MAANDEN,
    }


def ouderdom_tekst(maanden: int) -> str:
    """De ouderdom in woorden: "minder dan een maand", "11 maanden", "1 jaar", "ruim 3 jaar" (42 maanden). De frontend
    schrijft hem met dezelfde regel (`ouderdomTekst` in momentopname.jsx)."""
    if maanden < 1:
        return "minder dan een maand"
    if maanden < 12:
        return f"{maanden} {'maand' if maanden == 1 else 'maanden'}"
    jaren, rest = divmod(maanden, 12)
    return f"{'ruim ' if rest else ''}{jaren} jaar"


def _lange_datum(dag: date) -> str:
    return f"{dag.day} {_MAANDNAMEN[dag.month - 1]} {dag.year}"


def uwv_peiltekst(peildatum: str | None) -> str:
    """Het peilmoment van UWV voor de bronregels (#1219): "peildatum 16 mei 2023, ruim 3 jaar oud". Zonder leesbare
    datum de peildatum zoals hij is ("peildatum onbekend")."""
    datums = _peildata(peildatum)
    maanden = peildatum_ouderdom_maanden(peildatum)
    if not datums or maanden is None:
        return f"peildatum {peildatum or 'onbekend'}"
    return f"peildatum {' en '.join(_lange_datum(d) for d in datums)}, {ouderdom_tekst(maanden)} oud"


def uwv_actualiteit(peildatum: str | None) -> str | None:
    """Bij een verouderde stand: hoe oud hij is, waarom er niets nieuwers is en waar de actuele kwartaalcijfers staan
    (#1219, #1220); None bij een jonge stand. De app laadt die kwartaalcijfers niet: dat staat er ook."""
    datums = _peildata(peildatum)
    stand = ouderdom(peildatum)
    if not datums or not stand["verouderd"]:
        return None
    jongste = max(datums)
    return (
        f"De peildatum is {ouderdom_tekst(stand['peildatum_ouderdom_maanden'])} oud: UWV werkt deze open dataset "
        f"sinds {_MAANDNAMEN[jongste.month - 1]} {jongste.year} niet meer bij. Actuele vacatures per kwartaal staan bij "
        "UWV (dashboard Vacaturemarkt) en CBS (tabel 83599NED); deze app laadt die (nog) niet."
    )


def _in_provincie(df: pd.DataFrame, provincie: str) -> pd.DataFrame:
    return df[df["PROVINCIE"].str.lower() == _provincienaam(provincie)]


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
        provincie=str(subset["PROVINCIE"].iloc[0]),
        gemeente=str(subset["GEMEENTE"].iloc[0]) if gemeente else None,
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


_ROA_ID = "ais2030"
_ROA_SOORT = "arbeidsmarkt"  # het arbeidsmarktbestand van AIS 2030, met prognose en schoolverlatersinformatie
# Een bewuste pin op een oudere editie: de resourcenaam uit roa_resources.json (bijv. "arbeidsmarkt" = editie 2025) en
# de reden, die ook in docs/databronnen.md staat. None: de app laadt de editie die de catalogus de nieuwste noemt
# (#1091; tot dan laadde ze "arbeidsmarkt", editie 2025, terwijl de catalogus 2026 als nieuwste markeerde).
ROA_PIN: str | None = None
ROA_PIN_REDEN: str | None = None


class RoaThemaOnbekend(ValueError):
    """Het geladen ROA-bestand heeft geen thema dat de app herkent: een fout, geen lege tabel (#1091)."""


@dataclass(frozen=True)
class RoaBestand:
    """Het ROA-bestand dat de app laadt, volgens de catalogus (`roa_resources.json`)."""

    resource: str  # de resourcenaam voor roa.load ("arbeidsmarkt_editie2026")
    editie: str | None  # "2026"
    bestandsnaam: str | None
    themas: tuple[str, ...]  # de thema's uit het gevalideerde schema
    pin: str | None = None  # de reden van een bewuste pin; None bij de nieuwste editie


def _roa_resources() -> list[dict]:
    from onderwijsbronnen import roa

    record = next((r for r in roa.catalog() if r.get("_roa_id") == _ROA_ID), None)
    if record is None:
        raise ValueError(f"ROA-dataset {_ROA_ID} staat niet in de catalogus")
    return [x for x in record.get("_resources") or [] if (x.get("schema") or {}).get("soort") == _ROA_SOORT]


def roa_bestand() -> RoaBestand:
    """Het arbeidsmarktbestand van AIS 2030 dat dashboards, get_roa_benchmark en de snippet laden (#1091): de editie
    die de catalogus `meest_recente_editie` noemt, of de pin in ROA_PIN met haar reden. Eén plek, zodat dashboard,
    chat, snippet en het venster Databronnen dezelfde editie noemen."""
    resources = _roa_resources()
    if ROA_PIN:
        gekozen = [x for x in resources if x["naam"] == ROA_PIN]
    else:
        gekozen = [x for x in resources if x["schema"].get("meest_recente_editie")]
    if len(gekozen) != 1:
        namen = [x["naam"] for x in resources]
        raise ValueError(f"geen eenduidig ROA-bestand ({ROA_PIN or 'meest_recente_editie'}) in {namen}")
    schema = gekozen[0]["schema"]
    return RoaBestand(
        resource=gekozen[0]["naam"],
        editie=schema.get("editie"),
        bestandsnaam=schema.get("bestandsnaam"),
        themas=tuple(schema.get("themas") or ()),
        pin=ROA_PIN_REDEN if ROA_PIN else None,
    )


def roa_sis(themas: Iterable[str]) -> str | None:
    """Het SIS-jaar ("SIS 2025") uit de thema's van een ROA-bestand of zijn schema; None zonder SIS-thema."""
    return next((m.group(1) for t in themas if (m := _ROA_SIS_PATROON.match(str(t)))), None)


def _themas(df: pd.DataFrame) -> tuple[str, ...]:
    """De thema's van het geladen bestand, één keer per lading uitgerekend."""
    themas = df.attrs.get("roa_themas")
    if themas is None:
        themas = tuple(sorted(df["thema"].dropna().astype(str).unique()))
        df.attrs["roa_themas"] = themas
    return themas


def _thema(df: pd.DataFrame, patroon: re.Pattern, onderdeel: str) -> str:
    """Het thema van een onderdeel in het geladen bestand; RoaThemaOnbekend als er geen (of meer dan één) is."""
    gevonden = [t for t in _themas(df) if patroon.match(t)]
    if len(gevonden) != 1:
        raise RoaThemaOnbekend(
            f"ROA-bestand zonder eenduidig thema voor {onderdeel} (gevonden: {gevonden or 'geen'}); "
            f"thema's in het bestand: {list(_themas(df))}"
        )
    return gevonden[0]


@actualiteit.Lading
def _roa() -> pd.DataFrame:
    from onderwijsbronnen import roa

    bestand = roa_bestand()
    df = roa.load(_ROA_ID, bestand.resource)
    brongebruik.meld(
        {
            "bron": "ROA",
            "dataset": _ROA_ID,
            # De editie van het bestand, uit het schema van onderwijsbronnen; de catalogus als het schema ontbreekt.
            "editie": (df.attrs.get("schema") or {}).get("editie") or bestand.editie,
            "sis": roa_sis(_themas(df)),  # "SIS 2025", uit de thema's van het bestand
            "versie": _versie(df),
            "opgehaald_op": actualiteit.nu().isoformat(),
        }
    )
    return df


def _versie(df: pd.DataFrame) -> str:
    """De versie in de kolom `versie` van het ROA-bestand ("v20251218"); meer versies met komma's."""
    return ", ".join(sorted(df["versie"].dropna().astype(str).unique())) or "onbekend"


def roa_versie() -> str:
    return _versie(_roa())


def roa_editie() -> str | None:
    """De editie van het geladen ROA-bestand ("2026"): uit zijn schema, anders uit de catalogus."""
    return (_roa().attrs.get("schema") or {}).get("editie") or roa_bestand().editie


def roa_sis_label() -> str:
    """Het SIS-jaar van het geladen bestand ("SIS 2025"); RoaThemaOnbekend zonder SIS-thema."""
    return roa_sis([roa_sis_thema()]) or ""


def roa_peiltekst(editie: str | None, sis: str | None, versie: str | None) -> str | None:
    """Het peilmoment van een ROA-bestand ("editie 2026, SIS 2025, versie v20260901"), in de bronregel van de chat en
    in het bronblok van de dashboards (#1091). Een deel dat er niet is, valt weg; None als er niets is."""
    delen = [f"editie {editie}" if editie else None, sis, f"versie {versie}" if versie else None]
    return ", ".join(d for d in delen if d) or None


def roa_peilmoment() -> str | None:
    """Het peilmoment van het geladen ROA-bestand (roa_peiltekst)."""
    df = _roa()
    return roa_peiltekst(roa_editie(), roa_sis(_themas(df)), _versie(df))


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


def roa_regio_alternatieven(naam: str, gekozen: str) -> list[str]:
    """De andere ROA-regio's die de opgegeven naam als heel woord dragen, naast de gekozen (#966).

    'Utrecht' wordt 'provincie Utrecht', maar 'Midden-Utrecht' is ook een arbeidsmarktregio; 'Groningen' wordt de
    arbeidsmarktregio, en 'provincie Groningen' bestaat ook. Een volledige naam ('Midden-Utrecht', 'provincie Utrecht')
    is eenduidig. Zonder voorvoegsel 'provincie ' vergeleken, hoofdletterongevoelig.
    """
    sleutel = " ".join(naam.split()).lower()
    heel_woord = re.compile(r"(?<!\w)" + re.escape(sleutel) + r"(?!\w)")
    return [
        r
        for r in roa_regios()
        if r not in (gekozen, ROA_LANDELIJK) and heel_woord.search(r.removeprefix(_ROA_PROVINCIE).lower())
    ]


def roa_regiotype(regionaam: str) -> str:
    if regionaam == ROA_LANDELIJK:
        return "landelijk"
    return "provincie" if regionaam.startswith(_ROA_PROVINCIE) else "arbeidsmarktregio"


def _categorieen(categorieen: tuple[str, ...] | dict[str, str]) -> dict[str, str]:
    """Detailniveau → laag uit ROA_AGGREGATIE; losse namen zijn opleidingsniveaus."""
    return categorieen if isinstance(categorieen, dict) else dict.fromkeys(categorieen, "niveau")


def roa_waarden(
    categorieen: tuple[str, ...] | dict[str, str],
    onderwerpen: tuple[str, ...],
    thema: str,
    regio: str = ROA_LANDELIJK,
) -> dict[str, dict[str, dict[str, float | int | str]]]:
    """ROA-waarden van één regio: detailniveau → onderwerp → {perc, aantal, typering}, alleen wat er staat.

    Elke categorie wordt in haar eigen laag gezocht: 'Master - techniek en ict' is zowel sector als subsector.
    """
    df = _roa()
    lagen = {naam: ROA_AGGREGATIE[laag] for naam, laag in _categorieen(categorieen).items()}
    rijen = df[
        (df["regionaam"] == regio)
        & (df["thema"] == thema)
        & (df["detailniveau"].map(lagen) == df["aggregatieniveau"])
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


def roa_categorieen(laag: str) -> list[str]:
    """Alle namen in één laag van ROA_AGGREGATIE ('subsector', 'type', ...), zoals de bron ze spelt."""
    df = _roa()
    return sorted(df.loc[df["aggregatieniveau"] == ROA_AGGREGATIE[laag], "detailniveau"].dropna().astype(str).unique())


def roa_opleidingstypen(subsector: str) -> list[str]:
    """De opleidingstypen onder een ROA-subsector, in de volgorde van hun code.

    De hiërarchie komt uit de bron: de ONR2019-code in `waarde` van een subsector eindigt op 0 (32120, 'Master -
    journalistiek, gedrag en maatschappij'), die van haar typen op 1-9 (32121-32123). Leeg als ROA de subsector niet
    kent of niet verder indeelt.
    """
    df = _roa()
    lagen = df["aggregatieniveau"]
    codes = pd.to_numeric(df["waarde"], errors="coerce")
    sub = codes[(lagen == ROA_AGGREGATIE["subsector"]) & (df["detailniveau"] == subsector)].dropna().unique()
    if len(sub) != 1 or sub[0] % 10:
        return []
    typen = df[(lagen == ROA_AGGREGATIE["type"]) & (codes // 10 == sub[0] // 10) & (codes != sub[0])]
    volgorde = typen.assign(code=codes).drop_duplicates("detailniveau").sort_values("code")
    return volgorde["detailniveau"].astype(str).tolist()


def roa_sis_thema(df: pd.DataFrame | None = None) -> str:
    """Het SIS-thema van het geladen bestand ("Schoolverlatersinformatie (SIS 2025)"); RoaThemaOnbekend zonder."""
    return _thema(_roa() if df is None else df, _ROA_SIS_PATROON, "de schoolverlatersinformatie")


def roa_prognose_thema(df: pd.DataFrame | None = None) -> str:
    """Het prognosethema van het geladen bestand; RoaThemaOnbekend zonder."""
    return _thema(_roa() if df is None else df, _ROA_PROGNOSE_PATROON, "de prognose tot 2030")


def roa_schoolverlaters(categorieen: tuple[str, ...] | dict[str, str], regio: str = ROA_LANDELIJK) -> dict:
    """Schoolverlatersinformatie per categorie; losse namen zijn opleidingsniveaus, een dict noemt de laag."""
    return roa_waarden(categorieen, ROA_SIS_INDICATOREN, roa_sis_thema(), regio)


def roa_prognose(categorieen: tuple[str, ...] | dict[str, str], regio: str = ROA_LANDELIJK) -> dict:
    """De prognose tot 2030 per categorie; losse namen zijn opleidingsniveaus, een dict noemt de laag."""
    return roa_waarden(categorieen, ROA_PROGNOSE_INDICATOREN, roa_prognose_thema(), regio)
