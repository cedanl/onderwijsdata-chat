"""Profiel van een geladen tabel: schema, statistiek en korrel, zonder model (#59, #61).

De catalogus kent per kolom een steekproef, en `kolomprofiel` (#362) het bereik en de unieke
waarden van een DUO-bestand bij het laden. Wat het model daarna nog zelf moest raden, staat
hier per key: hoeveel cellen leeg zijn, welke waarden het vaakst voorkomen, waar een kolom op
lijkt (identificatie, jaar, schooljaar, geocode, categorie, getal, datum, tekst) en welke
kolommen samen één rij aanwijzen: de korrel. Die laatste zegt of een som over de tabel dubbel
telt.

Pure pandas, één keer per key berekend en onthouden zolang dezelfde data onder die key staat;
de tool `dataset_profiel` leest het profiel, hij rekent niet opnieuw.
"""

import json
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, replace
from itertools import combinations
from typing import Any

import pandas as pd

from . import fouten, store

TOP = 5  # zoveel vaakst voorkomende waarden per kolom
MAX_SLEUTELKOLOMMEN = 6  # kandidaten voor de korrel; meer combinaties kosten op 50k rijen te veel
MAX_SLEUTELLENGTE = 3
MAX_SLEUTELS = 5
_PROFIELEN_MAX = 64

IDENTIFICATIE = "identificatie"
JAAR = "jaar"
SCHOOLJAAR = "schooljaar"
GEOCODE = "geocode"
CATEGORIE = "categorie"
GETAL = "getal"
DATUM = "datum"
TEKST = "tekst"

# Een kolomnaam die iets aanwijst in plaats van meet (dezelfde lezing als agent/meetwaarden.py).
_IDENTIFICATIE = re.compile(r"code|nummer|brin|(?:^|[_\s])(?:id|nr|key)(?:$|[_\s])", re.IGNORECASE)
_JAARNAAM = re.compile(r"jaar|year", re.IGNORECASE)
_SCHOOLJAAR = r"\d{4}SJ\d{2}|\d{4}\s*/\s*'?\d{2}(?:\d{2})?"  # 2024SJ00, 2021/22, 2021/'22, 2021/2022
_GEOCODE = r"(?:GM|PV|CR|AM|LD|NL)\d{2,4}"
_JAREN = (1900, 2100)
_ONHASHBAAR = (list, dict, set)
# Bij gelijke onderscheidendheid gaat een code vóór een naam in de korrel: dat is wat een bron als sleutel bedoelt.
_VOORKEUR = {IDENTIFICATIE: 0, JAAR: 1, SCHOOLJAAR: 2, GEOCODE: 3, CATEGORIE: 4, TEKST: 5}


@dataclass(frozen=True)
class Kolom:
    """Wat één kolom bevat: type, waar hij op lijkt, lege en unieke cellen, bereik en vaakste waarden."""

    type: str
    lijkt_op: str
    leeg: int
    leeg_pct: float
    uniek: int
    uniek_pct: float
    min: Any = None  # getallen, jaren en datums
    max: Any = None
    kwartielen: tuple[Any, Any, Any] | None = None  # 25/50/75 voor een meetkolom
    top: tuple[tuple[str, int], ...] = ()  # waarde → aantal, vaakste eerst; niet voor een meetkolom

    def als_dict(self) -> dict:
        uit: dict = {
            "type": self.type,
            "lijkt_op": self.lijkt_op,
            "leeg": self.leeg,
            "leeg_pct": self.leeg_pct,
            "uniek": self.uniek,
            "uniek_pct": self.uniek_pct,
        }
        if self.min is not None:
            uit["min"], uit["max"] = self.min, self.max
        if self.kwartielen is not None:
            uit["kwartielen"] = list(self.kwartielen)
        if self.top:
            uit["top"] = [{"waarde": waarde, "aantal": aantal} for waarde, aantal in self.top]
        return uit


