"""Een onderdrukte cel terugrekenen als totaal min de zichtbare delen, geven we niet (#1265).

DUO schrijft een aantal van 1 tot en met 4 als -1, CBS een geheim of onbetrouwbaar cijfer als '.'. De store maakt die
cellen leeg (`core.sentinels`), zodat een som een ondergrens is. Maar staat het totaal ergens anders (een totaalrij in
dezelfde tabel, of een totaalbestand), dan is de cel exact terug te rekenen: totaal min de zichtbare delen. Dat is
differencing, en de bron onderdrukte de cel juist om dat kleine aantal niet te publiceren.

Deze module zoekt per onderdrukte cel de groep waarin zij het enige ontbrekende deel is (de rijen die alleen in één
dimensie verschillen, zonder totaalrij) en de totalen die precies bij die groep horen: een totaalrij van dezelfde
tabel, of een andere tabel die die dimensie niet heeft (of alleen als totaal) en op de andere dimensies past. Totaal
min de zichtbare delen is de reconstructie. Een uitkomst van run_analysis of compute_kpi, of een getal in het antwoord,
die gelijk is aan een reconstructie, wordt geweigerd met `MELDING`.

Wat niet als reconstructie telt (geen valse weigering): een verschil van twee totalen die allebei de onderdrukte cel
bevatten (de cel valt weg), een groep met twee of meer onderdrukte cellen (dan is geen van beide exact), en een
tabel die van de onderdrukte tabel zelf is afgeleid (haar som is een ondergrens, geen totaal). Bij DUO is een
reconstructie 1 tot en met 4: een verschil daarbuiten is niet de cel.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from . import duo, periode, store

MELDING = "Deze cel is door de bron onderdrukt; terugrekenen geven we niet."

# DUO onderdrukt 1 tot en met 4 (data/domeinregels.toml, [sentinel]): een exacte reconstructie ligt daartussen.
_DUO_BEREIK = (1, 4)
# Een totaalrij: "Totaal", "Totaal hbo", "Total", of een CBS-totaalcode (T001038 = mannen en vrouwen).
_TOTAAL = re.compile(r"totaa?l|^T\d{6}$", re.IGNORECASE)
_GETAL = re.compile(r"-?\d+(?:[.,]\d+)?")
_DECIMALEN = 6


@dataclass(frozen=True)
class Reconstructie:
    """Eén onderdrukte cel, terug te rekenen als `totaal - zichtbaar`."""

    waarde: float
    totaal: float
    zichtbaar: float
    label: str  # de waarde van de cel in de dimensie waarin ze van de andere delen verschilt
    kolom: str
    key: str


def _is_totaal(waarde: Any) -> bool:
    return isinstance(waarde, str) and bool(_TOTAAL.search(waarde.strip()))


def _totaalrijen(kolom: pd.Series) -> pd.Series:
    return kolom.map(_is_totaal).astype(bool)


def _dimensies(df: pd.DataFrame, meta: store.KeyMeta | None) -> list[str]:
    """De kolommen die een rij aanwijzen: tekst, en een periodekolom (ook als getal)."""
    periodekolom = meta.periodekolom if meta else None
    return [
        str(k)
        for k in df.columns
        if not pd.api.types.is_numeric_dtype(df[k])
        or pd.api.types.is_bool_dtype(df[k])
        or k == periodekolom
        or k in periode.JAARKOLOMMEN
    ]


def _meetkolommen(df: pd.DataFrame, dims: list[str]) -> list[str]:
    return [str(k) for k in df.columns if k not in dims and pd.api.types.is_numeric_dtype(df[k])]


def _bron(key: str, meta: store.KeyMeta | None) -> str:
    return meta.bron if meta and meta.bron else key.split(":", 1)[0]


def _in_bereik(waarde: float, bron: str) -> bool:
    if not math.isfinite(waarde) or waarde <= 0:
        return False
    if bron == "duo":
        laag, hoog = _DUO_BEREIK
        return laag <= waarde <= hoog
    return True


def _scope(keys: Iterable[str]) -> list[str]:
    """De keys en de geladen tabellen waar ze op rusten, elk één keer, alleen wat de store nog heeft."""
    uit: list[str] = []
    for key in keys:
        if not isinstance(key, str):
            continue
        key = store.canoniek(key)
        for k in (key, *store.bronsleutels(key)):
            if k not in uit and isinstance(store.get(k), pd.DataFrame):
                uit.append(k)
    return uit


def _groepen(df: pd.DataFrame, onderdrukt: pd.Series, kolom: str, dim: str, andere: list[str]) -> pd.DataFrame:
    """Per groep van rijen die alleen in `dim` verschillen (zonder totaalrij): de groepen met precies één ontbrekend
    deel, en dat deel een onderdrukte cel. Kolommen: `andere`, `_zichtbaar` (som van de andere delen), `_label`."""
    delen = df.loc[~_totaalrijen(df[dim].astype(object))]
    if delen.empty:
        return pd.DataFrame()
    frame = delen[[*andere, dim]].copy()
    frame["_waarde"] = pd.to_numeric(delen[kolom], errors="coerce")
    frame["_leeg"] = frame["_waarde"].isna()
    frame["_onderdrukt"] = onderdrukt.reindex(delen.index, fill_value=False).astype(bool)
    sleutel = andere or (lambda _: 0)
    per = frame.groupby(sleutel, dropna=False, sort=False)
    samen = pd.DataFrame(
        {
            "_n": per.size(),
            "_leeg": per["_leeg"].sum(),
            "_onderdrukt": per["_onderdrukt"].sum(),
            "_zichtbaar": per["_waarde"].sum(min_count=0),
        }
    )
    goed = samen[(samen["_n"] >= 2) & (samen["_leeg"] == 1) & (samen["_onderdrukt"] == 1)]
    if goed.empty:
        return pd.DataFrame()
    labels = frame.loc[frame["_onderdrukt"]].groupby(sleutel, dropna=False, sort=False)[dim].first()
    goed = goed.assign(_label=labels.reindex(goed.index).astype(str))
    return goed.reset_index(drop=not andere)[[*andere, "_zichtbaar", "_label"]]


def _totalen_zelfde(df: pd.DataFrame, kolom: str, dim: str, andere: list[str]) -> pd.DataFrame:
    """De totaalrijen van `dim` in dezelfde tabel: kolommen `andere` en `_totaal`."""
    rijen = df.loc[_totaalrijen(df[dim].astype(object))]
    uit = rijen[andere].copy() if andere else pd.DataFrame(index=rijen.index)
    uit["_totaal"] = pd.to_numeric(rijen[kolom], errors="coerce")
    return uit.dropna(subset=["_totaal"])


def _totalen_elders(
    df: pd.DataFrame, df2: pd.DataFrame, meta2: store.KeyMeta | None, kolom: str, dim: str, andere: list[str]
) -> tuple[list[str], pd.DataFrame] | None:
    """De totalen van een andere tabel die bij een groep van `df` passen: (gedeelde dimensies, totalen).

    Heeft de andere tabel `dim`, dan telt alleen haar totaalrij; zonder `dim` is ze een totaal erover. Een dimensie van
    `df` die zij mist, moet in de groep een totaal of overal dezelfde zijn: anders telt zij over meer dan de groep. Een
    eigen dimensie van haar met een totaalrij telt alleen in die rij; zonder totaalrij telt de som (het script dat
    het totaalbestand optelt)."""
    dims2 = _dimensies(df2, meta2)
    rijen = df2
    if dim in df2.columns:
        rijen = df2.loc[_totaalrijen(df2[dim].astype(object))]
        if rijen.empty:
            return None
    for eigen in [d for d in dims2 if d not in andere and d != dim]:
        totaal = _totaalrijen(rijen[eigen].astype(object))
        if totaal.any():
            rijen = rijen.loc[totaal]
    kolommen = [kolom] if kolom in df2.columns else _meetkolommen(df2, dims2)
    if not kolommen or rijen.empty:
        return None
    gedeeld = [d for d in andere if d in dims2]
    waarden = rijen[kolommen].apply(pd.to_numeric, errors="coerce")
    if gedeeld:
        som = waarden.join(rijen[gedeeld]).groupby(gedeeld, dropna=False).sum(min_count=1).reset_index()
    else:
        som = waarden.sum(min_count=1).to_frame().T
    lang = som.melt(id_vars=gedeeld, value_vars=kolommen, value_name="_totaal").drop(columns="variable")
    return gedeeld, lang.dropna(subset=["_totaal"])


def _passend(groepen: pd.DataFrame, df: pd.DataFrame, andere: list[str], gedeeld: list[str]) -> pd.DataFrame:
    """De groepen waarvoor een totaal over `gedeeld` past: elke andere dimensie is daar een totaal of constant."""
    mist = [d for d in andere if d not in gedeeld]
    houd = pd.Series(True, index=groepen.index)
    for d in mist:
        if df[d].nunique(dropna=False) > 1:
            houd &= groepen[d].map(_is_totaal).astype(bool)
    return groepen.loc[houd]


def _uit_paren(paren: pd.DataFrame, key: str, kolom: str, bron: str) -> set[Reconstructie]:
    uit: set[Reconstructie] = set()
    for zichtbaar, totaal, label in paren[["_zichtbaar", "_totaal", "_label"]].itertuples(index=False):
        waarde = round(float(totaal) - float(zichtbaar), _DECIMALEN)
        if _in_bereik(waarde, bron):
            uit.add(Reconstructie(waarde, float(totaal), float(zichtbaar), label, kolom, key))
    return uit


def _van_key(key: str, scope: list[str], constanten: tuple[float, ...]) -> set[Reconstructie]:
    df = store.get(key)
    cellen = duo.sentinel_cells(key)
    if not isinstance(df, pd.DataFrame) or cellen is None or cellen.empty or duo.is_groepstotaal(key):
        return set()
    meta = store.meta(key)
    bron = _bron(key, meta)
    dims = _dimensies(df, meta)
    afgeleid = {k for k in scope if k != key and key in store.bronsleutels(k, met_afgeleid=True)}
    uit: set[Reconstructie] = set()
    for kolom in [str(c) for c in cellen.columns if cellen[c].any() and c in df.columns]:
        onderdrukt = cellen[kolom].astype(bool)
        for dim in dims:
            andere = [d for d in dims if d != dim]
            groepen = _groepen(df, onderdrukt, kolom, dim, andere)
            if groepen.empty:
                continue
            totalen = _totalen_zelfde(df, kolom, dim, andere)
            paren = groepen.merge(totalen, on=andere) if andere else groepen.merge(totalen, how="cross")
            uit |= _uit_paren(paren, key, kolom, bron)
            for k2 in scope:
                if k2 == key or k2 in afgeleid or not isinstance(df2 := store.get(k2), pd.DataFrame):
                    continue
                if (elders := _totalen_elders(df, df2, store.meta(k2), kolom, dim, andere)) is None:
                    continue
                gedeeld, totalen2 = elders
                passend = _passend(groepen, df, andere, gedeeld)
                paren = passend.merge(totalen2, on=gedeeld) if gedeeld else passend.merge(totalen2, how="cross")
                uit |= _uit_paren(paren, key, kolom, bron)
            # Een getal dat het script zelf typte, kan het totaal zijn dat het model eerder las: alleen bij DUO, waar
            # de reconstructie 1-4 is; zonder grens zou elke getypte constante min een deelsom een treffer geven.
            if bron == "duo" and constanten:
                paren = groepen.assign(_sleutel=0).merge(
                    pd.DataFrame({"_totaal": list(constanten), "_sleutel": 0}), on="_sleutel"
                )
                uit |= _uit_paren(paren, key, kolom, bron)
    return uit


# Per scope (de keys met hun tabel en cellen) de uitkomst: elke antwoordcontrole vraagt het opnieuw. De waarde houdt de
# tabellen vast, zodat hun id niet hergebruikt kan worden zolang de sleutel bestaat.
_cache: dict[tuple, tuple[tuple, frozenset[Reconstructie]]] = {}
_CACHE_MAX = 32


def reconstructies(keys: Iterable[str], constanten: Iterable[Any] = ()) -> frozenset[Reconstructie]:
    """Elke onderdrukte cel in (de bronnen van) `keys` die met de totalen in die keys exact terug te rekenen is."""
    scope = _scope(keys)
    getypt = tuple(sorted({float(c) for c in constanten if _is_getal(c)}))
    objecten = tuple((store.get(k), duo.sentinel_cells(k)) for k in scope)
    sleutel = (tuple(scope), tuple((id(df), id(c)) for df, c in objecten), getypt)
    if (bekend := _cache.get(sleutel)) is not None:
        return bekend[1]
    uit = frozenset(r for k in scope for r in _van_key(k, scope, getypt))
    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    _cache[sleutel] = (objecten, uit)
    return uit


def _is_getal(waarde: Any) -> bool:
    return isinstance(waarde, int | float) and not isinstance(waarde, bool) and math.isfinite(waarde)


def getallen(uitkomst: Any) -> list[float]:
    """Elk getal in een uitkomst: losse getallen, in dicts, lijsten, tekst en een Plotly-figuur als dict."""
    if _is_getal(uitkomst):
        return [float(uitkomst)]
    if isinstance(uitkomst, str):
        return [float(n.replace(",", ".")) for n in _GETAL.findall(uitkomst)]
    if isinstance(uitkomst, dict):
        return [g for v in uitkomst.values() for g in getallen(v)]
    if isinstance(uitkomst, list | tuple | set):
        return [g for v in uitkomst for g in getallen(v)]
    if hasattr(uitkomst, "to_json"):
        try:
            return getallen(json.loads(uitkomst.to_json()))
        except (TypeError, ValueError):
            return []
    if hasattr(uitkomst, "item"):
        try:
            return getallen(uitkomst.item())
        except (TypeError, ValueError):
            return []
    return []


def treffers(uitkomst: Any, keys: Iterable[str], constanten: Iterable[Any] = ()) -> list[Reconstructie]:
    """De reconstructies die als getal in `uitkomst` staan."""
    gezocht = reconstructies(keys, constanten)
    if not gezocht:
        return []
    waarden = {round(g, _DECIMALEN) for g in getallen(uitkomst)}
    return [r for r in gezocht if r.waarde in waarden]


def teruggerekend(uitkomst: Any, keys: Iterable[str], constanten: Iterable[Any] = ()) -> bool:
    """Staat er in `uitkomst` een onderdrukte cel, teruggerekend als totaal min de zichtbare delen?"""
    return bool(treffers(uitkomst, keys, constanten))
