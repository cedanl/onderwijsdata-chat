"""run_analysis: modelgeschreven Python op opgehaalde data, in benoemde stappen (#420).

De tool controleert het script (`scriptcontrole`), draait het in een eigen proces
(`sandbox`), stelt vast welke keys het las (#201), toetst of de uitkomst van de data
afhangt (`afhankelijkheid`, CH-27), bewaart rijen als nieuwe key en bouwt de tekst voor
het model. Elke stap die de analyse kan stoppen, zegt dat met `_Afgebroken`; de melding
is de tekst voor het model.
"""

import hashlib
import json
import logging
import traceback
from dataclasses import dataclass
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from . import afhankelijkheid, cbs_afronding, dekking, fouten, plot, sandbox, scriptcontrole, store

logger = logging.getLogger(__name__)

SCRIPTCONSTANTEN = afhankelijkheid.SCRIPTCONSTANTEN


class _Afgebroken(Exception):
    """De analyse stopt; de tekst is de melding voor het model."""


@dataclass(frozen=True)
class _Run:
    """Eén geslaagde uitvoering: wat het script kreeg, las en opleverde."""

    code: str
    df: pd.DataFrame | None
    tabellen: dict[str, Any]
    result: Any
    figure: go.Figure | None
    bronnen: tuple[str, ...]  # elke gelezen key, in volgorde en zonder dubbelen (#201)
    complete: bool  # rust elke gelezen key op volledige data (#186, #210)


def _analysekey(bronnen: list[str], df: pd.DataFrame) -> str:
    """De key volgt herkomst en inhoud: een identieke run geeft dezelfde key (#62, #47)."""
    # JSON en niet hash_pandas_object: die faalt op een cel met een lijst of dict.
    inhoud = f"{json.dumps(bronnen)}{df.to_json(orient='split', default_handler=str)}"
    return f"analysis:{hashlib.sha256(inhoud.encode()).hexdigest()[:12]}"


def _gecontroleerd(code: str) -> scriptcontrole.Script:
    """De AST-controle vooraf; een weigering of een syntaxfout is de melding voor het model."""
    try:
        return scriptcontrole.ontleed(code)
    except scriptcontrole.Geweigerd as weigering:
        raise _Afgebroken(str(weigering)) from weigering
    except SyntaxError as fout:
        raise _Afgebroken(f"Fout in script:\n{traceback.format_exc(limit=0)}") from fout


def _invoer(data_key: str | None) -> pd.DataFrame | None:
    """De tabel achter `data_key` als kopie (#209); None zonder key."""
    if data_key is None:
        return None
    df = store.readonly(data_key)
    if df is None:
        raise _Afgebroken(fouten.onbekende_key(data_key))
    return df


def _figuur(figure: dict | None) -> go.Figure | None:
    if not figure:
        return None
    try:
        return go.Figure(figure)
    except ValueError as fout:
        raise _Afgebroken(f"Fout in script: de figuur is geen geldige Plotly-figuur ({fout}).") from fout


def _draai(code: str, script: scriptcontrole.Script, data_key: str | None) -> _Run:
    """Het script in de sandbox, met alleen de tabellen die het letterlijk noemt."""
    df = _invoer(data_key)
    tabellen = {k: v for k in script.keys if (v := store.readonly(k)) is not None}
    uitkomst = sandbox.voer_uit(code, df, tabellen)
    if uitkomst.fout:
        raise _Afgebroken(f"Fout in script:\n{uitkomst.fout}")
    figure = _figuur(uitkomst.figure)
    if uitkomst.result is None and figure is None:
        raise _Afgebroken(
            "Script heeft geen 'result' of 'figure' variabele gezet. Wijs je uitkomst toe aan result = ..."
        )
    # Elke key die het script las, via data_key of store_get (#201); het kindproces
    # kan alleen keys melden die het script letterlijk noemde.
    gelezen = [data_key] if data_key is not None else []
    gelezen += [k for k in uitkomst.gelezen if k in script.keys]
    bronnen = tuple(dict.fromkeys(gelezen))
    return _Run(code, df, tabellen, uitkomst.result, figure, bronnen, all(store.volledig(k) for k in bronnen))


