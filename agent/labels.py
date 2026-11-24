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
from tools.duo import OPLEIDINGSVORM_DATASETS, OPLEIDINGSVORMEN

from .probleem import Probleem
from .selectie import data_keys

_CODES = "|".join(OPLEIDINGSVORMEN)
_VORMEN = "|".join(OPLEIDINGSVORMEN.values())
# "Deeltijd (DU)" en "DU = deeltijd": woord en code naast elkaar.
_VORM_CODE = re.compile(rf"\b({_VORMEN})\w*\s*\(\s*({_CODES})\s*\)", re.IGNORECASE)
_CODE_VORM = re.compile(rf"\b({_CODES})\s*(?:=|:|staat voor|betekent)\s*({_VORMEN})", re.IGNORECASE)

# DUO-ID's (p01hoinges, p02ho1ejrs, ook met een streepje: p09mbo-fantasie) en CBS-tabelnummers (85423NED).
_DATASET_ID = re.compile(r"\b(p\d{2}[a-z0-9]{3,}(?:-[a-z0-9]+)*|\d{5}(?:NED|ENG))\b")
# De Bronnen-sectie uit prompts/system.md, tot de Definities of het einde (#213).
BRONNEN = re.compile(r"\*\*Bronnen\*\*(.*?)(?=\*\*Definities\*\*|\Z)", re.DOTALL)


def verkeerde_opleidingsvormen(tekst: str, tool_results: list[str]) -> list[str]:
    """Een opleidingsvormcode naast het woord van een andere vorm.

    Alleen als de beurt data heeft uit een dataset waarvan de beschrijving deze codes
    noemt; elders betekent OPLEIDINGSVORM iets anders (#371).
    """
    if not any(
        (known := store.meta(key)) and known.dataset in OPLEIDINGSVORM_DATASETS for key in data_keys(tool_results)
    ):
        return []
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


def _dataset_ids(tekst: str) -> list[str]:
    """De dataset-ID's in de tekst, zoals ze er staan.

    Een ID met een streepje erachter ("p01hoinges-bestand") is het ID van vóór het streepje als dat bestaat: wat erna
    komt is dan een woord. Anders is het hele woord het ID dat het model noemt ("p09mbo-fantasie", #1085).
    """
    ids = []
    for gevonden in _DATASET_ID.findall(tekst):
        kaal = gevonden.split("-")[0]
        ids.append(kaal if catalogus_titel(kaal) != kaal else gevonden)
    return sorted(set(ids))


def onbekende_datasets(tekst: str, genoemd: str = "") -> list[Probleem]:
    """Dataset-ID's in de tekst die niet in de catalogus staan, zoals een typfout in de bron.

    `genoemd` is wat de beurt zelf noemde: de vraag van de gebruiker en de toolresultaten. Een ID dat daar staat is niet
    verzonnen door het model: een antwoord dat terecht zegt dat tabel 99999NED niet bestaat, krijgt geen melding (#1088).
    """
    genoemd = genoemd.lower()
    return [
        Probleem(f"Dataset {dataset_id} bestaat niet in de catalogus.", "Noem de dataset-ID zoals de tool hem gaf.")
        for dataset_id in _dataset_ids(tekst)
        if catalogus_titel(dataset_id) == dataset_id and dataset_id.lower() not in genoemd
    ]


def ongebruikte_bronnen(tekst: str, tool_results: list[str]) -> list[str]:
    """Dataset-ID's in de Bronnen-sectie die bestaan, maar niet in de data van deze beurt zitten.

    Alleen de Bronnen-sectie: daar wordt een dataset als bron opgegeven. Elders mag
    een ID als context staan ("DUO publiceert ook p03hoinschr"). Zonder data in de
    beurt zwijgt de controle: een vervolgvraag mag de bron van een eerdere beurt noemen.
    Een ID dat niet bestaat meldt onbekende_datasets al.
    """
    gebruikt = {known.dataset.lower() for key in data_keys(tool_results) if (known := store.meta(key))}
    sectie = BRONNEN.search(tekst)
    if not gebruikt or not sectie:
        return []
    return [
        Probleem(
            f"Dataset {dataset_id} staat in de bronnen, maar is in deze beurt niet gebruikt.",
            "Noem alleen de datasets waar de getallen uit komen.",
        )
        for dataset_id in _dataset_ids(sectie.group(1))
        if dataset_id.lower() not in gebruikt and catalogus_titel(dataset_id) != dataset_id
    ]
