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

# Wat een DUO-key telt, uit het label van zijn teldefinitie ("Ingeschrevenen: …").
# p01 en p02 tellen hoofdinschrijvingen als personen, p03 alle inschrijvingen (#172).
_TEKST_INSCHRIJVINGEN = re.compile(r"(?<!hoofd)inschrijving", re.IGNORECASE)
_TEKST_PERSONEN = re.compile(r"\bpersonen\b", re.IGNORECASE)


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
    for key in data_keys(tool_results):
        known = store.meta(key)
        if known and (eenheid := _teleenheid(known.teldefinitie)):
            eenheden.setdefault(eenheid, known.dataset)
    if len(eenheden) != 1:
        return []
    [(eenheid, dataset)] = eenheden.items()
    verkeerd, woord = (
        (_TEKST_INSCHRIJVINGEN, "inschrijvingen") if eenheid == "personen" else (_TEKST_PERSONEN, "personen")
    )
    if not verkeerd.search(tekst):
        return []
    return [
        f"{dataset} telt {eenheid} (teldefinitie van DUO), maar de tekst spreekt van {woord}. "
        f"Noem de teleenheid zoals de bron hem telt."
    ]
