"""Een SKDB-rij zonder DUO-rij: een opleiding die na de DUO-peildatum begint, of niet (#1060, #1015). Code beslist.

De Studiekeuzedatabase toont het aanbod van het komende studiejaar, DUO telt het vorige (peildatum 1 oktober). Een
opleiding die na die peildatum begint, staat dus eerst alleen in de SKDB. Bij Avans (07GR) begint HBO-ICT (30020) op
1-9-2026 als opvolger van Informatica (34479); DUO 2025 telt 34479 (928) en nog geen 30020. `koppel_data` zei daarom
"geen DUO-rij", en het antwoord maakte er "Avans heeft geen ICT in DUO" van (heraudit 10-11, N07/N09). Het besluit van
#1015: de koppeling blijft brin + CROHO, zonder naamkoppeling of handmatige mapping, met een signaal uit RIO.

De regels, deterministisch uit de onderwijslicenties van RIO (`onderwijsbronnen.rio.licenties`):

1. **Nieuw na de peildatum.** De licentie van die brin + CROHO die vandaag geldt, begint ná de DUO-peildatum
   (1 oktober van het laatste studiejaar in de DUO-tabel). Reden: "nieuw per <begindatum>, nog niet in DUO <jaar>".
2. **Voorgangers.** Licenties van dezelfde brin die op de DUO-peildatum bestonden en vandaag niet meer, in hetzelfde
   `onderdeel` als de nieuwe, met als einddatum de begindatum van de nieuwe. Ze worden genoemd met hun CROHO en, als
   de DUO-tabel ze heeft, hun aantal; nooit opgeteld bij de nieuwe: Avans zette alleen Informatica om, Technische
   Informatica (34475) loopt door en staat apart in de SKDB, dus optellen telt dubbel.
3. Anders, of als RIO niet antwoordt: "geen DUO-rij", zoals voorheen. Een storing breekt de koppeling niet; er komt een
   vaste waarschuwing bij dat het niet is nagegaan (#970), met een WARNING in het log.

De licentielijsten staan per (brin, datum) een dag in de cache (`core.actualiteit.Lading`), de erkenning per licentie
ook. Alleen de licenties die tussen de twee dagen wisselen, hebben hun erkenning nodig: bij Avans 2 lijsten en 6
erkenningen. Boven MAX_INSTELLINGEN instellingen met een SKDB-rij zonder DUO-rij vraagt de koppeling RIO niets
(zoals `fusies`): dan is het een overzicht, geen vraag over één instelling.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import pandas as pd
from onderwijsbronnen import sleutels as kern
from onderwijsbronnen.rio import Licentie, met_erkenning, onderwijslicenties

from core import actualiteit

from . import periode

logger = logging.getLogger(__name__)

KOPPELREDEN = "koppelreden"
GEEN_DUO_RIJ = "geen DUO-rij"
# DUO telt studenten en inschrijvingen per 1 oktober: de telling van startjaar J is die van 1-10-J (zoals fusies).
_TELDAG = (10, 1)
MAX_INSTELLINGEN = 10
TOELICHTING = (
    f"Een rij met {KOPPELREDEN} 'nieuw per …' (zie opvolgers) is een opleiding die volgens RIO pas na de DUO-peildatum "
    "begint: zeg dat ze nieuw is en nog niet in dat DUO-jaar zit, niet dat er data mist. Noem haar voorgangers met hun "
    "eigen DUO-aantal; tel die niet op bij de nieuwe opleiding en reken er geen groei of krimp mee uit."
)


def d_m_j(iso: str) -> str:
    """2026-09-01 → 1-9-2026."""
    dag = date.fromisoformat(iso)
    return f"{dag.day}-{dag.month}-{dag.year}"


def peildatum(jaar: int) -> str:
    """De DUO-peildatum van startjaar `jaar`: 1 oktober (jjjj-mm-dd)."""
    return date(jaar, *_TELDAG).isoformat()


# --- De regels, puur: alleen licenties en data, geen netwerk ---------------------------------------------------------


def te_bepalen(peil: str, nu: Iterable[Licentie], toen: Iterable[Licentie]) -> list[Licentie]:
    """De licenties waarvan de regels de erkenning (CROHO, onderdeel) nodig hebben: die van vandaag die na `peil`
    beginnen, en die van `peil` die vandaag niet meer gelden."""
    nu = list(nu)
    ids_nu = {lic.id for lic in nu}
    return [lic for lic in nu if (lic.begindatum or "") > peil] + [lic for lic in toen if lic.id not in ids_nu]


def nieuwe_licentie(croho: str, peil: str, nu: Iterable[Licentie]) -> Licentie | None:
    """Regel 1: de licentie van `croho` die vandaag geldt en ná `peil` begint; None als er geen is of als `croho` ook
    een licentie heeft die al vóór de peildatum gold (dan is de opleiding niet nieuw)."""
    eigen = [lic for lic in nu if lic.croho == croho]
    if not eigen or any(not lic.begindatum or lic.begindatum <= peil for lic in eigen):
        return None
    return min(eigen, key=lambda lic: lic.begindatum or "")


def voorgangers(nieuw: Licentie, nu: Iterable[Licentie], toen: Iterable[Licentie]) -> list[Licentie]:
    """Regel 2: de licenties van de peildatum die vandaag niet meer gelden, in hetzelfde onderdeel als `nieuw`, met als
    einddatum haar begindatum. Gesorteerd op CROHO."""
    if not nieuw.onderdeel or not nieuw.begindatum:
        return []
    ids_nu = {lic.id for lic in nu}
    gevonden = [
        lic
        for lic in toen
        if lic.id not in ids_nu
        and lic.croho
        and lic.onderdeel == nieuw.onderdeel
        and (lic.einddatum or lic.instroom_einddatum) == nieuw.begindatum
    ]
    return sorted(gevonden, key=lambda lic: lic.croho or "")


# --- De DUO-kant -----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DuoTabel:
    """De DUO-kant van de koppeling: de tabel, haar brin- en CROHO-kolom en het laatste studiejaar erin."""

    df: pd.DataFrame
    brin: str
    croho: str
    jaar: int
    periodekolom: str | None = None

    @classmethod
    def van(cls, df: pd.DataFrame, kolommen: dict[str, str], meta) -> DuoTabel | None:
        """None als het laatste studiejaar niet vast te stellen is: dan is er geen peildatum, en geen reden."""
        periodekolom = meta.periodekolom if meta is not None else None
        jaren = periode.dekking(df, "duo", periodekolom) or (meta.schooljaren if meta is not None else None)
        if not jaren or "brin" not in kolommen or "croho" not in kolommen:
            return None
        return cls(df, kolommen["brin"], kolommen["croho"], max(jaren), periodekolom)

    def rijen(self, brin: str, croho: str) -> pd.DataFrame:
        """De rijen van brin + CROHO in het laatste studiejaar."""
        df = self.df
        raak = (df[self.brin].map(kern.norm_code) == brin) & (df[self.croho].map(kern.norm_opleidingscode) == croho)
        if self.periodekolom and self.periodekolom in df.columns:
            raak &= df[self.periodekolom].map(lambda w: periode.startjaar("duo", w)) == self.jaar
        return df[raak]


def _aantalkolommen(df: pd.DataFrame) -> list[str]:
    return [
        k
        for k in df.columns
        if str(k).upper().startswith("AANTAL")
        and pd.api.types.is_numeric_dtype(df[k])
        and not pd.api.types.is_bool_dtype(df[k])
    ]


def _getal(waarde) -> int | float | None:
    if waarde is None or pd.isna(waarde):
        return None
    getal = float(waarde)
    return int(getal) if getal.is_integer() else getal


def _naam(rijen: pd.DataFrame) -> str | None:
    kolom = next((k for k in rijen.columns if str(k).upper() in ("OPLEIDINGSNAAM_ACTUEEL", "OPLEIDINGSNAAM")), None)
    namen = rijen[kolom].dropna() if kolom else pd.Series(dtype=object)
    return str(namen.iloc[0]) if len(namen) else None


@dataclass(frozen=True)
class Voorganger:
    """Een voorganger zoals de koppeling hem noemt. `aantal` alleen bij precies één DUO-rij met één aantalkolom: bij
    meer rijen (een rij per vorm of geslacht) kiest de code niet welke som bedoeld is; `rijen` zegt hoeveel het er zijn."""

    croho: str
    einde: str
    naam: str | None = None
    aantal: int | float | None = None
    rijen: int = 0

    @classmethod
    def uit(cls, lic: Licentie, brin: str, duo: DuoTabel) -> Voorganger:
        rijen = duo.rijen(brin, lic.croho or "")
        kolommen = _aantalkolommen(rijen)
        aantal = _getal(rijen[kolommen[0]].iloc[0]) if len(rijen) == 1 and len(kolommen) == 1 else None
        einde = lic.einddatum or lic.instroom_einddatum or ""
        return cls(lic.croho or "", einde, _naam(rijen), aantal, len(rijen))

    def zin(self, jaar: int) -> str:
        wie = f"{self.croho} {self.naam}" if self.naam else self.croho
        if self.aantal is not None:
            duo = f"in DUO {jaar}: {self.aantal}"
        elif self.rijen:
            duo = f"in DUO {jaar}: {self.rijen} rijen in de koppeling"
        else:
            duo = "niet in deze DUO-tabel"
        return f"{wie} (instroom tot {d_m_j(self.einde)}; {duo})"

    def als_dict(self, jaar: int) -> dict:
        uit: dict = {"croho": self.croho, "einde": d_m_j(self.einde), "duo_jaar": jaar}
        if self.naam:
            uit["naam"] = self.naam
        if self.aantal is not None:
            uit["duo_aantal"] = self.aantal
        elif self.rijen:
            uit["duo_rijen"] = self.rijen
        return uit


@dataclass(frozen=True)
class Opvolging:
    """Een SKDB-rij zonder DUO-rij die volgens RIO na de DUO-peildatum begint."""

    brin: str
    croho: str
    begindatum: str
    jaar: int
    voorgangers: tuple[Voorganger, ...] = ()

    @property
    def reden(self) -> str:
        return f"nieuw per {d_m_j(self.begindatum)}, nog niet in DUO {self.jaar}"

    @property
    def tekst(self) -> str:
        zin = f"{self.brin}/{self.croho}: {self.reden}."
        if not self.voorgangers:
            return f"{zin} RIO noemt geen voorganger in hetzelfde onderdeel."
        namen = "; ".join(v.zin(self.jaar) for v in self.voorgangers)
        woord = "Voorganger" if len(self.voorgangers) == 1 else "Voorgangers"
        return f"{zin} {woord} volgens RIO: {namen}. Genoemd, niet opgeteld bij {self.croho}."

    def als_dict(self) -> dict:
        return {
            "brin": self.brin,
            "croho": self.croho,
            "reden": self.reden,
            "voorgangers": [v.als_dict(self.jaar) for v in self.voorgangers],
            "tekst": self.tekst,
        }


# --- RIO, een dag in de cache ----------------------------------------------------------------------------------------


@actualiteit.Lading
def _licenties(brin: str, datum: str) -> tuple[Licentie, ...]:
    return onderwijslicenties(brin, datum)


@actualiteit.Lading
def _erkenning(licentie: Licentie) -> Licentie:
    return met_erkenning(licentie)


def wis_caches() -> None:
    _licenties.cache_clear()
    _erkenning.cache_clear()


def _wissel(brin: str, peil: str, vandaag: str) -> tuple[list[Licentie], list[Licentie]]:
    """De licenties van vandaag en van de peildatum; alleen die de regels nodig hebben, met hun erkenning."""
    nu, toen = _licenties(brin, vandaag), _licenties(brin, peil)
    nodig = {lic.id for lic in te_bepalen(peil, nu, toen)}

    def vul(licenties: Iterable[Licentie]) -> list[Licentie]:
        return [_erkenning(lic) if lic.id in nodig else lic for lic in licenties]

    return vul(nu), vul(toen)


def _opvolging(brin: str, croho: str, duo: DuoTabel, nu: list[Licentie], toen: list[Licentie]) -> Opvolging | None:
    peil = peildatum(duo.jaar)
    if (nieuw := nieuwe_licentie(croho, peil, nu)) is None or not nieuw.begindatum:
        return None
    paar = tuple(Voorganger.uit(lic, brin, duo) for lic in voorgangers(nieuw, nu, toen))
    return Opvolging(brin, croho, nieuw.begindatum, duo.jaar, paar)


@dataclass(frozen=True)
class Uitslag:
    opvolgingen: dict[tuple[str, str], Opvolging]
    niet_nagegaan: tuple[str, ...] = ()


def bepaal(zonder_duo: Iterable[tuple[str, str]], duo: DuoTabel, vandaag: date | None = None) -> Uitslag:
    """Per (brin, CROHO) zonder DUO-rij de opvolging, als RIO er een geeft. Een storing per instelling komt in
    `niet_nagegaan`; die rijen houden "geen DUO-rij"."""
    peil, dag = peildatum(duo.jaar), (vandaag or date.today()).isoformat()
    per_brin: dict[str, list[str]] = {}
    for brin, croho in zonder_duo:
        per_brin.setdefault(brin, []).append(croho)
    if peil >= dag or not per_brin or len(per_brin) > MAX_INSTELLINGEN:
        return Uitslag({})
    gevonden: dict[tuple[str, str], Opvolging] = {}
    storing: list[str] = []
    for brin in sorted(per_brin):
        try:
            nu, toen = _wissel(brin, peil, dag)
        except Exception as e:  # een storing bij RIO breekt de koppeling niet: "geen DUO-rij" en een vaste regel
            logger.warning("OPVOLGER_ONBEKEND brin=%s fout=%s", brin, type(e).__name__)
            storing.append(brin)
            continue
        for croho in per_brin[brin]:
            if (opvolging := _opvolging(brin, croho, duo, nu, toen)) is not None:
                gevonden[(brin, croho)] = opvolging
                logger.info(
                    "OPVOLGER brin=%s croho=%s voorgangers=%s",
                    brin,
                    croho,
                    ",".join(v.croho for v in opvolging.voorgangers),
                )
    return Uitslag(gevonden, tuple(storing))


def bij_koppeling(
    df: pd.DataFrame, statuskolom: str, status: str, duo: DuoTabel, vandaag: date | None = None
) -> tuple[pd.DataFrame, dict]:
    """De koppeling met per SKDB-rij zonder DUO-rij (`status`) de reden, en wat het toolresultaat erover zegt.

    Alleen als RIO minstens één opvolger geeft, krijgt de koppeling de kolom `koppelreden` (na `statuskolom`):
    "nieuw per …" of "geen DUO-rij" bij `status`, leeg bij de andere rijen. Anders blijft ze zoals ze was. Het tweede
    deel heeft `opvolgers`, een aanvulling op de `toelichting` van `status` en een `waarschuwing` bij een storing.
    """
    if KOPPELREDEN in df.columns:  # al een reden (een eigen kolom met die naam): niet overschrijven
        return df, {}
    zonder = df.loc[df[statuskolom] == status, ["brin", "croho"]].dropna().drop_duplicates()
    uitslag = bepaal(zonder.itertuples(index=False, name=None), duo, vandaag)
    extra: dict = {}
    if uitslag.niet_nagegaan:
        extra["waarschuwing"] = (
            f"Of een rij {status} een nieuwe opleiding is die nog niet in DUO {duo.jaar} zit, is niet nagegaan voor "
            f"{', '.join(uitslag.niet_nagegaan)}: RIO gaf een storing. Die rijen houden de reden {GEEN_DUO_RIJ}."
        )
    if not uitslag.opvolgingen:
        return df, extra
    redenen = [
        (uitslag.opvolgingen[(b, c)].reden if (b, c) in uitslag.opvolgingen else GEEN_DUO_RIJ) if s == status else None
        for b, c, s in zip(df["brin"], df["croho"], df[statuskolom], strict=True)
    ]
    df = df.copy()
    df.insert(list(df.columns).index(statuskolom) + 1, KOPPELREDEN, redenen)
    extra["opvolgers"] = [uitslag.opvolgingen[k].als_dict() for k in sorted(uitslag.opvolgingen)]
    extra["toelichting"] = {status: TOELICHTING}
    return df, extra
