"""Een rapportgrafiek toont de periode die het rapport noemt (#385).

Het model maakt de grafiek vaak op de volle dataset en schrijft er een titel bij
over vijf jaar: "Aantal mbo-studenten 2020/21-2024/25" boven een as van
2015/16 tot 2025/26. De periode staat in de tekst, de punten op de tijdas: code
legt ze naast elkaar en laat alleen de jaren binnen het bereik staan, ook in de
exportrijen. Een grafiek zonder tijdas, of zonder punt in het bereik, blijft
zoals hij is.
"""

from __future__ import annotations

import json
import re

from tools import periode
from tools.plot import kopruimte

# Een tijdas: jaartal, schooljaar (2021/22, 2021/2022) of CBS-periodecode (2021SJ00, 2021JJ00).
_JAARTAL = re.compile(r"^(20\d{2})$")
_CBS_PERIODE = re.compile(r"^(20\d{2})(?:SJ|JJ)\d{2}$")

# Arrays die per punt een waarde hebben en dus met x mee moeten.
_PER_PUNT = ("x", "y", "text", "hovertext", "customdata")


def startjaar(waarde) -> int | None:
    """Het startjaar van een tijdaswaarde (2021, 2021/22, 2021SJ00); None als het geen jaar is."""
    if isinstance(waarde, bool):
        return None
    if isinstance(waarde, int | float):
        return int(waarde) if float(waarde).is_integer() and 2000 <= waarde < 2100 else None
    tekst = str(waarde).strip()
    if match := _JAARTAL.match(tekst) or _CBS_PERIODE.match(tekst):
        return int(match.group(1))
    jaren = periode.gevraagde_schooljaren(tekst)
    return next(iter(jaren)) if len(jaren) == 1 else None


def _binnen(waarden: list, bereik: tuple[int, int]) -> list[bool] | None:
    """Per waarde: valt hij in het bereik? None als het geen tijdas is."""
    jaren = [j for w in waarden if (j := startjaar(w)) is not None]
    if not jaren or len(jaren) != len(waarden):
        return None
    return [bereik[0] <= j <= bereik[1] for j in jaren]


def bijgesneden(figure_json: str, bereik: tuple[int, int]) -> str:
    """De figuur met alleen de punten binnen `bereik` (startjaren, inclusief)."""
    try:
        figuur = json.loads(figure_json)
    except (TypeError, ValueError):
        return figure_json
    traces = figuur.get("data") or [] if isinstance(figuur, dict) else []
    maskers: list[list[bool]] = []
    for trace in traces:
        masker = _binnen(trace.get("x"), bereik) if isinstance(trace.get("x"), list) else None
        if masker is None:
            return figure_json
        maskers.append(masker)
    if not any(any(m) for m in maskers):
        return figure_json

    for trace, masker in zip(traces, maskers, strict=True):
        for veld in _PER_PUNT:
            if isinstance(trace.get(veld), list) and len(trace[veld]) == len(masker):
                trace[veld] = [w for w, houden in zip(trace[veld], masker, strict=True) if houden]

    meta = figuur.get("layout", {}).get("meta")
    if isinstance(meta, dict) and meta.get("x") and isinstance(meta.get("data"), list):
        meta["data"] = [
            rij for rij in meta["data"] if (j := startjaar(rij.get(meta["x"]))) is None or bereik[0] <= j <= bereik[1]
        ]
    _kopruimte_opnieuw(figuur)
    return json.dumps(figuur, ensure_ascii=False)


def _kopruimte_opnieuw(figuur: dict) -> None:
    """De waardeas van een lijn met labels loopt tot boven het hoogste label (#579); na het bijsnijden
    is dat het hoogste punt dat blijft. Een as zonder die ruimte blijft zoals hij is."""
    as_ = figuur.get("layout", {}).get("yaxis")
    if not (isinstance(as_, dict) and isinstance(opties := as_.get("autorangeoptions"), dict) and "include" in opties):
        return
    kop = kopruimte(figuur.get("data") or [])
    if kop is None:
        del opties["include"]
    else:
        opties["include"] = [kop]


def gevraagd_bereik(*teksten: str) -> tuple[int, int] | None:
    """Het eerste periodebereik dat een van de teksten noemt, in volgorde van voorrang."""
    return next((b for t in teksten if t and (b := periode.genoemd_bereik(t))), None)
