"""run_analysis voert modelgeschreven Python uit in een eigen proces (#410, #62).

Het script draait niet in de server maar in `tools/sandbox_kind.py`, gestart met
dezelfde interpreter (`sys.executable -I`), een lege omgeving (geen secrets) en een
eigen, lege werkmap. Een time-out stopt het proces echt (kill), niet een thread.

De data gaat erheen als pickle (van ons, dus te vertrouwen); de uitkomst komt terug
als JSON, want wat het kindproces schrijft vertrouwen we niet.
"""

import json
import logging
import pickle
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import MAX_SANDBOX_RUNS, SANDBOX_QUEUE_TIMEOUT_S
from core.gelijktijdig import Procesplaatsen
from core.logging_util import tekst_kenmerk

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10
_KIND = Path(__file__).with_name("sandbox_kind.py")
_EEN_DRAAD = dict.fromkeys(("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"), "1")
# Hooguit zoveel kindprocessen tegelijk op de pod (#688); de rest wacht even, daarna een melding voor het model.
_PROCESSEN = Procesplaatsen(max_tegelijk=MAX_SANDBOX_RUNS, wacht_s=SANDBOX_QUEUE_TIMEOUT_S)
BEZET = "De analyseomgeving is nu bezet door andere gebruikers. Probeer het over een minuut opnieuw."


@dataclass(frozen=True)
class Uitkomst:
    result: Any = None
    figure: dict | None = None  # Plotly-figuur als dict
    gelezen: tuple[str, ...] = ()  # de keys die het script via store_get opvroeg
    fout: str | None = None


def voer_uit(code: str, df: pd.DataFrame | None, tabellen: dict[str, Any]) -> Uitkomst:
    """Draai `code` met `df` en (via store_get) alleen `tabellen` in een afgeschermd proces."""
    with _PROCESSEN.plaats() as vrij:
        if not vrij:
            logger.warning("SANDBOX bezet  max=%d  wacht=%ss", MAX_SANDBOX_RUNS, SANDBOX_QUEUE_TIMEOUT_S)
            return Uitkomst(fout=BEZET)
        return _voer_uit(code, df, tabellen)


def _voer_uit(code: str, df: pd.DataFrame | None, tabellen: dict[str, Any]) -> Uitkomst:
    invoer = pickle.dumps({"code": code, "df": df, "tabellen": tabellen}, protocol=pickle.HIGHEST_PROTOCOL)
    with tempfile.TemporaryDirectory(prefix="run_analysis-") as werkmap:
        try:
            proces = subprocess.run(
                [sys.executable, "-I", "-B", str(_KIND)],
                input=invoer,
                capture_output=True,
                timeout=TIMEOUT_SECONDS,
                cwd=werkmap,
                env={"HOME": werkmap, "LANG": "C.UTF-8", **_EEN_DRAAD},
                check=False,
            )
        except subprocess.TimeoutExpired:
            return Uitkomst(fout=f"Script duurde langer dan {TIMEOUT_SECONDS} seconden en is afgebroken.")
    return _lees(proces)


def _log_zonder_uitkomst(proces: subprocess.CompletedProcess) -> None:
    """De stderr van een kindproces dat modelcode draaide, kan die code citeren (#502).

    Op WARNING de returncode en een kenmerk, de staart van stderr alleen op DEBUG.
    """
    stderr = proces.stderr.decode("utf-8", errors="replace")
    logger.warning("sandbox stopte zonder uitkomst (code %s): %s", proces.returncode, tekst_kenmerk(stderr, "stderr_"))
    logger.debug("sandbox stopte zonder uitkomst (code %s), stderr: %s", proces.returncode, stderr[-500:])


def _lees(proces: subprocess.CompletedProcess) -> Uitkomst:
    try:
        uit = json.loads(proces.stdout)
    except ValueError:
        uit = None
    if not isinstance(uit, dict):
        _log_zonder_uitkomst(proces)
        return Uitkomst(fout="Script is afgebroken: het overschreed de geheugen- of tijdslimiet van de sandbox.")
    if uit.get("fout"):
        return Uitkomst(fout=str(uit["fout"]))
    figure = uit.get("figure")
    gelezen = uit.get("gelezen")
    return Uitkomst(
        result=uit.get("result"),
        figure=figure if isinstance(figure, dict) else None,
        gelezen=tuple(k for k in gelezen if isinstance(k, str)) if isinstance(gelezen, list) else (),
    )
