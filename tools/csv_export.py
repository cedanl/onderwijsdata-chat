"""CSV van de tabel achter een antwoord, voor Excel (#269).

De export is de tabel die query_data, run_analysis, koppel_data of get_maat in de store legde,
of de selectie van een lader als het toolresultaat haar helemaal toonde (#605), of de tabel achter
get_bestuursfinancien, get_wo_personeel of get_studiekeuze (#956, #957), of de vacatures van CBS (#1226, #1227);
niet de tabel die het model in zijn antwoord overschreef. Puntkomma en decimale komma,
zoals Nederlandse Excel ze verwacht; wat de tabel over zichzelf moet zeggen
(bron, selecties, afkap, onderdrukte cellen) staat als '#'-regels erboven,
zoals bij de grafiekexport (#118); een rij met een onderdrukte cel zegt dat in
de kolom `ondergrens` (#1257). Data die na een herstart opnieuw bij de bron
is opgehaald zegt dat bovenaan: de cijfers kunnen afwijken van het antwoord (#472).
"""

import csv
import io
import json
import re

import pandas as pd

from core.bestandsnaam import bestandsdeel

from . import catalog, duo, herlaad, ondergrens, store
from .exportnoten import herkomstregels
from .schemas import (
    TOOL_GET_BESTUURSFINANCIEN,
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_MAAT,
    TOOL_GET_ONTSTANE_VACATURES,
    TOOL_GET_RIO_DATA,
    TOOL_GET_STUDIEKEUZE,
    TOOL_GET_VACATURES,
    TOOL_GET_WO_PERSONEEL,
    TOOL_KOPPEL_DATA,
    TOOL_QUERY_DATA,
    TOOL_RUN_ANALYSIS,
)

# Het label van de knop onder een antwoord met een tabel (frontend/src/components/DataExport.jsx): een toolmelding en de
# prompt noemen hem zo, zodat het model niet zegt dat het geen bestand kan geven (#979).
KNOP = "Download data als CSV"

# De stappen die een selectie in de store leggen en `data_key` plus `rijen` teruggeven. get_maat selecteert zelf
# (#188) en gaf daardoor geen CSV-knop (#538). koppel_data legt de koppeling van twee tabellen neer (#988).
_EXPORTEERBAAR = {TOOL_QUERY_DATA, TOOL_RUN_ANALYSIS, TOOL_KOPPEL_DATA, TOOL_GET_MAAT}
# De laders leggen een hele selectie in de store en tonen het model alleen de eerste rijen (`preview`). Toonde
# het resultaat álle rijen, dan is die selectie de tabel achter het antwoord: het model schreef zijn tabel eruit
# en er kwam geen query_data meer aan te pas (#605: een CBS-selectie van twee schooljaren gaf geen knop). Een
# grotere selectie blijft erbuiten: de export zou het hele bronbestand zijn, niet de tabel in het antwoord; de
# geciteerde getallen zijn dan de export (frontend/src/citatieCsv.js, #544).
_LADERS = {TOOL_GET_CBS_DATA, TOOL_GET_DUO_DATA, TOOL_GET_RIO_DATA}
# Een bron met een eigen resultaatvorm toont haar hele tabel, in haar eigen vorm (#956): elke eenheid en elk verslagjaar
# van een bestuur, elk jaar en elke groep van een WOPI-selectie. Haar tabel in de store is de tabel achter het antwoord.
# De vacatures van CBS (#1226, #1227) tonen hun hele tabel ook: elke sectie of elk beroep met elke periode.
_EIGEN_VORM = {
    TOOL_GET_BESTUURSFINANCIEN,
    TOOL_GET_WO_PERSONEEL,
    TOOL_GET_STUDIEKEUZE,
    TOOL_GET_VACATURES,
    TOOL_GET_ONTSTANE_VACATURES,
}


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
    elif name in _EIGEN_VORM:
        tabel = True
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


def _noten(key: str, afronden: bool, username: str | None) -> list[str]:
    """De herkomstregels (dezelfde als bij de grafiek, #809), met de herlaadnotitie en de prognosenoot erbij."""
    noten = [f"let op: {tekst}"] if (tekst := herlaad.notitie(username, key)) else []
    noten += herkomstregels(key)
    if afronden:
        noten.append(duo.PROGNOSE_NOOT)
    return noten


# Bestandsnaam van een export (#533): <titel>_<dataset-id>.csv, zonder titel alleen het id. Elk deel veilig
# voor een bestandsnaam en de Content-Disposition-header: accenten weg (é → e), al het andere dan letters en
# cijfers een underscore, de titel hoogstens 80 tekens (core/bestandsnaam.py). Dezelfde regel als figureCsvFilename
# in frontend/src/figureCsv.js: de twee moeten gelijk opgaan.
_TITEL_MAX = 80
_KENMERK_MAX = 40


def bestandsnaam(key: str) -> str:
    """De naam van de CSV onder `key`: de catalogustitel van de dataset plus het dataset-id."""
    known = store.meta(key)
    if known is None:
        return "data.csv"
    titel = catalog.bron_titel(known.dataset, vo_context=known.vo_context)
    # Kent de catalogus de dataset niet, dan is de titel het kale id: dat staat er niet twee keer in.
    titeldeel = bestandsdeel(titel, _TITEL_MAX) if titel != known.dataset else ""
    delen = (titeldeel, bestandsdeel(known.dataset), _selectiedeel(key, known))
    return f"{'_'.join(deel for deel in delen if deel) or 'data'}.csv"


def _selectiedeel(key: str, known: store.KeyMeta) -> str:
    """Wat een afgeleide tabel onderscheidt van haar ouder en van de andere selecties op dezelfde dataset (#1120): haar
    kenmerk (de groepering) en de rest van de key (resource en digest van de selectie). De ruwe lading houdt de naam
    van de dataset."""
    if not known.afgeleid_van:
        return ""
    delen = (bestandsdeel(known.kenmerk, _KENMERK_MAX), bestandsdeel(":".join(key.split(":")[2:])))
    return "_".join(deel for deel in delen if deel)


def naar_csv(key: str, username: str | None = None) -> str | None:
    """De tabel onder `key` als CSV, of None als de store hem niet (meer) heeft."""
    df = store.get(key)
    if not isinstance(df, pd.DataFrame):
        return None
    afronden = duo.is_prognose(store.meta(key))
    # Per rij ja/nee: valt er een onderdrukte cel in, dan is die rij een ondergrens (#1257). Alleen als de bron zulke
    # cellen per rij heeft; een tabel zonder krijgt geen extra kolom.
    met_vlag = ondergrens.met_kolom(df, key)
    noten = _noten(key, afronden, username)
    if met_vlag is not df:
        noten.append(ondergrens.KOLOMREGEL)
        df = met_vlag
    uit = io.StringIO()
    for noot in noten:
        uit.write(f"# {noot}\n")
    writer = csv.writer(uit, delimiter=";", lineterminator="\n")
    writer.writerow(_veilig(kolom) if isinstance(kolom, str) else kolom for kolom in df.columns)
    for rij in df.itertuples(index=False):
        writer.writerow(_cel(v, afronden) for v in rij)
    return uit.getvalue()