def _controle(run: _Run) -> afhankelijkheid.Toets | None:
    """Vóór het opslaan: wat niet van de data afhangt, reist mee met de afgeleide key (#456)."""
    if not run.bronnen:
        return None
    geerfd = tuple(dict.fromkeys(c for k in run.bronnen if (m := store.meta(k)) for c in m.scriptconstanten))
    return afhankelijkheid.toets(run.code, run.df, run.tabellen, run.result, geerfd)


def _bewaar(run: _Run, controle: afhankelijkheid.Toets | None) -> str | None:
    """Rijen als resultaat krijgen een eigen key, afgeleid van de eerste bron; een los getal niet."""
    if not (isinstance(run.result, list) and run.result):
        return None
    store_df = pd.DataFrame(run.result)
    result_key = _analysekey(list(run.bronnen), store_df)
    if not run.bronnen:
        store.put(result_key, store_df)
        return result_key
    store.derive(
        run.bronnen[0],
        result_key,
        store_df,
        stap="eigen berekening (run_analysis)",
        gelezen=run.bronnen,
        scriptconstanten=controle.constanten if controle else (),
        **dekking.van(store_df, store.meta(run.bronnen[0])),
    )
    return result_key


def _tekst(run: _Run, result_key: str | None, controle: afhankelijkheid.Toets | None) -> str:
    """Het toolresultaat voor het model: de uitkomst, waar hij op rust en wat er niet als bewijs telt."""
    text_obj = run.result if run.result is not None else {}
    if result_key:
        text_obj = {"data_key": result_key, "rijen": run.result}
        if not run.complete:
            text_obj["waarschuwing"] = store.ONVOLLEDIG
    if not run.bronnen:
        # Een uitkomst die geen data las is geen bewijs: de getalcontrole telt haar niet mee (#201).
        text_obj = {"bron": None, "resultaat": text_obj}
    elif not result_key:
        # Een los getal heeft geen eigen key; wat het las is zijn selectie, ook voor de onderdrukking (#414).
        text_obj = {"gelezen": list(run.bronnen), "resultaat": text_obj}
    # Op afgeronde CBS-data is een eigen som of verschil niet exacter dan de bron, net als bij compute_kpi (#531).
    if noot := next((n for k in run.bronnen if (n := cbs_afronding.van_key(k))), None):
        text_obj["afronding"] = noot
    if controle and controle.constanten:
        text_obj[SCRIPTCONSTANTEN] = list(controle.constanten)
    if controle and controle.soort == afhankelijkheid.ONBEPAALD:
        text_obj["afhankelijkheid"] = afhankelijkheid.ONBEPAALD_MELDING
    return json.dumps(text_obj, ensure_ascii=False, default=str)


def run_analysis(code: str, data_key: str | None = None) -> str | tuple[str, go.Figure]:
    try:
        run = _draai(code, _gecontroleerd(code), data_key)
    except _Afgebroken as melding:
        return str(melding)
    # Op afgekapte data is een los getal of een samenvatting (len(df) = 50) een
    # telling van de pagina, niet van de bron (#186). Rijen mogen, met melding.
    # Dat geldt voor elke gelezen key, niet alleen voor data_key (#201).
    if not run.complete and run.result is not None and not isinstance(run.result, list):
        return store.ONVOLLEDIG
    controle = _controle(run)
    text = _tekst(run, _bewaar(run, controle), controle)
    if run.figure is None:
        return text
    known = store.meta(run.bronnen[0]) if run.bronnen else None
    return text, plot.leesbare_titels(plot.with_export_rows(run.figure), known)
