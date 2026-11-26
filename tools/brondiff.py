"""Twee standen van één brontabel naast elkaar: wat "herhaal deze analyse" toont (#1240).

Alleen getallen en bronversie: de numerieke cellen per rij (de rij herkend aan haar dimensies), de dag waarop de bron de
tabel het laatst bijwerkte (`KeyMeta.bijgewerkt_op`) en de inhoudshash (#715). Nooit modeltekst: het eerdere antwoord
blijft staan, de herhaling is een tak ernaast. Gelijke versie en gelijke hash is "ongewijzigd".

De zinnen zeggen wat er veranderde bij de bron, nooit dat het eerdere antwoord niet klopte: het rustte op de stand van
toen (besluit #1236).
"""

import math
import numbers
from dataclasses import dataclass
from datetime import date

import pandas as pd

from .getal import nl_getal

ONGEWIJZIGD = "ongewijzigd"
BIJGEWERKT = "bijgewerkt"
# Wat de app van toen niet meer heeft (een herstart, de bovengrens of de termijn van de store): alleen de stand van nu.
ZONDER_TOEN = "niet_te_vergelijken"

# Kolommen die geen cijfer van de bron zijn: het rijnummer van CBS en de labels en status die de app ernaast zet.
_GEEN_CIJFER = frozenset({"ID"})
_LABEL = "_label"

ZIN_ONGEWIJZIGD = "Ongewijzigd: dezelfde cijfers en dezelfde bronversie{versie}."
ZIN_BIJGEWERKT = "Bron bijgewerkt op {datum}"
ZIN_ZELFDE_VERSIE = "Bronversie gelijk{versie}"
ZIN_VERSIE_ONBEKEND = "Bronversie onbekend"
ZIN_CIJFER = "cijfer verschilt: {toen} → {nu} ({waar})"
ZIN_CELLEN = "{n} cellen verschillen"
ZIN_GEEN_CIJFER_ANDERS = "dezelfde cijfers in deze tabel"
ZIN_INHOUD = "de tabel zelf is anders (bijvoorbeeld een label), geen cijfer"
ZIN_RIJEN_ERBIJ = "{n} {rijen} erbij"
ZIN_RIJEN_WEG = "{n} {rijen} niet meer in de tabel"
ZIN_VERSIE = "versie van {toen} → {nu}"
ZIN_ZONDER_TOEN = (
    "De cijfers van het eerdere antwoord bewaart de app niet meer, dus naast elkaar zetten kan niet. "
    "Nu: bijgewerkt op {nu}."
)


@dataclass(frozen=True)
class Stand:
    """Eén stand van de tabel: de dag waarop de bron haar bijwerkte en de inhoudshash."""

    bijgewerkt_op: str | None
    hash: str | None

    def als_dict(self) -> dict:
        return {"bijgewerkt_op": self.bijgewerkt_op, "hash": self.hash}


@dataclass(frozen=True)
class Celverschil:
    rij: str
    kolom: str
    toen: float | int | None
    nu: float | int | None


@dataclass(frozen=True)
class Verschil:
    cellen: int = 0
    eerste: Celverschil | None = None
    rijen_erbij: int = 0
    rijen_weg: int = 0

    def als_dict(self) -> dict:
        return {
            "cellen": self.cellen,
            "eerste": None
            if self.eerste is None
            else {"rij": self.eerste.rij, "kolom": self.eerste.kolom, "toen": self.eerste.toen, "nu": self.eerste.nu},
            "rijen_erbij": self.rijen_erbij,
            "rijen_weg": self.rijen_weg,
        }


def _leeg(waarde: object) -> bool:
    return waarde is None or (isinstance(waarde, float) and math.isnan(waarde)) or waarde is pd.NA


def _gelijk(a: object, b: object) -> bool:
    if _leeg(a) or _leeg(b):
        return _leeg(a) and _leeg(b)
    return a == b


def _python(waarde: object) -> float | int | None:
    """Een cel als gewoon getal voor JSON: numpy-typen en NaN niet."""
    if _leeg(waarde) or not isinstance(waarde, numbers.Real):
        return None
    getal = float(waarde)
    return int(getal) if getal.is_integer() else getal


def _dimensies(toen: pd.DataFrame, nu: pd.DataFrame, dims: list[str]) -> list[str]:
    return [d for d in dims if d in toen.columns and d in nu.columns]


def _cijferkolommen(toen: pd.DataFrame, nu: pd.DataFrame, dims: list[str]) -> list[str]:
    return [
        k
        for k in toen.columns
        if k in nu.columns
        and k not in dims
        and k not in _GEEN_CIJFER
        and not k.endswith(_LABEL)
        and pd.api.types.is_numeric_dtype(toen[k])
        and pd.api.types.is_numeric_dtype(nu[k])
    ]


def _rijen(df: pd.DataFrame, dims: list[str]) -> dict[tuple, dict]:
    """Per rij (haar dimensiecodes; zonder dimensies haar plaats) de rij zelf. Een dubbele sleutel: de eerste."""
    rijen: dict[tuple, dict] = {}
    for plaats, rij in enumerate(df.to_dict(orient="records")):
        sleutel = tuple(str(rij.get(d)).strip() for d in dims) if dims else (plaats,)
        rijen.setdefault(sleutel, rij)
    return rijen


