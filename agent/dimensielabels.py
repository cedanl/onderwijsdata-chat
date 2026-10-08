"""Welke CBS-dimensiewaarden een antwoord gekozen heeft, uit code (#401, audit 14 §3.2).

De getalcontrole ziet 118.160 in de tooluitvoer en is tevreden; dat het A025279 'Totaal
(speciaal) basisonderwijs' is en geen 'studenten, alle onderwijssoorten', ziet alleen een
mens. De selectie staat in de data achter de keys van de beurt: een dimensie die daar
op één waarde vastligt, is gekozen. Die labels komen onder het antwoord, en de tekst mag
er niet iets ruimers van maken.
"""

import re

from tools import cbs, store
from tools.catalog import bron_naam

from .probleem import Probleem
from .selectie import data_keys

# CBS-totaalcodes beginnen met T00 (T001038 'Totaal'); een label dat met 'Totaal' begint
# is dat niet altijd: 'Totaal (speciaal) basisonderwijs' is een deeltotaal.
_TOTAALCODE = re.compile(r"^T00")
_LABEL = "_label"
# Onderwijssoorten met leerlingen, niet studenten: po, so en vo.
_LEERLINGEN = re.compile(r"basisonderwijs|speciaal onderwijs|voortgezet|vmbo|havo|vwo|praktijkonderwijs", re.IGNORECASE)
_STUDENTEN = re.compile(r"\bstudenten\b", re.IGNORECASE)
_LEERLINGWOORD = re.compile(r"\bleerlingen\b", re.IGNORECASE)


def _bladeren(tool_results: list[str]) -> list[str]:
    """De CBS-keys van de beurt waar geen andere key van de beurt van is afgeleid: de selectie."""
    keys = [k for k in dict.fromkeys(data_keys(tool_results)) if k.startswith("cbs:")]
    ouders = {known.afgeleid_van for k in keys if (known := store.meta(k)) and known.afgeleid_van}
    return [k for k in keys if k not in ouders]


def _gekozen(key: str) -> dict[str, tuple[str | None, str]]:
    """Dimensie → (code, label) voor elke niet-tijddimensie die in de data op één waarde ligt."""
    df = store.get(key)
    known = store.meta(key)
    if df is None or known is None:
        return {}
    gekozen = {}
    for dim in cbs.dimension_columns(key):
        if dim == known.periodekolom or dim + _LABEL not in df.columns:
            continue
        labels = df[dim + _LABEL].dropna().unique()
        if len(labels) != 1:
            continue
        codes = df[dim].dropna().unique() if dim in df.columns else []
        gekozen[dim] = (str(codes[0]) if len(codes) == 1 else None, str(labels[0]))
    return gekozen


def _selecties(tool_results: list[str]) -> dict[str, dict[str, tuple[str | None, str]]]:
    selecties: dict[str, dict[str, tuple[str | None, str]]] = {}
    for key in _bladeren(tool_results):
        known = store.meta(key)
        if known and (gekozen := _gekozen(key)):
            selecties.setdefault(known.dataset, gekozen)
    return selecties


def selectie_regels(tool_results: list[str]) -> list[str]:
    """Regels voor het telling-blok: per CBS-dataset de gekozen dimensielabels."""
    regels = []
    for dataset, gekozen in _selecties(tool_results).items():
        keuzes = "; ".join(f"{dim}: {label}" for dim, (_, label) in gekozen.items())
        regels.append(f"- {bron_naam(dataset)}: selectie {keuzes}")
    return regels


def _ruimer_dan_gekozen(tekst: str, dataset: str, dim: str, code: str | None, label: str) -> Probleem | None:
    """'Alle onderwijssoorten' terwijl de selectie één deelwaarde is."""
    if not code or _TOTAALCODE.match(code):
        return None
    m = re.search(rf"\balle\s+{re.escape(dim.lower().rstrip('s'))}\w*", tekst, re.IGNORECASE)
    if not m:
        return None
    return Probleem(
        f"De tekst zegt '{m.group(0)}', maar de selectie uit {dataset} is {dim} = '{label}' ({code}).",
        f"Noem de gekozen waarde '{label}' en maak er geen totaal van.",
    )


def _studenten_bij_leerlingen(tekst: str, dataset: str, dim: str, label: str) -> Probleem | None:
    """'Studenten' terwijl de gekozen onderwijssoort po, so of vo is."""
    if not dim.lower().startswith("onderwijssoort") or not _LEERLINGEN.search(label):
        return None
    if not _STUDENTEN.search(tekst) or _LEERLINGWOORD.search(tekst):
        return None
    return Probleem(
        f"De tekst noemt studenten, maar de selectie uit {dataset} is '{label}': dat zijn leerlingen.",
        f"Noem het getal bij zijn label '{label}' en spreek van leerlingen.",
    )


def verkeerde_dimensielabels(tekst: str, tool_results: list[str]) -> list[str]:
    """Een tekst die van de gekozen CBS-dimensiewaarde iets ruimers of iets anders maakt."""
    problemen = []
    for dataset, gekozen in _selecties(tool_results).items():
        for dim, (code, label) in gekozen.items():
            problemen += [
                p
                for p in (
                    _ruimer_dan_gekozen(tekst, dataset, dim, code, label),
                    _studenten_bij_leerlingen(tekst, dataset, dim, label),
                )
                if p
            ]
    return problemen
