import hashlib
import json
import logging
import traceback

import pandas as pd
import plotly.graph_objects as go

from . import afhankelijkheid, dekking, fouten, plot, sandbox, scriptcontrole, store

logger = logging.getLogger(__name__)

# Getallen die niet van de data afhangen; de getalcontrole telt ze niet als bewijs (#410, CH-27).
SCRIPTCONSTANTEN = "scriptconstanten"


def _analysekey(bronnen: list[str], df: pd.DataFrame) -> str:
    """De key volgt herkomst en inhoud: een identieke run geeft dezelfde key (#62, #47)."""
    # JSON en niet hash_pandas_object: die faalt op een cel met een lijst of dict.
    inhoud = f"{json.dumps(bronnen)}{df.to_json(orient='split', default_handler=str)}"
    return f"analysis:{hashlib.sha256(inhoud.encode()).hexdigest()[:12]}"


def run_analysis(code: str, data_key: str | None = None) -> str | tuple[str, go.Figure]:
    try:
        script = scriptcontrole.ontleed(code)
    except scriptcontrole.Geweigerd as weigering:
        return str(weigering)
    except SyntaxError:
        return f"Fout in script:\n{traceback.format_exc(limit=0)}"

    df = None
    if data_key is not None:
        df = store.readonly(data_key)
        if df is None:
            return fouten.onbekende_key(data_key)

    # De sandbox krijgt alleen de tabellen die het script letterlijk noemt.
    tabellen = {k: v for k in script.keys if (v := store.readonly(k)) is not None}
    uitkomst = sandbox.voer_uit(code, df, tabellen)
    if uitkomst.fout:
        return f"Fout in script:\n{uitkomst.fout}"

    # Elke key die het script las, via data_key of store_get (#201); het kindproces
    # kan alleen keys melden die het script letterlijk noemde.
    gelezen = [data_key] if data_key is not None else []
    gelezen += [k for k in uitkomst.gelezen if k in script.keys]
    result = uitkomst.result
    try:
        figure = go.Figure(uitkomst.figure) if uitkomst.figure else None
    except ValueError as fout:
        return f"Fout in script: de figuur is geen geldige Plotly-figuur ({fout})."

    if result is None and figure is None:
        return "Script heeft geen 'result' of 'figure' variabele gezet. Wijs je uitkomst toe aan result = ..."

    # Op afgekapte data is een los getal of een samenvatting (len(df) = 50) een
    # telling van de pagina, niet van de bron (#186). Rijen mogen, met melding.
    # Dat geldt voor elke gelezen key, niet alleen voor data_key (#201).
    bronnen = list(dict.fromkeys(gelezen))
    complete = all(store.volledig(k) for k in bronnen)
    if not complete and result is not None and not isinstance(result, list):
        return store.ONVOLLEDIG

    result_key = None
    if isinstance(result, list) and result:
        store_df = pd.DataFrame(result)
        result_key = _analysekey(bronnen, store_df)
        if bronnen:
            store.derive(
                bronnen[0],
                result_key,
                store_df,
                stap="eigen berekening (run_analysis)",
                gelezen=tuple(bronnen),
                **dekking.van(store_df, store.meta(bronnen[0])),
            )
        else:
            store.put(result_key, store_df)

    text_obj = result if result is not None else {}
    if result_key:
        text_obj = {"data_key": result_key, "rijen": result}
        if not complete:
            text_obj["waarschuwing"] = store.ONVOLLEDIG
    if not bronnen:
        # Een uitkomst die geen data las is geen bewijs: de getalcontrole telt haar niet mee (#201).
        text_obj = {"bron": None, "resultaat": text_obj}
    elif not result_key:
        # Een los getal heeft geen eigen key; wat het las is zijn selectie, ook voor de onderdrukking (#414).
        text_obj = {"gelezen": bronnen, "resultaat": text_obj}
    if bronnen and (eigen := afhankelijkheid.onafhankelijke_getallen(code, df, tabellen, result)):
        text_obj[SCRIPTCONSTANTEN] = list(eigen)
    text = json.dumps(text_obj, ensure_ascii=False, default=str)

    if isinstance(figure, go.Figure):
        known = store.meta(bronnen[0]) if bronnen else None
        return text, plot.leesbare_titels(plot.with_export_rows(figure), known)
    return text