def _rijnaam(rij: dict, dims: list[str], sleutel: tuple) -> str:
    """De rij in woorden: het label van elke dimensie als de app het heeft, anders de code."""
    if not dims:
        return f"rij {sleutel[0] + 1}"
    delen = []
    for d in dims:
        label = rij.get(d + _LABEL)
        delen.append(str(label).strip() if isinstance(label, str) and label.strip() else str(rij.get(d)).strip())
    return ", ".join(delen)


def vergelijk(
    toen: pd.DataFrame, nu: pd.DataFrame, dims: list[str], kolomtitels: dict[str, str] | None = None
) -> Verschil:
    """De numerieke cellen van `toen` en `nu`, per rij op haar dimensies: hoeveel verschillen, en het eerste verschil.

    Rijen die alleen in een van beide staan (een nieuwe periode, een rij die de bron weghaalde) tellen apart.
    """
    dims = _dimensies(toen, nu, dims)
    kolommen = _cijferkolommen(toen, nu, dims)
    oud, nieuw = _rijen(toen, dims), _rijen(nu, dims)
    titels = kolomtitels or {}
    cellen, eerste = 0, None
    for sleutel, rij in oud.items():
        if (andere := nieuw.get(sleutel)) is None:
            continue
        for kolom in kolommen:
            if _gelijk(rij.get(kolom), andere.get(kolom)):
                continue
            cellen += 1
            if eerste is None:
                eerste = Celverschil(
                    _rijnaam(andere, dims, sleutel),
                    titels.get(kolom) or kolom,
                    _python(rij.get(kolom)),
                    _python(andere.get(kolom)),
                )
    return Verschil(
        cellen=cellen,
        eerste=eerste,
        rijen_erbij=sum(1 for s in nieuw if s not in oud),
        rijen_weg=sum(1 for s in oud if s not in nieuw),
    )


def status(toen: Stand, nu: Stand, verschil: Verschil) -> str:
    """Gelijke versie en gelijke hash, en geen cel anders: ongewijzigd. Anders is de bron bijgewerkt."""
    gelijk = toen.bijgewerkt_op == nu.bijgewerkt_op and toen.hash == nu.hash
    leeg = not (verschil.cellen or verschil.rijen_erbij or verschil.rijen_weg)
    return ONGEWIJZIGD if gelijk and leeg else BIJGEWERKT


def nl_dag(iso: str | None) -> str:
    """2025-06-15 → 15-06-2025, zoals de bronregels; een onbekende dag heet "onbekend"."""
    if not iso:
        return "onbekend"
    try:
        return f"{date.fromisoformat(iso[:10]):%d-%m-%Y}"
    except ValueError:
        return "onbekend"


def _getal(waarde: float | int | None) -> str:
    return "leeg" if waarde is None else nl_getal(waarde)


def _rijen_woord(n: int) -> str:
    return "rij" if n == 1 else "rijen"


def samenvatting(toen: Stand | None, nu: Stand, verschil: Verschil | None) -> str:
    """De zin onder de herhaling, per tabel: wat de bron nu anders levert, met de oude en de nieuwe waarde."""
    if toen is None or verschil is None:
        return ZIN_ZONDER_TOEN.format(nu=nl_dag(nu.bijgewerkt_op))
    versie = f" (bijgewerkt op {nl_dag(nu.bijgewerkt_op)})" if nu.bijgewerkt_op else ""
    if status(toen, nu, verschil) == ONGEWIJZIGD:
        return ZIN_ONGEWIJZIGD.format(versie=versie)
    nieuwe_versie = toen.bijgewerkt_op != nu.bijgewerkt_op
    if nieuwe_versie:
        delen = [ZIN_BIJGEWERKT.format(datum=nl_dag(nu.bijgewerkt_op))]
    else:
        delen = [ZIN_ZELFDE_VERSIE.format(versie=versie) if nu.bijgewerkt_op else ZIN_VERSIE_ONBEKEND]
    if verschil.eerste is not None:
        e = verschil.eerste
        delen.append(ZIN_CIJFER.format(toen=_getal(e.toen), nu=_getal(e.nu), waar=f"{e.rij}; {e.kolom}"))
        if verschil.cellen > 1:
            delen.append(ZIN_CELLEN.format(n=verschil.cellen))
    elif not (verschil.rijen_erbij or verschil.rijen_weg):
        delen.append(ZIN_GEEN_CIJFER_ANDERS if toen.hash == nu.hash else ZIN_INHOUD)
    if verschil.rijen_erbij:
        delen.append(ZIN_RIJEN_ERBIJ.format(n=verschil.rijen_erbij, rijen=_rijen_woord(verschil.rijen_erbij)))
    if verschil.rijen_weg:
        delen.append(ZIN_RIJEN_WEG.format(n=verschil.rijen_weg, rijen=_rijen_woord(verschil.rijen_weg)))
    if nieuwe_versie:
        delen.append(ZIN_VERSIE.format(toen=nl_dag(toen.bijgewerkt_op), nu=nl_dag(nu.bijgewerkt_op)))
    return "; ".join(delen) + "."
