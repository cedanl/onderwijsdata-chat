import ast
import ctypes
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

from . import dekking, store

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
    "len": len, "range": range, "sorted": sorted,
    "list": list, "dict": dict, "tuple": tuple, "set": set,
    "str": str, "int": int, "float": float, "bool": bool,
    "zip": zip, "enumerate": enumerate,
    "min": min, "max": max, "sum": sum, "round": round, "abs": abs,
    "isinstance": isinstance, "type": type,
    "True": True, "False": False, "None": None,
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
            nums = [
                n for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            ]
            if len(nums) >= 6:
                return (
                    "Script bevat een literal datastructuur met ≥6 getallen. "
                    "Dit ziet eruit als overgetypte data. Lees data via df of store_get(key)."
                )
    return None


def _check_code(code: str) -> str | None:
    # Check regex blocklist (security)
    match = _BLOCKED_PATTERNS.search(code)
    if match:
        return f"Niet toegestaan in analyse-scripts: '{match.group()}'. Gebruik de beschikbare libraries (pd, np, px, go)."

    # Check data sourcing (data integrity): reject hardcoded data
    if err := _check_no_hardcoded_data(code):
        return err

    return None


def run_analysis(code: str, data_key: str | None = None) -> str | tuple[str, go.Figure]:
    violation = _check_code(code)
    if violation:
        return violation

    namespace = {
        "__builtins__": _SAFE_BUILTINS,
        "pd": pd,
        "np": np,
        "math": math,
        "px": px,
        "go": go,
        "store_get": lambda key: store.get(key),
        "result": None,
        "figure": None,
    }

    if data_key is not None:
        df = store.get(data_key)
        if df is None:
            available = store.list_keys()
            hint = f" Beschikbaar: {available}" if available else ""
            return f"Geen data gevonden voor '{data_key}'.{hint}"
        namespace["df"] = df.copy()

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
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(tid), ctypes.py_object(SystemExit)
            )
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
    complete = data_key is None or store.volledig(data_key)
    if not complete and result is not None and not isinstance(result, list):
        return store.ONVOLLEDIG

    result_key = None
    if isinstance(result, list) and result:
        store_df = pd.DataFrame(result)
        result_key = f"analysis:{id(store_df)}"
        if data_key is not None:
            store.derive(data_key, result_key, store_df, **dekking.van(store_df, store.meta(data_key)))
        else:
            store.put(result_key, store_df)

    text_obj = result if result is not None else {}
    if result_key:
        text_obj = {"data_key": result_key, "rijen": result}
        if not complete:
            text_obj["waarschuwing"] = store.ONVOLLEDIG
    text = json.dumps(text_obj, ensure_ascii=False, default=str)

    if isinstance(figure, go.Figure):
        return text, figure
    return text
