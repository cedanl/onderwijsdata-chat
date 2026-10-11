"""Wat er veranderde tussen twee reeksen Plotly-figuren, in gewone taal (#346).

Ververs haalt de data opnieuw op bij de bron; hier wordt de bewaarde grafiek
vergeleken met de verse en worden de gewijzigde waarden benoemd (een CBS-
herziening, een DUO-mutatie). De vergelijking leest beide kanten via plotly
(pio.from_json), zodat ook binair gecodeerde reeksen (bdata) gewoon waarden
zijn. De meldingen zijn voor de gebruiker geschreven: data, geen instructies.
"""

import logging

import plotly.io as pio

from tools.getal import nl_getal

logger = logging.getLogger(__name__)

MAX_MELDINGEN = 8


def figuur_verschillen(oud: list[str], nieuw: list[str]) -> list[str]:
    """De gewijzigde waarden tussen twee reeksen figuur-JSON, als meldingen.

    Leeg betekent: geen zichtbaar verschil. De lijst is begrensd op
    MAX_MELDINGEN; de rest wordt samengevat in een slotregel.
    """
    if oud == nieuw:
        return []
    meldingen: list[str] = []
    for i, (o, n) in enumerate(zip(oud, nieuw, strict=False)):
        if o != n:
            meldingen.extend(_figuur_diff(i, o, n))
    if len(oud) != len(nieuw):
        meldingen.append(f"Het aantal grafieken veranderde van {len(oud)} naar {len(nieuw)}.")
    if len(meldingen) > MAX_MELDINGEN:
        rest = len(meldingen) - MAX_MELDINGEN
        meldingen = [*meldingen[:MAX_MELDINGEN], f"… en nog {rest} andere wijzigingen."]
    return meldingen


def _figuur_diff(index: int, oud_json: str, nieuw_json: str) -> list[str]:
    try:
        oud_fig = pio.from_json(oud_json, skip_invalid=True)
        nieuw_fig = pio.from_json(nieuw_json, skip_invalid=True)
    except Exception:
        logger.debug("Figuur %d is niet te vergelijken", index, exc_info=True)
        return [f"{_naam(None, index)} is gewijzigd."]

    titel = _naam(nieuw_fig, index)
    if len(oud_fig.data) != len(nieuw_fig.data):
        return [f"{titel}: het aantal reeksen veranderde van {len(oud_fig.data)} naar {len(nieuw_fig.data)}."]

    meldingen: list[str] = []
    for oud_trace, nieuw_trace in zip(oud_fig.data, nieuw_fig.data, strict=False):
        meldingen.extend(_reeks_diff(titel, oud_trace, nieuw_trace))
    if not meldingen:
        # Wel andere bytes (bv. opmaak), geen andere waarden: dat is geen datawijziging.
        return []
    return meldingen


def _naam(fig, index: int) -> str:
    tekst = fig.layout.title.text if fig is not None and fig.layout.title else None
    return f"'{tekst}'" if tekst else f"Grafiek {index + 1}"


def _reeks_diff(titel: str, oud_trace, nieuw_trace) -> list[str]:
    """Per categorie (x-waarde of taartlabel) de gewijzigde waarde benoemen."""
    reeks = f", reeks '{nieuw_trace.name}'" if getattr(nieuw_trace, "name", None) else ""
    oud = _waarden(oud_trace)
    nieuw = _waarden(nieuw_trace)

    meldingen = [
        f"{titel}{reeks}, {cat}: {_getal(oud[cat])} → {_getal(nieuw[cat])}"
        for cat in oud
        if cat in nieuw and not _gelijk(oud[cat], nieuw[cat])
    ]
    erbij = [c for c in nieuw if c not in oud]
    weg = [c for c in oud if c not in nieuw]
    if erbij:
        meldingen.append(f"{titel}{reeks}: nieuw in de data: {', '.join(erbij[:3])}")
    if weg:
        meldingen.append(f"{titel}{reeks}: niet meer in de data: {', '.join(weg[:3])}")
    return meldingen


def _waarden(trace) -> dict[str, object]:
    """Categorie → waarde van een reeks: x/y voor staaf en lijn, labels/values voor taart."""
    categorieen = getattr(trace, "labels", None)
    waarden = getattr(trace, "values", None)
    if categorieen is None or waarden is None:
        categorieen = getattr(trace, "x", None)
        waarden = getattr(trace, "y", None)
    if categorieen is None or waarden is None:
        return {}
    return {str(c): w for c, w in zip(_lijst(categorieen), _lijst(waarden), strict=False)}


def _lijst(reeks) -> list:
    return reeks.tolist() if hasattr(reeks, "tolist") else list(reeks)


def _gelijk(a, b) -> bool:
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _getal(waarde) -> str:
    try:
        return nl_getal(float(waarde))
    except (TypeError, ValueError):
        return str(waarde)
