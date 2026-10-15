"""CSV van de tabel achter een antwoord, voor Excel (#269).

De export is de tabel die query_data, run_analysis of get_maat in de store legde,
niet de tabel die het model in zijn antwoord overschreef. Puntkomma en decimale komma,
zoals Nederlandse Excel ze verwacht; wat de tabel over zichzelf moet zeggen
(bron, selecties, afkap, onderdrukte cellen) staat als '#'-regels erboven,
zoals bij de grafiekexport (#118). Data die na een herstart opnieuw bij de bron
is opgehaald zegt dat bovenaan: de cijfers kunnen afwijken van het antwoord (#472).
"""

import csv
import io
import json
import re
import unicodedata

import pandas as pd

from . import catalog, duo, herlaad, store
from .schemas import TOOL_GET_MAAT, TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS

# De stappen die een selectie in de store leggen en `data_key` plus `rijen` teruggeven. get_maat selecteert zelf
# (#188) en gaf daardoor geen CSV-knop (#538). De laders (get_cbs_data, get_duo_data, get_rio_data) blijven
# erbuiten: de export is de tabel achter het antwoord, niet het hele bronbestand.
_EXPORTEERBAAR = {TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS, TOOL_GET_MAAT}


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


# Excel voert tekst die met = + - of @ begint uit als formule (#483). Zulke tekst
# krijgt een ' ervoor, dus de CSV wijkt daar bewust af van de tabel in de store;
# getallen en getaltekst als '-1' of '-0,5' blijven zoals ze zijn.
# Dezelfde regel als safeText in frontend/src/figureCsv.js.
_FORMULE = re.compile(r"[=+\-@]")
_GETAL = re.compile(r"[+-]?\d+([.,]\d+)*")


def _veilig(tekst: str) -> str:
    if _FORMULE.match(tekst) and not _GETAL.fullmatch(tekst):
        return "'" + tekst
    return tekst


def _cel(v, afronden: bool) -> str:
    v = duo.json_waarde(v, afronden)
    if v is None or v is pd.NaT:
        return ""
    if isinstance(v, float):
        return repr(v).replace(".", ",")
    if isinstance(v, pd.Timestamp):
        return v.strftime("%d-%m-%Y")
    return _veilig(str(v))


# Wat de CSV zegt als de tabel afgekapt is (BEV-08): in de taal van wie het bestand opent, niet de
# aanwijzing voor de tool (store.ONVOLLEDIG). Een compleet bestand krijgt geen regel: dat is het gewone geval.
ONVOLLEDIG_EXPORT = (
    "Onvolledig bestand: de bron levert deze data in delen en dit bestand bevat alleen het eerste deel. "
    "Aantallen, sommen en totalen die je hieruit berekent, kloppen dus niet."
)


def _noten(key: str, afronden: bool) -> list[str]:
    noten = [f"let op: {tekst}"] if (tekst := herlaad.notitie(key)) else []
    noten += store.herkomst(key)
    known = store.meta(key)
    if known is not None and not known.volledig:
        noten.append(ONVOLLEDIG_EXPORT)
    noten += duo.sentinel_notes(duo.onderdrukt(key))
    if afronden:
        noten.append(duo.PROGNOSE_NOOT)
    return noten


# Bestandsnaam van een export (#533): <titel>_<dataset-id>.csv, zonder titel alleen het id. Elk deel veilig
# voor een bestandsnaam en de Content-Disposition-header: accenten weg (é → e), al het andere dan letters en
# cijfers een underscore, de titel hoogstens 80 tekens. Dezelfde regel als figureCsvFilename in
# frontend/src/figureCsv.js: de twee moeten gelijk opgaan.
_TITEL_MAX = 80


def _bestandsdeel(tekst: str) -> str:
    zonder_accenten = "".join(c for c in unicodedata.normalize("NFD", tekst) if not "\u0300" <= c <= "\u036f")
    return re.sub(r"[^A-Za-z0-9]+", "_", zonder_accenten).strip("_")


def bestandsnaam(key: str) -> str:
    """De naam van de CSV onder `key`: de catalogustitel van de dataset plus het dataset-id."""
    known = store.meta(key)
    if known is None:
        return "data.csv"
    titel = catalog.bron_titel(known.dataset)
    # Kent de catalogus de dataset niet, dan is de titel het kale id: dat staat er niet twee keer in.
    titeldeel = _bestandsdeel(titel)[:_TITEL_MAX].rstrip("_") if titel != known.dataset else ""
    naam = "_".join(deel for deel in (titeldeel, _bestandsdeel(known.dataset)) if deel)
    return f"{naam or 'data'}.csv"


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
    writer.writerow(_veilig(kolom) if isinstance(kolom, str) else kolom for kolom in df.columns)
    for rij in df.itertuples(index=False):
        writer.writerow(_cel(v, afronden) for v in rij)
    return uit.getvalue()
