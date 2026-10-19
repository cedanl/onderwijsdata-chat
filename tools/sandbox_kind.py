"""Het kindproces van run_analysis: voert één modelgeschreven script uit (#410, #62).

`tools/sandbox.py` start dit bestand met `python -I`, een lege omgeving en een eigen
werkmap. Het leest de invoer (gepickeld, van de server) van stdin en schrijft de
uitkomst als JSON naar stdout; de server ontpickelt nooit iets van dit proces.

Vóór het script draait, sluit het proces zichzelf af:
- resourcelimieten: CPU-tijd, geheugen, geen bestanden schrijven, geen nieuwe processen;
- een audit hook (niet te verwijderen) weigert netwerk, processen, schrijven en elk
  bestand buiten de Python-installatie;
- het script krijgt alleen een handvol builtins en pd, np, math, px, go, df en store_get.

Dit bestand importeert niets uit het project: het draait buiten het projectpad.
"""

import base64
import io
import json
import math
import os
import pickle
import resource
import sys
import traceback
import warnings

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_CPU_SECONDS = 15
_GEHEUGEN_BYTES = 1024**3
# De uitkomst gaat als JSON door een pipe naar de server en door alle antwoordcontroles; een tabel van
# tientallen MB hoort daar niet doorheen (#629). De server kapt de rijen voor het model verder af.
_MAX_UITVOER_TEKENS = 8_000_000
_MAX_FOUT_TEKENS = 400

# Audit-events (prefix) die het script nooit nodig heeft.
_VERBODEN_EVENTS = (
    "socket.",
    "subprocess.",
    "os.system",
    "os.exec",
    "os.posix_spawn",
    "os.spawn",
    "os.fork",
    "os.forkpty",
    "os.kill",
    "os.killpg",
    "os.putenv",
    "os.unsetenv",
    "os.remove",
    "os.rmdir",
    "os.rename",
    "os.mkdir",
    "os.symlink",
    "os.link",
    "os.truncate",
    "os.chmod",
    "os.chown",
    "os.chdir",
    "os.chroot",
    "os.setxattr",
    "os.removexattr",
    "os.utime",
    "shutil.",
    "ctypes.",
    "urllib.",
    "http.",
    "ftplib.",
    "smtplib.",
    "webbrowser.",
    "pty.",
    "mmap.",
    "sqlite3.",
)
# Events met een pad: alleen lezen, en alleen binnen de Python-installatie (lazy imports).
_PAD_EVENTS = ("open", "os.listdir", "os.scandir", "glob.glob")
_SCHRIJVEN = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
_LEESBAAR = tuple(
    os.path.join(os.path.realpath(p), "")
    for p in {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix, "/usr/share/zoneinfo"}
)

