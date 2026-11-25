"""Eerlijke grafiekregels voor elke figuur: create_plot en een eigen figuur uit run_analysis (#1264).

create_plot tekende staven al vanaf nul en zette op een afgekapte lijnas de titel "as begint niet bij 0" (#871), maar
een eigen figuur ging er buitenom: een staafgrafiek met `yaxis.range=[100, 200]` of een tweede y-as kwam zo in de chat.
Eén controle in code, na `leesbare_titels`:

- staven: de waardeas heeft nul erin; een andere range wordt gecorrigeerd, met een noot;
- geen tweede y-as op hetzelfde plotvlak (`overlaying`, of een as die het vlak van een andere deelt): zo'n figuur wordt
  geweigerd met `TWEE_ASSEN`; twee figuren, of subplots onder elkaar, mogen wel;
- een lijn met een as die niet bij nul begint, krijgt de afgekapte-astitel;
- `barmode="overlay"` alleen met doorschijnende staven, anders `group`.

Kaarten en sankey hebben geen waardeas en vallen erbuiten.
"""

import math
import re

import plotly.graph_objects as go

# Dezelfde tekst als tools/plot.py (#871); hier, zodat plot.py deze module kan importeren zonder kring.
AS_NIET_BIJ_NUL = "as begint niet bij 0"

TWEE_ASSEN = (
    "Geen grafiek gemaakt: deze figuur heeft een tweede y-as op hetzelfde plotvlak (yaxis2 of overlaying). Twee maten "
    "op twee assen suggereren een verband dat alleen uit de schaalkeuze komt. Maak twee grafieken naast elkaar: twee "
    "figuren, of één figuur met subplots onder elkaar (make_subplots(rows=2, cols=1, shared_xaxes=True))."
)

NOOT_NUL = "De waardeas van de staven is gecorrigeerd zodat ze bij 0 begint: een staaf toont een hoeveelheid vanaf nul."
NOOT_OVERLAY = "De staven staan naast elkaar in plaats van over elkaar: over elkaar verborgen ze elkaar."

_YAS = re.compile(r"^yaxis(\d*)$")
_STAAFTYPES = ("bar", "histogram")


class TweeAssen(ValueError):
    """De figuur heeft twee y-assen op één plotvlak; de melding is `TWEE_ASSEN`."""

    def __init__(self) -> None:
        super().__init__(TWEE_ASSEN)


def _asnaam(ref: str | None, letter: str) -> str:
    """'y2' → 'yaxis2', None of 'y' → 'yaxis'."""
    ref = ref or letter
    return f"{letter}axis{ref[1:]}"


def _domein(as_: dict) -> tuple[float, float]:
    domein = as_.get("domain") or [0, 1]
    return float(domein[0]), float(domein[1])


def _overlapt(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _y_assen(fig: go.Figure, layout: dict) -> list[str]:
    """Elke y-as van de figuur: die in de layout en die een spoor gebruikt."""
    namen = [k for k in layout if _YAS.match(k)]
    namen += [_asnaam(getattr(t, "yaxis", None), "y") for t in fig.data if hasattr(t, "yaxis")]
    return list(dict.fromkeys(namen))


def _plotvlak(layout: dict, yas: str) -> tuple[tuple[float, float], tuple[float, float]]:
    """(x-domein van de x-as waaraan deze y-as hangt, y-domein)."""
    as_ = layout.get(yas) or {}
    anker = as_.get("anchor")
    xas = _asnaam(anker if isinstance(anker, str) and anker.startswith("x") else None, "x")
    return _domein(layout.get(xas) or {}), _domein(as_)


def twee_y_assen(fig: go.Figure) -> bool:
    """Heeft de figuur twee y-assen op hetzelfde plotvlak? Subplots onder of naast elkaar niet."""
    layout = fig.layout.to_plotly_json()
    assen = _y_assen(fig, layout)
    if any((layout.get(a) or {}).get("overlaying") for a in assen):
        return True
    vlakken = [_plotvlak(layout, a) for a in assen]
    return any(_overlapt(a[0], b[0]) and _overlapt(a[1], b[1]) for i, a in enumerate(vlakken) for b in vlakken[i + 1 :])


def _getallen(waarden) -> list[float]:
    return [
        float(v)
        for v in (waarden if waarden is not None else ())
        if isinstance(v, int | float) and not isinstance(v, bool) and not math.isnan(v)
    ]


def _waardeas(trace) -> str:
    """De as met de waarden van een spoor: x bij liggende staven, anders y."""
    if trace.type in _STAAFTYPES and getattr(trace, "orientation", None) == "h":
        return _asnaam(trace.xaxis, "x")
    return _asnaam(trace.yaxis, "y")


def _waarden(trace) -> list[float]:
    liggend = trace.type in _STAAFTYPES and getattr(trace, "orientation", None) == "h"
    return _getallen(trace.x if liggend else trace.y)


def _is_lijn(trace) -> bool:
    if trace.type != "scatter":
        return False
    modus = trace.mode
    return modus is None or "lines" in modus


def _range(as_: dict) -> list[float] | None:
    bereik = as_.get("range")
    if not isinstance(bereik, list | tuple) or len(bereik) != 2:
        return None
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in bereik):
        return None
    return [float(bereik[0]), float(bereik[1])]


