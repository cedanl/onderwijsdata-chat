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

from .probleem import Probleem
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
                Probleem(
                    f"'{woord}' met code {code}: {code} is {OPLEIDINGSVORMEN[code]}, {vorm} is {juiste_code[vorm]} "
                    "(DUO-datasetbeschrijving)."
                )
            )
    return problemen


def onbekende_datasets(tekst: str) -> list[str]:
    """Dataset-ID's in de tekst die niet in de catalogus staan, zoals een typfout in de bron."""
    return [
        Probleem(f"Dataset {dataset_id} bestaat niet in de catalogus.", "Noem de dataset-ID zoals de tool hem gaf.")
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
        Probleem(
            f"Dataset {dataset_id} staat in de bronnen, maar is in deze beurt niet gebruikt.",
            "Noem alleen de datasets waar de getallen uit komen.",
        )
        for dataset_id in sorted(set(_DATASET_ID.findall(sectie.group(1))))
        if dataset_id.lower() not in gebruikt and catalogus_titel(dataset_id) != dataset_id
    ]