_BUILTINS = {
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


class Geweigerd(PermissionError):
    pass


def _schrijft(args: tuple) -> bool:
    mode, flags = (args[1], args[2]) if len(args) >= 3 else (None, 0)
    if isinstance(mode, str):
        return any(c in mode for c in "wax+")
    return bool(isinstance(flags, int) and flags & _SCHRIJVEN)


def _leesbaar(pad) -> bool:
    if pad is None:
        return True  # de eigen, lege werkmap
    if isinstance(pad, int):
        return False
    return os.path.join(os.path.realpath(os.fsdecode(pad)), "").startswith(_LEESBAAR)


def _audit(event: str, args: tuple) -> None:
    if event.startswith(_VERBODEN_EVENTS):
        raise Geweigerd(f"Niet toegestaan in de sandbox: {event}")
    if event in _PAD_EVENTS:
        pad = args[0] if args else None
        if (event == "open" and _schrijft(args)) or not _leesbaar(pad):
            raise Geweigerd(f"Niet toegestaan in de sandbox: {event} {pad!r}")


def _sluit_af() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (_CPU_SECONDS, _CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS, (_GEHEUGEN_BYTES, _GEHEUGEN_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    sys.addaudithook(_audit)


def _standaard(waarde):
    if isinstance(waarde, np.generic):
        return waarde.item()
    return str(waarde)


def _plat(waarde):
    """Plotly's binaire arrays ({'dtype', 'bdata'}) als gewone lijsten: de server leest ze als JSON."""
    if isinstance(waarde, dict):
        if set(waarde) <= {"dtype", "bdata", "shape"} and {"dtype", "bdata"} <= set(waarde):
            array = np.frombuffer(base64.b64decode(waarde["bdata"]), dtype=waarde["dtype"])
            if "shape" in waarde:
                array = array.reshape([int(n) for n in str(waarde["shape"]).split(",")])
            return array.tolist()
        return {k: _plat(v) for k, v in waarde.items()}
    if isinstance(waarde, (list, tuple)):
        return [_plat(v) for v in waarde]
    if isinstance(waarde, np.ndarray):
        return waarde.tolist()
    return waarde


def _fouttekst(code: str) -> str:
    """De fout van het script voor het model: de scriptregels en de laatste regel, geen serverpaden (#629).

    Een volledige traceback loopt door pandas en numpy en noemt de paden van de server; het model heeft de
    regel in zijn eigen script en de foutmelding nodig.
    """
    soort, waarde, spoor = sys.exc_info()
    bron = code.splitlines()
    regels = ["Traceback (most recent call last):"]
    for frame in traceback.extract_tb(spoor):
        if frame.filename != "<analysis>":
            continue
        regels.append(f'  File "<analysis>", line {frame.lineno}, in {frame.name}')
        if frame.lineno and 0 < frame.lineno <= len(bron):
            regels.append(f"    {bron[frame.lineno - 1].strip()}")
    laatste = "".join(traceback.format_exception_only(soort, waarde)).strip()
    if len(laatste) > _MAX_FOUT_TEKENS:
        laatste = laatste[:_MAX_FOUT_TEKENS] + "…"
    regels.append(laatste)
    if isinstance(waarde, FloatingPointError):
        regels.append("De noemer van een deling is 0 (of de waarde is ongeldig); controleer de noemer vóór je deelt.")
    return "\n".join(regels)


def _voer_uit(invoer: dict) -> dict:
    gelezen: list[str] = []
    tabellen = invoer["tabellen"]

    def store_get(key: str):
        gelezen.append(key)
        waarde = tabellen.get(key)
        return waarde.copy() if hasattr(waarde, "copy") else waarde

    namespace = {
        "__builtins__": _BUILTINS,
        "pd": pd,
        "np": np,
        "math": math,
        "px": px,
        "go": go,
        "store_get": store_get,
        "result": None,
        "figure": None,
    }
    if invoer["df"] is not None:
        namespace["df"] = invoer["df"]

    # Een waarschuwing (numpy: deling door nul) doet in de C-code een lazy import, en `__import__` staat niet in
    # de builtins van het script: het script eindigde dan in `KeyError: '__import__'`. Waarschuwingen gaan dus uit
    # en een numpy-deling door nul of een ongeldige waarde is een gewone fout, zoals bij een Python-float (#629).
    # pandas rekent met inf en NaN in een eigen errstate en blijft ongemoeid.
    try:
        with np.errstate(divide="raise", invalid="raise", over="ignore", under="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            exec(compile(invoer["code"], "<analysis>", "exec"), namespace)
    except Exception:
        return {"fout": _fouttekst(invoer["code"])}

    result, figure = namespace["result"], namespace["figure"]
    if isinstance(result, pd.DataFrame):
        result = result.to_dict(orient="records")
    return {
        "result": result,
        "figure": _plat(figure.to_plotly_json()) if isinstance(figure, go.Figure) else None,
        "gelezen": gelezen,
    }


def main() -> None:
    invoer = pickle.load(sys.stdin.buffer)  # van de server, vóór de afsluiting
    uit = sys.stdout
    sys.stdout = io.StringIO()  # wat een library print, hoort niet in de uitkomst
    _sluit_af()
    uitkomst = _voer_uit(invoer)
    try:
        tekst = json.dumps(uitkomst, ensure_ascii=False, default=_standaard)
    except (ValueError, RecursionError):  # o.a. een result dat naar zichzelf verwijst
        tekst = json.dumps({"fout": _fouttekst("")})
    if len(tekst) > _MAX_UITVOER_TEKENS:
        tekst = json.dumps(
            {
                "fout": (
                    f"De uitkomst is te groot ({len(tekst) // 1_000_000} MB; het maximum is {_MAX_UITVOER_TEKENS // 1_000_000} MB). "
                    "Filter, aggregeer of selecteer minder kolommen en geef dat als result."
                )
            }
        )
    uit.write(tekst)
    uit.flush()


if __name__ == "__main__":
    main()
