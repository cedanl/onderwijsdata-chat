"""Kloppen de namen bij de getallen? (#196)

De getalcontrole (grounding.py) en de selectiecontroles (selectie.py) zien een
antwoord waarvan elk getal klopt. Live-audit 8 vond de fout in de woorden
erbij: "Deeltijd (DU)" terwijl DU duaal is, "inschrijvingen" boven personen uit
p01hoinges, en p01hoenges als bron. Deze controles leggen die woorden naast de
brondata: de codes uit de DUO-beschrijving, de catalogus en de teldefinitie
van de keys waarop het antwoord rust.
"""

import re

from tools import store
from tools.catalog import catalogus_titel
from tools.duo import OPLEIDINGSVORMEN

from .selectie import data_keys

_CODES = "|".join(OPLEIDINGSVORMEN)
_VORMEN = "|".join(OPLEIDINGSVORMEN.values())
# "Deeltijd (DU)" en "DU = deeltijd": woord en code naast elkaar.
_VORM_CODE = re.compile(rf"\b({_VORMEN})\w*\s*\(\s*({_CODES})\s*\)", re.IGNORECASE)
_CODE_VORM = re.compile(rf"\b({_CODES})\s*(?:=|:|staat voor|betekent)\s*({_VORMEN})", re.IGNORECASE)

# DUO-ID's (p01hoinges, p02ho1ejrs) en CBS-tabelnummers (85423NED).
_DATASET_ID = re.compile(r"\b(p\d{2}[a-z0-9]{3,}|\d{5}(?:NED|ENG))\b")
# De Bronnen-sectie uit prompts/system.md, tot de Definities of het einde (#213).
_BRONNEN = re.compile(r"\*\*Bronnen\*\*(.*?)(?=\*\*Definities\*\*|\Z)", re.DOTALL)

# Wat een DUO-key telt, uit het label van zijn teldefinitie ("Ingeschrevenen: …").
# p01 en p02 tellen hoofdinschrijvingen als personen, p03 alle inschrijvingen (#172).
_TEKST_INSCHRIJVINGEN = re.compile(r"(?<!hoofd)inschrijving", re.IGNORECASE)
_TEKST_PERSONEN = re.compile(r"\bpersonen\b", re.IGNORECASE)

# Een ontkenning vlak vóór het woord ("geen inschrijvingen maar personen", "gaat om
# personen, niet om inschrijvingen") is toelichting, geen toeschrijving (#214).
_ZIN_EINDE = re.compile(r"[!?;\n]|\.(?!\d)")
_ONTKENNING = re.compile(r"\b(?:geen|niet|nooit)\b(?:\W+\w+){0,3}?\W*$", re.IGNORECASE)
# Of erna, in DUO's eigen woorden: "Inschrijvingen … worden niet meegeteld" (#239).
_UITGESLOTEN = re.compile(r"\bniet\s+(?:meegeteld|meegenomen|geteld)\b|\bbuiten\s+beschouwing\b", re.IGNORECASE)
_WOORD = re.compile(r"\w+")
# Zoveel woorden rond het woord moeten letterlijk in de teldefinitie staan om als citaat te tellen.
_CITAAT_VOOR, _CITAAT_NA = 2, 4


def verkeerde_opleidingsvormen(tekst: str) -> list[str]:
    """Een opleidingsvormcode naast het woord van een andere vorm."""
    problemen = []
    paren = [(m.group(1), m.group(2)) for m in _VORM_CODE.finditer(tekst)]
    paren += [(m.group(2), m.group(1)) for m in _CODE_VORM.finditer(tekst)]
    juiste_code = {vorm: code for code, vorm in OPLEIDINGSVORMEN.items()}
    for woord, code in paren:
        vorm, code = woord.lower(), code.upper()
        if OPLEIDINGSVORMEN[code] != vorm:
            problemen.append(
                f"'{woord}' met code {code}: {code} is {OPLEIDINGSVORMEN[code]}, {vorm} is {juiste_code[vorm]} "
                "(DUO-datasetbeschrijving)."
            )
    return problemen


