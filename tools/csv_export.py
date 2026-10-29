"""CSV van de tabel achter een antwoord, voor Excel (#269).

De export is de tabel die query_data, run_analysis of get_maat in de store legde,
of de selectie van een lader als het toolresultaat haar helemaal toonde (#605);
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

from . import catalog, duo, herlaad, inhoudshash, store
from .schemas import (
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_MAAT,
    TOOL_GET_RIO_DATA,
    TOOL_QUERY_DATA,
    TOOL_RUN_ANALYSIS,
)

# De stappen die een selectie in de store leggen en `data_key` plus `rijen` teruggeven. get_maat selecteert zelf
# (#188) en gaf daardoor geen CSV-knop (#538).
_EXPORTEERBAAR = {TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS, TOOL_GET_MAAT}
# De laders leggen een hele selectie in de store en tonen het model alleen de eerste rijen (`preview`). Toonde
# het resultaat álle rijen, dan is die selectie de tabel achter het antwoord: het model schreef zijn tabel eruit
# en er kwam geen query_data meer aan te pas (#605: een CBS-selectie van twee schooljaren gaf geen knop). Een
# grotere selectie blijft erbuiten: de export zou het hele bronbestand zijn, niet de tabel in het antwoord; de
# geciteerde getallen zijn dan de export (frontend/src/citatieCsv.js, #544).
_LADERS = {TOOL_GET_CBS_DATA, TOOL_GET_DUO_DATA, TOOL_GET_RIO_DATA}


def _resultaat(result: str) -> dict | None:
    try:
        parsed = json.loads(result)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _alle_rijen_getoond(parsed: dict) -> bool:
    """Staan alle rijen van de geladen selectie in het toolresultaat (store.rijtelling, rio.get_rio_data)?"""
    preview = parsed.get("preview")
    if not isinstance(preview, list) or not preview:
        return False
    if parsed.get("volledig") is False or parsed.get("meer_beschikbaar") is True:
        return False
    aantal = parsed.get("totaal_rijen", parsed.get("opgehaalde_rijen"))
    return isinstance(aantal, int) and aantal == len(preview)


def export_key(name: str, result: str) -> str | None:
    """De key van de tabel die deze stap opleverde, of None als er niets te exporteren is."""
    parsed = _resultaat(result)
    if parsed is None:
        return None
    if name in _EXPORTEERBAAR:
        # run_analysis zonder bron verpakt zijn uitkomst onder 'resultaat': geen tabel uit de bron (#201).
        tabel = bool(parsed.get("rijen"))
    elif name in _LADERS:
        tabel = _alle_rijen_getoond(parsed)
    else:
        return None
    key = parsed.get("data_key")
    return key if tabel and isinstance(key, str) else None


# Waarom een antwoord met een tabel geen tabel-key kreeg (#605), voor het EXPORT-log in agent/run.py.
GEEN_DATASTAP = "geen_datastap"
BRON_GROTER_DAN_RESULTAAT = "bron_groter_dan_toolresultaat"


def geen_export_reden(steps: list[tuple[str, str]]) -> str:
    """Een lader legde wel data in de store, maar toonde niet alle rijen; of er was geen datastap."""
    for tool, result in steps:
        if tool in _LADERS and (parsed := _resultaat(result)) and isinstance(parsed.get("data_key"), str):
            return BRON_GROTER_DAN_RESULTAAT
    return GEEN_DATASTAP


# Excel voert tekst die met = + - of @ begint uit als formule (#483); OWASP (CSV injection)
# noemt ook een tab en een CR vooraan (#607). Zulke tekst krijgt een ' ervoor, dus de CSV
# wijkt daar bewust af van de tabel in de store; getallen en getaltekst als '-1' of '-0,5'
# blijven zoals ze zijn. csv.writer zet een cel met een CR tussen quotes, dus die splitst
# geen rij. Dezelfde regel als safeText in frontend/src/figureCsv.js.
_FORMULE = re.compile(r"[=+\-@\t\r]")
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
    if inhoud := inhoudshash.hash_van(key):
        noten.append(
            f"inhoudshash van de brontabel: {inhoud} (sha256 van df.to_csv(index=False), eerste 12 tekens; "
            "zie docs/reproducibility.md)"
        )
    known = store.meta(key)
    if known is not None and known.bronhash:
        noten.append(
            f"md5 van het DUO-bestand: {known.bronhash} (zoals DUO het levert, na te rekenen met md5sum; "
            "zie docs/reproducibility.md)"
        )
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
