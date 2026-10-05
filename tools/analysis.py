import ast
import ctypes
import hashlib
import json
import logging
import math
import re
import threading
import traceback

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import dekking, fouten, plot, store

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10

_BLOCKED_PATTERNS = re.compile(
    r"\b("
    r"import|__import__|"
    r"exec|eval|compile|"
    r"open|"
    r"os\.|sys\.|subprocess|"
    r"__builtins__|__class__|__subclasses__|"
    r"globals|locals|"
    r"getattr|setattr|delattr|"
    r"breakpoint"
    r")\b"
)

_SAFE_BUILTINS = {
    "len": len,
    "range": range,
    "sorted": sorted,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "zip": zip,
    "enumerate": enumerate,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "abs": abs,
    "isinstance": isinstance,
    "type": type,
    "True": True,
    "False": False,
    "None": None,
    "print": lambda *a, **kw: None,
}


def _check_no_hardcoded_data(code: str) -> str | None:
    """Detect hardcoded data structures (likely copy-pasted rows)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None  # Syntaxfout wordt later gerapporteerd

    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Dict, ast.Tuple)):
            # Count numeric constants in this structure
            nums = [n for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))]
            if len(nums) >= 6:
                return (
                    "Script bevat een literal datastructuur met ≥6 getallen. "
                    "Dit ziet eruit als overgetypte data. Lees data via df of store_get(key)."
                )
    return None


def _check_reads_data(code: str) -> str | None:
    """Een script dat geen data leest, rekent niet op data (#11)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    if not any(isinstance(n, ast.Name) and n.id in ("df", "store_get") for n in ast.walk(tree)):
        return "Script leest geen data. Lees data via `df` of `store_get(key)`; typ nooit data over."
    return None


def _check_code(code: str) -> str | None:
    # Check regex blocklist (security)
    match = _BLOCKED_PATTERNS.search(code)
    if match:
        return (
            f"Niet toegestaan in analyse-scripts: '{match.group()}'. Gebruik de beschikbare libraries (pd, np, px, go)."
        )

    # Check data sourcing (data integrity): reject hardcoded data
    if err := _check_no_hardcoded_data(code):
        return err
    return _check_reads_data(code)


def _analysekey(bronnen: list[str], df: pd.DataFrame) -> str:
    """De key volgt herkomst en inhoud: een identieke run geeft dezelfde key (#62, #47)."""
    # JSON en niet hash_pandas_object: die faalt op een cel met een lijst of dict.
    inhoud = f"{json.dumps(bronnen)}{df.to_json(orient='split', default_handler=str)}"
    return f"analysis:{hashlib.sha256(inhoud.encode()).hexdigest()[:12]}"


def run_analysis(code: str, data_key: str | None = None) -> str | tuple[str, go.Figure]:
    violation = _check_code(code)
    if violation:
        return violation

    gelezen: list[str] = []  # elke key die het script las, via data_key of store_get (#201)

    def store_get(key: str):
        gelezen.append(key)
        return store.readonly(key)

    namespace = {
        "__builtins__": _SAFE_BUILTINS,
        "pd": pd,
        "np": np,
        "math": math,
        "px": px,
        "go": go,
        "store_get": store_get,
        "result": None,
        "figure": None,
    }

    if data_key is not None:
        df = store.get(data_key)
        if df is None:
            return fouten.onbekende_key(data_key)
        namespace["df"] = df.copy()
        gelezen.append(data_key)

    exc_result: list = [None]

    def _target():
        try:
            exec(compile(code, "<analysis>", "exec"), namespace)
        except Exception:
            exc_result[0] = traceback.format_exc()

    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    worker.join(timeout=_TIMEOUT_SECONDS)

    if worker.is_alive():
        # Forceer stop via async exception — best-effort, daemon thread wordt opgeruimd bij exit
        tid = worker.ident
        if tid is not None:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), ctypes.py_object(SystemExit))
        return f"Script duurde langer dan {_TIMEOUT_SECONDS} seconden en is afgebroken."

    if exc_result[0]:
        return f"Fout in script:\n{exc_result[0]}"

    result = namespace["result"]
    figure = namespace["figure"]

    if result is None and figure is None:
        return "Script heeft geen 'result' of 'figure' variabele gezet. Wijs je uitkomst toe aan result = ..."

    if isinstance(result, pd.DataFrame):
        result = result.to_dict(orient="records")

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
    text = json.dumps(text_obj, ensure_ascii=False, default=str)

    if isinstance(figure, go.Figure):
        return text, plot.with_export_rows(figure)
    return text