def onbekende_datasets(tekst: str) -> list[str]:
    """Dataset-ID's in de tekst die niet in de catalogus staan, zoals een typfout in de bron."""
    return [
        f"Dataset {dataset_id} bestaat niet in de catalogus; noem de dataset-ID zoals de tool hem gaf."
        for dataset_id in sorted(set(_DATASET_ID.findall(tekst)))
        if catalogus_titel(dataset_id) == dataset_id
    ]


def ongebruikte_bronnen(tekst: str, tool_results: list[str]) -> list[str]:
    """Dataset-ID's in de Bronnen-sectie die bestaan, maar niet in de data van deze beurt zitten.

    Alleen de Bronnen-sectie: daar wordt een dataset als bron opgegeven. Elders mag
    een ID als context staan ("DUO publiceert ook p03hoinschr"). Zonder data in de
    beurt zwijgt de controle: een vervolgvraag mag de bron van een eerdere beurt noemen.
    Een ID dat niet bestaat meldt onbekende_datasets al.
    """
    gebruikt = {known.dataset.lower() for key in data_keys(tool_results) if (known := store.meta(key))}
    sectie = _BRONNEN.search(tekst)
    if not gebruikt or not sectie:
        return []
    return [
        f"Dataset {dataset_id} staat in de bronnen, maar is in deze beurt niet gebruikt; "
        f"noem alleen de datasets waar de getallen uit komen."
        for dataset_id in sorted(set(_DATASET_ID.findall(sectie.group(1))))
        if dataset_id.lower() not in gebruikt and catalogus_titel(dataset_id) != dataset_id
    ]


def _geciteerd(zin: str, start: int, definitie: str) -> bool:
    """Staat het woord met zijn omgeving letterlijk in de DUO-teldefinitie (#239)?"""
    woorden = _WOORD.findall(zin.lower())
    i = len(_WOORD.findall(zin[:start]))
    venster = woorden[max(0, i - _CITAAT_VOOR): i + _CITAAT_NA]
    return f" {' '.join(venster)} " in f" {definitie} "


def _toegeschreven(verkeerd: re.Pattern, tekst: str, definities: list[str]) -> bool:
    """Staat het woord ergens als bewering in de tekst, dus niet in een ontkenning of citaat?"""
    definitie = " ".join(" ".join(_WOORD.findall(d.lower())) for d in definities)
    for zin in _ZIN_EINDE.split(tekst):
        for treffer in verkeerd.finditer(zin):
            voor = zin[: treffer.start()].rsplit(" maar ", 1)[-1]
            bijzin = zin[treffer.end():].split(",", 1)[0]
            if _ONTKENNING.search(voor) or _UITGESLOTEN.search(bijzin):
                continue
            if not _geciteerd(zin, treffer.start(), definitie):
                return True
    return False


def _teleenheid(teldefinitie: str | None) -> str | None:
    label = (teldefinitie or "").split(":", 1)[0].strip().lower()
    if label.startswith("inschrijving"):
        return "inschrijvingen"
    if label.endswith("ingeschrevenen"):
        return "personen"
    return None


def verkeerde_teleenheid(tekst: str, tool_results: list[str]) -> list[str]:
    """Personen als inschrijvingen gebracht, of andersom.

    Alleen als alle keys van de beurt hetzelfde tellen: een vergelijking van p01
    en p03 noemt terecht beide.
    """
    eenheden = {}
    definities = []
    for key in data_keys(tool_results):
        known = store.meta(key)
        if known and (eenheid := _teleenheid(known.teldefinitie)):
            eenheden.setdefault(eenheid, known.dataset)
            definities.append(known.teldefinitie)
    if len(eenheden) != 1:
        return []
    [(eenheid, dataset)] = eenheden.items()
    verkeerd, woord = (
        (_TEKST_INSCHRIJVINGEN, "inschrijvingen") if eenheid == "personen" else (_TEKST_PERSONEN, "personen")
    )
    if not _toegeschreven(verkeerd, tekst, definities):
        return []
    return [
        f"{dataset} telt {eenheid} (teldefinitie van DUO), maar de tekst spreekt van {woord}. "
        f"Noem de teleenheid zoals de bron hem telt."
    ]
