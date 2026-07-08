import json
import re
import signal
import traceback

import math
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import store

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


def _check_code(code: str) -> str | None:
    match = _BLOCKED_PATTERNS.search(code)
    if match:
        return f"Niet toegestaan in analyse-scripts: '{match.group()}'. Gebruik de beschikbare libraries (pd, np, px, go)."
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

    def _timeout_handler(signum, frame):
        raise TimeoutError("Script duurde langer dan 10 seconden.")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    try:
        signal.alarm(_TIMEOUT_SECONDS)
        exec(compile(code, "<analysis>", "exec"), namespace)
        signal.alarm(0)
    except Exception:
        signal.alarm(0)
        return f"Fout in script:\n{traceback.format_exc()}"
    finally:
        signal.signal(signal.SIGALRM, old_handler)

    result = namespace["result"]
    figure = namespace["figure"]

    if result is None and figure is None:
        return "Script heeft geen 'result' of 'figure' variabele gezet. Wijs je uitkomst toe aan result = ..."

    if isinstance(result, pd.DataFrame):
        result = result.to_dict(orient="records")

    text = json.dumps(result, ensure_ascii=False, default=str) if result is not None else "{}"

    if isinstance(figure, go.Figure):
        return text, figure
    return text
