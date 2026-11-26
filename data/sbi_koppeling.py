"""De koppeltabel van SBI-secties aan onderwijssectoren (#1224), voor de matchscore van de arbeidsmarktdashboards.

CBS 83599NED telt de openstaande vacatures per bedrijfstak (een sectie van de SBI 2008), de gediplomeerden staan per
onderwijssector: in het mbo de hoofdgroep van DUO (`HOOFDGROEP NAAM`), in hbo en wo het onderdeel (`ONDERDEEL`). Welke
sector bij welke bedrijfstak hoort, staat in `sbi_onderwijssector.csv`, met de hand opgesteld (geen taalmodel), per
sectie één rij met per niveau de sectoren (gescheiden door ";") of "geen koppeling", en een korte reden. Een
onderwijssector die bij geen enkele sectie hoort, staat met reden in `onderwijssector_geen_sbi.csv`.

De beperking: een vacature telt bij de bedrijfstak van de werkgever, niet bij het beroep. Een verpleegkundige in een
fabriek telt bij C Industrie, een programmeur bij een bank bij K Financiële dienstverlening. De koppeling zegt dus welke
bedrijfstakken vooral de gediplomeerden van een sector aannemen, niet hoeveel vacatures er voor hun beroep zijn: de
matchscore die erop rust is indicatief.
"""

from __future__ import annotations

import csv
import functools
import math
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

KOPPELTABEL = Path(__file__).parent / "sbi_onderwijssector.csv"
ZONDER_KOPPELING = Path(__file__).parent / "onderwijssector_geen_sbi.csv"
NIVEAUS = ("mbo", "hbo", "wo")
GEEN_KOPPELING = "geen koppeling"
HERKOMST = "met de hand opgesteld, geen taalmodel"
BIJGEWERKT = "2026-11-26"  # de laatste keer dat de rijen zijn nagelopen
_KOLOMMEN = ["sectie", "naam", *NIVEAUS, "reden"]
_SCHEIDING = ";"


class OngeldigeKoppeltabel(ValueError):
    """De CSV wijkt af van wat de lader verwacht: een kolom, een lege reden, een dubbele sectie."""


@dataclass(frozen=True)
class Rij:
    sectie: str  # "C"
    naam: str  # "Industrie"
    sectoren: dict[str, tuple[str, ...]]  # niveau → sectoren; leeg bij "geen koppeling"
    reden: str


def _sectoren(cel: str) -> tuple[str, ...]:
    cel = cel.strip()
    if cel == GEEN_KOPPELING:
        return ()
    delen = tuple(d.strip() for d in cel.split(_SCHEIDING))
    if not cel or any(not d for d in delen):
        raise OngeldigeKoppeltabel(f"lege sector in {cel!r}: schrijf de sectoren of {GEEN_KOPPELING!r}")
    return delen


def lees(pad: Path = KOPPELTABEL) -> tuple[Rij, ...]:
    """De rijen van de koppeltabel, gevalideerd: de kolommen, één rij per sectie, elke cel gevuld en een reden."""
    with pad.open(encoding="utf-8", newline="") as f:
        lezer = csv.DictReader(f)
        if lezer.fieldnames != _KOLOMMEN:
            raise OngeldigeKoppeltabel(f"kolommen {lezer.fieldnames}, verwacht {_KOLOMMEN}")
        rijen = []
        for ruw in lezer:
            if not (ruw["sectie"] or "").strip() or not (ruw["reden"] or "").strip():
                raise OngeldigeKoppeltabel(f"rij zonder sectie of reden: {ruw}")
            rijen.append(
                Rij(
                    sectie=ruw["sectie"].strip(),
                    naam=ruw["naam"].strip(),
                    sectoren={n: _sectoren(ruw[n] or "") for n in NIVEAUS},
                    reden=ruw["reden"].strip(),
                )
            )
    dubbel = sorted({r.sectie for r in rijen if [s.sectie for s in rijen].count(r.sectie) > 1})
    if dubbel:
        raise OngeldigeKoppeltabel(f"secties met meer dan één rij: {dubbel}")
    return tuple(rijen)


def lees_zonder_koppeling(pad: Path = ZONDER_KOPPELING) -> dict[str, dict[str, str]]:
    """niveau → {sector: reden} voor de sectoren die bewust bij geen sectie horen."""
    uit: dict[str, dict[str, str]] = {n: {} for n in NIVEAUS}
    with pad.open(encoding="utf-8", newline="") as f:
        for ruw in csv.DictReader(f):
            niveau, sector, reden = (ruw[k].strip() for k in ("niveau", "sector", "reden"))
            if niveau not in uit or not sector or not reden:
                raise OngeldigeKoppeltabel(f"ongeldige rij zonder koppeling: {ruw}")
            uit[niveau][sector] = reden
    return uit


@functools.cache
def koppeltabel() -> tuple[Rij, ...]:
    """De koppeltabel uit de repo, één keer gelezen: pakketdata, geen bron die verandert."""
    return lees()


def niveau_van(onderwijs_type: str, soort: str | None = None) -> str:
    """Het niveau in de koppeltabel: mbo, of voor het ho de soort van de instelling (hbo of wo; onbekend: hbo)."""
    if onderwijs_type == "mbo":
        return "mbo"
    return soort if soort in ("hbo", "wo") else "hbo"


def secties_per_sector(niveau: str, rijen: tuple[Rij, ...] | None = None) -> dict[str, list[str]]:
    """sector → de secties ("C", "F") waar hij bij hoort, op één niveau."""
    uit: dict[str, list[str]] = {}
    for rij in rijen if rijen is not None else koppeltabel():
        for sector in rij.sectoren[niveau]:
            uit.setdefault(sector, []).append(rij.sectie)
    return uit


def vacatures_per_sector(
    vacatures_per_sectie: Mapping[str, int | None], niveau: str, rijen: tuple[Rij, ...] | None = None
) -> dict[str, int]:
    """Vacatures per onderwijssector uit vacatures per SBI-sectie, op één niveau.

    Een sectie bij k sectoren telt voor elk van hen voor 1/k mee, zodat de sectoren samen nooit meer vacatures hebben
    dan hun secties (zoals de oude telling naar rato, #455); per sector naar beneden afgerond. Een sectie zonder cijfer
    (None, "geen gegevens") telt niet mee. Een sector staat er alleen in als minstens één van zijn secties een cijfer
    heeft: zonder cijfers is zijn aantal onbekend, geen 0.
    """
    totaal: dict[str, Fraction] = {}
    for rij in rijen if rijen is not None else koppeltabel():
        sectoren = rij.sectoren[niveau]
        n = vacatures_per_sectie.get(rij.sectie)
        if not sectoren or n is None:
            continue
        for sector in sectoren:
            totaal[sector] = totaal.get(sector, Fraction(0)) + Fraction(n, len(sectoren))
    return {sector: math.floor(waarde) for sector, waarde in totaal.items()}
