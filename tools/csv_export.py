"""CSV van de tabel achter een antwoord, voor Excel (#269).

De export is de tabel die query_data of run_analysis in de store legde, niet de
tabel die het model in zijn antwoord overschreef. Puntkomma en decimale komma,
zoals Nederlandse Excel ze verwacht; wat de tabel over zichzelf moet zeggen
(bron, selecties, afkap, onderdrukte cellen) staat als '#'-regels erboven,
zoals bij de grafiekexport (#118). Data die na een herstart opnieuw bij de bron
is opgehaald zegt dat bovenaan: de cijfers kunnen afwijken van het antwoord (#472).
"""

import csv
import io
import json

import pandas as pd

from . import duo, herlaad, store
from .schemas import TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS

_EXPORTEERBAAR = {TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS}


def export_key(name: str, result: str) -> str | None:
    """De key van de tabel die deze stap opleverde, of None als er niets te exporteren is."""
    if name not in _EXPORTEERBAAR:
        return None
    try:
        parsed = json.loads(result)
    except ValueError:
        return None
    # run_analysis zonder bron verpakt zijn uitkomst onder 'resultaat': geen tabel uit de bron (#201).
    if not isinstance(parsed, dict) or not parsed.get("rijen"):
        return None
    key = parsed.get("data_key")
    return key if isinstance(key, str) else None


def _cel(v, afronden: bool) -> str:
    v = duo.json_waarde(v, afronden)
    if v is None or v is pd.NaT:
        return ""
    if isinstance(v, float):
        return repr(v).replace(".", ",")
    if isinstance(v, pd.Timestamp):
        return v.strftime("%d-%m-%Y")
    return str(v)


def _noten(key: str, afronden: bool) -> list[str]:
    noten = [f"let op: {tekst}"] if (tekst := herlaad.notitie(key)) else []
    noten += store.herkomst(key)
    known = store.meta(key)
    if known is not None and not known.volledig:
        noten.append(store.ONVOLLEDIG)
    noten += duo.sentinel_notes(duo.onderdrukt(key))
    if afronden:
        noten.append(duo.PROGNOSE_NOOT)
    return noten


def naar_csv(key: str) -> str | None:
    """De tabel onder `key` als CSV, of None als de store hem niet (meer) heeft."""
    df = store.get(key)
    if not isinstance(df, pd.DataFrame):
        return None
    afronden = duo.is_prognose(store.meta(key))
    uit = io.StringIO()
    for noot in _noten(key, afronden):
        uit.write(f"# {noot}\n")
    writer = csv.writer(uit, delimiter=";", lineterminator="\n")
    writer.writerow(df.columns)
    for rij in df.itertuples(index=False):
        writer.writerow(_cel(v, afronden) for v in rij)
    return uit.getvalue()
