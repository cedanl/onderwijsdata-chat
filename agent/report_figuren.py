"""De figuren uit het gesprek in het rapport: opnieuw gemaakt op de server, niet gekopieerd (#993).

Wat de gebruiker in de chat zag, komt in het rapport. Het rapportmodel tekent zelf geen figuren (besluit 18-11): het
rapport bevat precies de figuren die de gebruiker in de checklist koos (`rapportselectie.kies`). Elke gekozen figuur
ontstaat opnieuw uit haar stap (`agent.figuurstappen`): de `create_plot`- of kaartaanroep met haar argumenten, of het
script van `run_analysis` met zijn `data_key`, via `tools.dispatch` op de data die `herstel_data` terugzette. Zo
gelden dezelfde controles en dezelfde sandbox als in de chat. De figuur-JSON van het opgeslagen gesprek komt van de
client en wordt nooit gelezen.

Een stap die niet meer lukt (data weg, een fout in het script, een lege figuur) valt weg met een vaste regel in het
voorbehoud (`NIET_OPNIEUW`); het rapport wordt daarom niet geweigerd.

Het model krijgt elke vaste figuur als beschrijving uit code (`beschrijf`): titel, soort, reeksen of knopen en
waarden. De waarden zijn bewijs voor de controles van het rapport; de titel is tekst van het model in de chat en is
dat niet (#211). Net als bij een toolresultaat telt een getal dat niet van de data afhangt niet (#410, CH-27), en
bewijst een figuur zonder bron niets (#201).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass

import numpy as np
import plotly.io as pio

from core.errors import log_interne_fout
from tools import analysis, dispatch, fouten, store
from tools.afhankelijkheid import SCRIPTCONSTANTEN
from tools.schemas import TOOL_RUN_ANALYSIS

from . import figuurstappen, grounding
from .rapportselectie import MAX_FIGUREN
from .selectie import stapkeys

logger = logging.getLogger(__name__)

NIET_OPNIEUW = "Deze figuur uit het gesprek kon niet opnieuw gemaakt worden."

# Zoveel punten per reeks en reeksen per figuur noemt de beschrijving; de rest staat er als aantal.
_MAX_PUNTEN = 60
_MAX_REEKSEN = 10
# Zo lang wordt een naam of label in de beschrijving: het is tekst uit de chat (het script of de data).
_MAX_LABEL = 80


@dataclass(frozen=True)
class VasteFiguur:
    """Een figuur uit het gesprek, opnieuw gemaakt: wat het rapport toont en wat de controles als bewijs lezen."""

    figure_json: str
    data_key: str  # waar de bronregel en de periode van komen (#569, #893)
    keys: tuple[str, ...]  # wat de stap las en maakte: de gebruikte datasets van het rapport (#738)
    bewijs: tuple[str, ...]  # elk als eigen toolresultaat voor de getalcontrole: zie `_bewijs`
    beschrijving: str  # voor de prompt, met titel
    indeling: str | None = None  # "per sector (DUO)" uit layout.meta, voor de bronregel (#1232)


@dataclass(frozen=True)
class VasteFiguren:
    figuren: tuple[VasteFiguur, ...] = ()
    mislukt: int = 0

    @property
    def voorbehoud(self) -> list[str]:
        """De regel voor het voorbehoud van het rapport, één per figuur die niet terugkwam."""
        return [NIET_OPNIEUW] * self.mislukt


async def maak_figuren(session: dict, ids: tuple[str, ...], stop_event: asyncio.Event | None = None) -> VasteFiguren:
    """De gekozen figuren, opnieuw gemaakt in de volgorde van het gesprek; hoogstens `MAX_FIGUREN`.

    Een id zonder stap in deze sessie telt als mislukt, net als een stap die niet opnieuw lukt. Na een stop begint
    geen volgende figuur meer; wie `stop_event` meegaf, kijkt daarna zelf of het rapport doorgaat.
    """
    if not ids:
        return VasteFiguren()
    gekozen = [s for s in figuurstappen.stappen(session) if s["id"] in ids][:MAX_FIGUREN]
    # Na elkaar, niet tegelijk: een script draait in de sandbox, en een rapport zet er hoogstens vier in gang.
    gemaakt = []
    for stap in gekozen:
        if stop_event is not None and stop_event.is_set():
            break
        gemaakt.append(await asyncio.to_thread(_opnieuw, stap))
    figuren = [f for f in gemaakt if f is not None]
    mislukt = min(len(ids), MAX_FIGUREN) - len(figuren)
    logger.info("RAPPORT vaste figuren  gekozen=%d  gemaakt=%d  mislukt=%d", len(ids), len(figuren), mislukt)
    return VasteFiguren(tuple(figuren), mislukt)


def _opnieuw(stap: dict) -> VasteFiguur | None:
    """De figuur van een stap, opnieuw uitgevoerd; None als dat niet lukt."""
    if stap.get("tool") not in figuurstappen.FIGUURTOOLS:
        # Alleen de server schrijft stappen, en alleen van figuurtools: een andere tool draait het rapport nooit.
        logger.warning("RAPPORT vaste figuur  mislukt=geen figuurtool")
        return None
    try:
        return _maak(stap)
    except Exception as e:  # een figuur die niet terugkomt, valt weg; het rapport gaat door
        # De fouttekst kan modeltekst of argumenten citeren (#502): op WARNING alleen het fout-ID, de rest op DEBUG.
        logger.warning("RAPPORT vaste figuur  tool=%s  mislukt=uitzondering", stap["tool"])
        log_interne_fout(e, "rapportfiguur")
        return None


def _maak(stap: dict) -> VasteFiguur | None:
    result, figure = dispatch(stap["tool"], dict(stap["arguments"]))
    if figure is None or fouten.code(result) is not None or not _heeft_waarden(figure):
        logger.warning("RAPPORT vaste figuur  tool=%s  mislukt=%s", stap["tool"], fouten.code(result) or "geen")
        return None
    return VasteFiguur(
        figure_json=pio.to_json(figure),
        data_key=stap["keys"][0],
        keys=tuple(dict.fromkeys([*stap["keys"], *stapkeys(result)])),
        bewijs=_bewijs(stap, result, figure),
        beschrijving=beschrijf(figure),
        indeling=_indeling(figure),
    )


def _indeling(figure) -> str | None:
    """De indeling die create_plot in layout.meta zette (#1232); None bij een figuur zonder."""
    meta = figure.layout.meta
    waarde = meta.get("indeling") if isinstance(meta, dict) else None
    return waarde if isinstance(waarde, str) and waarde else None


def _bewijs(stap: dict, result: str, figure) -> tuple[str, ...]:
    """Wat de controles van het rapport als bewijs lezen, elk als eigen toolresultaat (`agent/grounding.py`).

    Bij een script zijn uitkomst, zoals in de chat (#397); de melding van een grafiektool herhaalt alleen de titel van
    het model (#211). Daarnaast de waarden van de figuur zonder titels, zonder de getallen die niet van de data
    afhangen (#410, CH-27): bij een script gemeten op verstoorde invoer (`analysis.figuurtoets`), want het kan een getal
    ook alleen in zijn figuur typen; bij een grafiek of kaart wat haar key al zo meedroeg. Een figuur zonder bron
    bewijst niets (#201): een script dat geen data las, of een key waarvan de herkomst onbekend is.
    """
    argumenten = stap["arguments"]
    if stap["tool"] == TOOL_RUN_ANALYSIS:
        if grounding.bronloos(result):
            return ()
        toets = analysis.figuurtoets(argumenten["code"], argumenten.get("data_key"), figure, _waarden)
        return (result, _figuurbewijs(figure, toets.constanten))
    known = store.meta(store.canoniek(argumenten.get("data_key") or ""))
    return () if known is None else (_figuurbewijs(figure, known.scriptconstanten),)


def _waarden(figure) -> str:
    """De waarden van een figuur zonder titels; leeg zonder figuur."""
    return beschrijf(figure, met_titel=False) if figure is not None else ""


def _figuurbewijs(figure, constanten) -> str:
    """De waarden van een figuur in de vorm van een toolresultaat: de getalcontrole telt `constanten` niet mee."""
    return json.dumps({"figuur": _waarden(figure), SCRIPTCONSTANTEN: list(constanten)}, ensure_ascii=False)


def _heeft_waarden(figure) -> bool:
    return any(waarden for trace in figure.data for _, waarden in _reeks(trace))


def beschrijf(figure, met_titel: bool = True) -> str:
    """De figuur in woorden uit code: titel, per reeks de soort, de naam en de waarden; bij een sankey knopen en
    stromen. `met_titel=False` laat de titels (van het model in de chat) weg: dat is het bewijs voor de controles."""
    regels: list[str] = []
    if met_titel:
        regels.append(f"Titel: {figuurstappen.titel(figure) or 'geen'}")
    for trace in list(figure.data)[:_MAX_REEKSEN]:
        regels.extend(_beschrijf_reeks(trace, met_titel))
    if len(figure.data) > _MAX_REEKSEN:
        regels.append(f"(nog {len(figure.data) - _MAX_REEKSEN} reeksen)")
    return "\n".join(regels)


def _beschrijf_reeks(trace, met_naam: bool) -> list[str]:
    soort = trace.type or "onbekend"
    if soort == "sankey":
        return _beschrijf_sankey(trace)
    naam = f" '{_label(trace.name)}'" if met_naam and getattr(trace, "name", None) else ""
    regels = [f"Reeks{naam} ({soort}):"]
    for labels, waarden in _reeks(trace):
        punten = [f"{_label(label)}: {_getal(w)}" for label, w in zip(labels, waarden, strict=False)]
        regels.append("  " + "; ".join(punten[:_MAX_PUNTEN]) + _rest(len(punten)))
    return regels


def _beschrijf_sankey(trace) -> list[str]:
    knopen = [_label(k) for k in _lijst(trace.node.label)]
    bronnen, doelen, waarden = (_lijst(getattr(trace.link, veld)) for veld in ("source", "target", "value"))

    def knoop(i) -> str:
        return knopen[int(i)] if isinstance(i, int | float) and 0 <= int(i) < len(knopen) else _label(i)

    stromen = [f"{knoop(b)} → {knoop(d)}: {_getal(w)}" for b, d, w in zip(bronnen, doelen, waarden, strict=False)]
    return [
        "Reeks (sankey):",
        f"  Knopen: {'; '.join(knopen[:_MAX_PUNTEN])}{_rest(len(knopen))}",
        f"  Stromen: {'; '.join(stromen[:_MAX_PUNTEN])}{_rest(len(stromen))}",
    ]


def _reeks(trace) -> list[tuple[list, list]]:
    """(labels, waarden) van een reeks: x/y (liggend: y/x), labels/values, locaties/z, of de stromen van een sankey."""
    if trace.type == "sankey":
        return [([], _lijst(trace.link.value))]
    for labels, waarden in (("labels", "values"), ("locations", "z")):
        if w := _lijst(getattr(trace, waarden, None)):
            return [(_lijst(getattr(trace, labels, None)) or list(range(1, len(w) + 1)), w)]
    x, y = (_lijst(getattr(trace, a, None)) for a in ("x", "y"))
    if getattr(trace, "orientation", None) == "h":
        x, y = y, x
    if y:
        return [(x or list(range(1, len(y) + 1)), y)]
    return [(list(range(1, len(x) + 1)), x)] if x else []


def _lijst(waarde) -> list:
    """Een array uit een Plotly-figuur als lijst: tuple, numpy-array of de base64-vorm van Plotly 6+ (`bdata`)."""
    if waarde is None:
        return []
    if isinstance(waarde, dict) and isinstance(waarde.get("bdata"), str):
        try:
            return np.frombuffer(base64.b64decode(waarde["bdata"]), dtype=waarde.get("dtype", "f8")).tolist()
        except (TypeError, ValueError):
            return []
    if isinstance(waarde, np.ndarray):
        return waarde.ravel().tolist()
    if isinstance(waarde, list | tuple):
        return list(waarde)
    return []


def _getal(waarde) -> str:
    if isinstance(waarde, bool) or not isinstance(waarde, int | float):
        return _tekst(waarde)
    if isinstance(waarde, float) and waarde.is_integer():
        return str(int(waarde))
    return str(round(waarde, 4)) if isinstance(waarde, float) else str(waarde)


def _tekst(waarde) -> str:
    return " ".join(str(waarde).split())


def _label(waarde) -> str:
    """Een naam of label op één regel, hoogstens `_MAX_LABEL` tekens."""
    tekst = _tekst(waarde)
    return tekst if len(tekst) <= _MAX_LABEL else tekst[: _MAX_LABEL - 1] + "…"


def _rest(aantal: int) -> str:
    return f" (en nog {aantal - _MAX_PUNTEN})" if aantal > _MAX_PUNTEN else ""