@dataclass(frozen=True)
class Profiel:
    rijen: int
    kolommen: dict[str, Kolom]
    dubbele_rijen_pct: float
    kandidaat_sleutels: tuple[tuple[str, ...], ...]  # kleinste combinaties die elke rij apart aanwijzen

    def als_dict(self) -> dict:
        return {
            "dubbele_rijen_pct": self.dubbele_rijen_pct,
            "kandidaat_sleutels": [list(sleutel) for sleutel in self.kandidaat_sleutels],
            "kolommen": {naam: kolom.als_dict() for naam, kolom in self.kolommen.items()},
        }


def _pct(deel: int, geheel: int) -> float:
    return round(100 * deel / geheel, 1) if geheel else 0.0


def _getal(v):
    """Een numpy-getal als JSON-getal, een datum als ISO-dag; 4147.0 is een telling (#222)."""
    if isinstance(v, pd.Timestamp):
        return v.isoformat()[:10]
    v = v.item() if hasattr(v, "item") else v
    return int(v) if isinstance(v, float) and v.is_integer() else v


def _hashbaar(frame: pd.DataFrame) -> pd.DataFrame:
    """Een cel met een lijst of dict (RIO) als tekst, zodat nunique en duplicated erop werken."""
    objecten = [c for c in frame.columns if frame[c].dtype == object]
    onhashbaar = [c for c in objecten if frame[c].map(lambda v: isinstance(v, _ONHASHBAAR)).any()]
    if not onhashbaar:
        return frame
    plat = frame.copy()
    for c in onhashbaar:
        plat[c] = frame[c].map(
            lambda v: json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, _ONHASHBAAR) else v
        )
    return plat