def staven_vanaf_nul(fig: go.Figure) -> bool:
    """Zet elke waardeas van staven met een range zonder nul op een range met nul. True als er iets veranderde."""
    layout = fig.layout.to_plotly_json()
    veranderd = False
    for as_naam in dict.fromkeys(_waardeas(t) for t in fig.data if t.type == "bar"):
        bereik = _range(layout.get(as_naam) or {})
        if bereik is None:
            continue
        laag, hoog = min(bereik), max(bereik)
        if laag <= 0 <= hoog:
            continue
        nieuw = [min(laag, 0.0), max(hoog, 0.0)]
        fig.update_layout({as_naam: {"range": nieuw if bereik[0] <= bereik[1] else nieuw[::-1], "autorange": False}})
        veranderd = True
    return veranderd


def _titel(as_: dict) -> str:
    titel = as_.get("title")
    if isinstance(titel, dict):
        return str(titel.get("text") or "")
    return str(titel or "")


def lijn_afgekapt(fig: go.Figure, as_naam: str) -> bool:
    """Begint de waardeas van de lijnen op deze as niet bij 0? Een range zonder nul, of een vrije as boven nul."""
    layout = fig.layout.to_plotly_json()
    as_ = layout.get(as_naam) or {}
    if (bereik := _range(as_)) is not None:
        return not min(bereik) <= 0 <= max(bereik)
    if as_.get("rangemode") in ("tozero", "nonnegative"):
        return False
    waarden = [v for t in fig.data if _is_lijn(t) and _waardeas(t) == as_naam for v in _waarden(t)]
    return bool(waarden) and (min(waarden) > 0 or max(waarden) < 0)


def afgekapte_lijnen_titel(fig: go.Figure) -> None:
    """Een lijn met een as die niet bij 0 begint, krijgt dat op de as: de titel met "(as begint niet bij 0)"."""
    layout = fig.layout.to_plotly_json()
    for as_naam in dict.fromkeys(_waardeas(t) for t in fig.data if _is_lijn(t)):
        titel = _titel(layout.get(as_naam) or {})
        if AS_NIET_BIJ_NUL in titel or not lijn_afgekapt(fig, as_naam):
            continue
        tekst = f"{titel}<br>({AS_NIET_BIJ_NUL})" if titel else f"({AS_NIET_BIJ_NUL})"
        fig.update_layout({as_naam: {"title": {"text": tekst}}})


def _doorschijnend(trace) -> bool:
    for dekking in (trace.opacity, getattr(trace.marker, "opacity", None)):
        if isinstance(dekking, int | float) and not isinstance(dekking, bool) and dekking < 1:
            return True
    return False


def overlay_doorschijnend(fig: go.Figure) -> bool:
    """`barmode="overlay"` met dekkende staven wordt `group`. True als er iets veranderde."""
    staven = [t for t in fig.data if t.type in _STAAFTYPES]
    if fig.layout.barmode != "overlay" or len(staven) < 2 or all(_doorschijnend(t) for t in staven):
        return False
    fig.update_layout(barmode="group")
    return True


def controleer(fig: go.Figure) -> list[str]:
    """Pas de regels toe op `fig` (in place) en geef de noten over wat er veranderde.

    Raises TweeAssen bij een tweede y-as op hetzelfde plotvlak: die figuur gaat niet naar de chat."""
    if twee_y_assen(fig):
        raise TweeAssen()
    noten = []
    if staven_vanaf_nul(fig):
        noten.append(NOOT_NUL)
    if overlay_doorschijnend(fig):
        noten.append(NOOT_OVERLAY)
    afgekapte_lijnen_titel(fig)
    return noten


def overtredingen(fig: go.Figure) -> list[str]:
    """Wat er aan een figuur niet volgens de regels is, zonder iets te veranderen: voor tests en het log."""
    fouten = []
    if twee_y_assen(fig):
        fouten.append("twee y-assen")
    layout = fig.layout.to_plotly_json()
    for as_naam in dict.fromkeys(_waardeas(t) for t in fig.data if t.type == "bar"):
        bereik = _range(layout.get(as_naam) or {})
        if bereik is not None and not min(bereik) <= 0 <= max(bereik):
            fouten.append(f"staven zonder nul op {as_naam}")
    fouten += [
        f"afgekapte lijnas zonder titel op {as_naam}"
        for as_naam in dict.fromkeys(_waardeas(t) for t in fig.data if _is_lijn(t))
        if lijn_afgekapt(fig, as_naam) and AS_NIET_BIJ_NUL not in _titel(layout.get(as_naam) or {})
    ]
    staven = [t for t in fig.data if t.type in _STAAFTYPES]
    if layout.get("barmode") == "overlay" and len(staven) > 1 and not all(_doorschijnend(t) for t in staven):
        fouten.append("overlay met dekkende staven")
    return fouten