def _lijkt_op(naam: str, reeks: pd.Series, waarden: pd.Series, uniek: int) -> str:
    """Waar een kolom op lijkt, uit naam en waarden; een meetkolom (getal) is de rest."""
    if pd.api.types.is_datetime64_any_dtype(reeks):
        return DATUM
    if pd.api.types.is_bool_dtype(reeks):
        return CATEGORIE
    if pd.api.types.is_numeric_dtype(reeks):
        if not waarden.empty and _JAARNAAM.search(naam) and waarden.between(*_JAREN).all():
            return JAAR
        return IDENTIFICATIE if _IDENTIFICATIE.search(naam) else GETAL
    tekst = waarden.astype(str).str.strip()
    if not tekst.empty and tekst.str.fullmatch(_SCHOOLJAAR).all():
        return SCHOOLJAAR
    if not tekst.empty and tekst.str.fullmatch(_GEOCODE).all():
        return GEOCODE
    if _IDENTIFICATIE.search(naam):
        return IDENTIFICATIE
    if uniek <= max(12, len(waarden) // 20):
        return CATEGORIE
    return TEKST


def _kolom(naam: str, reeks: pd.Series) -> Kolom:
    waarden = reeks.dropna()
    uniek = int(waarden.nunique())
    soort = _lijkt_op(naam, reeks, waarden, uniek)
    leeg = len(reeks) - len(waarden)
    kolom = Kolom(str(reeks.dtype), soort, leeg, _pct(leeg, len(reeks)), uniek, _pct(uniek, len(waarden)))
    if waarden.empty:
        return kolom
    if soort in (GETAL, JAAR, DATUM):
        kwartielen = tuple(_getal(q) for q in waarden.quantile([0.25, 0.5, 0.75])) if soort == GETAL else None
        kolom = replace(kolom, min=_getal(waarden.min()), max=_getal(waarden.max()), kwartielen=kwartielen)
    if soort != GETAL:
        top = waarden.astype(str).value_counts().head(TOP)
        kolom = replace(kolom, top=tuple((str(waarde), int(aantal)) for waarde, aantal in top.items()))
    return kolom


def _kandidaat_sleutels(frame: pd.DataFrame, kolommen: dict[str, Kolom]) -> tuple[tuple[str, ...], ...]:
    """De kleinste kolomcombinaties die elke rij apart aanwijzen, tot MAX_SLEUTELLENGTE kolommen.

    Meetkolommen en datums doen niet mee, lege cellen ook niet; de meest onderscheidende
    kolommen eerst, bij gelijke stand een code vóór een naam. Eén rij heeft geen korrel.
    """
    if len(frame) < 2:
        return ()
    kandidaten = [n for n, k in kolommen.items() if k.lijkt_op not in (GETAL, DATUM) and k.leeg == 0 and k.uniek > 1]
    kandidaten = sorted(kandidaten, key=lambda n: (-kolommen[n].uniek, _VOORKEUR[kolommen[n].lijkt_op]))
    kandidaten = kandidaten[:MAX_SLEUTELKOLOMMEN]
    for lengte in range(1, min(MAX_SLEUTELLENGTE, len(kandidaten)) + 1):
        gevonden = [
            combo for combo in combinations(kandidaten, lengte) if not frame.duplicated(subset=list(combo)).any()
        ]
        if gevonden:
            return tuple(gevonden[:MAX_SLEUTELS])
    return ()


def profileer(df: pd.DataFrame) -> Profiel:
    """Het profiel van `df`: per kolom, de dubbele rijen en de korrel. Werkt ook op een lege tabel."""
    plat = _hashbaar(df)
    kolommen = {str(naam): _kolom(str(naam), plat[naam]) for naam in plat.columns}
    dubbel = int(plat.duplicated().sum()) if len(plat) else 0
    return Profiel(len(df), kolommen, _pct(dubbel, len(df)), _kandidaat_sleutels(plat, kolommen))


# Eén profiel per key, zolang hetzelfde object onder die key staat; de langst niet gelezen gaan eruit.
_profielen: OrderedDict[str, tuple[tuple, Profiel]] = OrderedDict()
_slot = threading.Lock()


def _kenmerk(df: pd.DataFrame) -> tuple:
    return (id(df), df.shape, tuple(str(c) for c in df.columns))


def profiel_van(key: str) -> Profiel | None:
    """Het profiel van de data achter `key`, uit de cache of nu berekend; None zonder tabel."""
    df = store.get(key)
    if not isinstance(df, pd.DataFrame):
        return None
    kenmerk = _kenmerk(df)
    with _slot:
        bekend = _profielen.get(key)
        if bekend is not None and bekend[0] == kenmerk:
            _profielen.move_to_end(key)
            return bekend[1]
    profiel = profileer(df)
    with _slot:
        _profielen[key] = (kenmerk, profiel)
        _profielen.move_to_end(key)
        while len(_profielen) > _PROFIELEN_MAX:
            _profielen.popitem(last=False)
    return profiel


def vergeet() -> None:
    with _slot:
        _profielen.clear()


def _korrel(profiel: Profiel) -> str:
    if profiel.rijen < 2:
        return "niet te bepalen: minder dan twee rijen"
    if not profiel.kandidaat_sleutels:
        return (
            f"geen combinatie tot {MAX_SLEUTELLENGTE} kolommen wijst elke rij apart aan; tel niet zonder te ontdubbelen"
        )
    return "elke rij is uniek op " + " + ".join(profiel.kandidaat_sleutels[0])


def dataset_profiel(data_key: str) -> str:
    """Het profiel van een geladen tabel voor het model: schema, statistiek en korrel, uit de cache."""
    profiel = profiel_van(data_key)
    if profiel is None:
        return fouten.onbekende_key(data_key)
    volledig = store.volledig(data_key)
    uit: dict = {
        "data_key": data_key,
        **store.rijtelling(profiel.rijen, volledig),
        "korrel": _korrel(profiel),
        **profiel.als_dict(),
    }
    if not volledig:
        uit["waarschuwing"] = "Profiel van de opgehaalde pagina, niet van de hele bron."
    return json.dumps(uit, ensure_ascii=False, separators=(",", ":"), default=str)
