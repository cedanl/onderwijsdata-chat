"""Vervolgvragen onder een data-antwoord: uit de catalogus, niet van het model (#364).

Het model beslist er niets over: de app biedt ze aan onder elk gewoon antwoord met data (#539). Welke,
beslist code: de voorbeeldvragen uit de catalogus van de datasets die de beurt laadde, alleen als de
chat ze kan beantwoorden. Een voorbeeldvraag valt af als ze

- in de eerste persoon staat ("mijn regio", "onze instelling"): zonder profiel eindigde zo'n vraag
  in een scopeweigering (CH-42);
- een ruwe veldnaam, codewaarde of technische term noemt (AANGEBODENBOOPLEIDING, eindeAanmeldperiode,
  code C0001, sub-resource), of een dataset bij zijn ID (aangeboden-opleidingen, 85423NED);
- naar het antwoord ervoor wijst ("hoe verhoudt dit zich …", "de data"): als knop zegt ze dan niets;
- over po, so of vo gaat ("BO-opleidingen", vmbo, havo): buiten de scope van de chat (#355);
- om een aantal uit een RIO-register vraagt: get_rio_data levert één pagina en geen totalen (#170);
- haar eigen dataset niet terugvindt met search_catalog: dan vindt het model hem ook niet.

Toetsen kost een zoekactie per vraag; dat gebeurt per dataset één keer per proces, pas als een beurt
de dataset laadt (alle vragen samen kosten zo'n vijftien seconden).
"""

import json
import re
from functools import cache
from itertools import chain, zip_longest

from tools import catalog, scopeprofiel, store

from .selectie import laadkey, stapkeys

MAX_VERVOLGVRAGEN = 3

_EERSTE_PERSOON = re.compile(r"\b(?:mijn|ons|onze)\b", re.IGNORECASE)
# Een veldnaam, codewaarde of technische term uit de bron: met een underscore, zes of meer hoofdletters,
# camelCase, een code als C0001, of het woord resource.
_VELDNAAM = re.compile(r"\w_\w|\b[A-Z]{6,}\b|\b[a-z]+[A-Z]\w*|\b[A-Z]+\d{3,}\b|\bresources?\b")
# Een sjabloonvraag die naar het antwoord erboven wijst.
_VERWIJZEND = re.compile(r"\b(?:dit|de data)\b", re.IGNORECASE)
_AANTAL = re.compile(r"\b(?:hoeveel|aantal)\b", re.IGNORECASE)


def _noemt_dataset_id(vraag: str) -> bool:
    """Noemt de vraag een dataset bij zijn ID? Een ID dat een gewoon woord is ("opleidingen") telt niet."""
    return any(not dataset_id.isalpha() for dataset_id in catalog.genoemde_datasets(vraag))


def _leesbaar(vraag: str) -> bool:
    """Een vraag die een gebruiker zo kan stellen, die op zichzelf staat en binnen de scope van de chat valt."""
    return not (
        _EERSTE_PERSOON.search(vraag)
        or _VELDNAAM.search(vraag)
        or _VERWIJZEND.search(vraag)
        or scopeprofiel.PO_SO_VO.search(vraag)
        or _noemt_dataset_id(vraag)
    )


def _vindt_eigen_dataset(vraag: str, dataset_id: str) -> bool:
    """Zet search_catalog de dataset van de vraag bij zijn treffers?"""
    try:
        treffers = json.loads(catalog.search_catalog(vraag))
    except ValueError:  # geen treffers: dan is het antwoord een melding, geen lijst
        return False
    return any(isinstance(t, dict) and scopeprofiel.dataset_id(t) == dataset_id for t in treffers)


@cache
def _beantwoordbaar(dataset_id: str) -> tuple[str, ...]:
    """De voorbeeldvragen van één dataset die de chat kan beantwoorden; leeg als hij er geen heeft."""
    rio = catalog.leverancier(dataset_id) == "RIO"
    with catalog.stil():
        return tuple(
            vraag
            for vraag in catalog.voorbeeldvragen().get(dataset_id, [])
            if _leesbaar(vraag) and not (rio and _AANTAL.search(vraag)) and _vindt_eigen_dataset(vraag, dataset_id)
        )


def beantwoordbare_vragen() -> dict[str, tuple[str, ...]]:
    """Per dataset die de chat kan ophalen: de voorbeeldvragen die hij kan beantwoorden."""
    return {dataset_id: vragen for dataset_id in catalog.voorbeeldvragen() if (vragen := _beantwoordbaar(dataset_id))}


def datasets_van(steps: list[tuple[str, str]]) -> list[str]:
    """De datasets waarop de stappen van een beurt rusten, in de volgorde waarin ze voor het eerst gebruikt zijn."""
    datasets: list[str] = []
    for _, resultaat in steps:
        for key in stapkeys(resultaat):
            if (meta := store.meta(laadkey(key))) and meta.dataset not in datasets:
                datasets.append(meta.dataset)
    return datasets


def _vorm(vraag: str) -> str:
    return " ".join(vraag.split()).casefold()


def kies(steps: list[tuple[str, str]], gevraagd: str, getoond: list[str], n: int = MAX_VERVOLGVRAGEN) -> list[str]:
    """Tot `n` vervolgvragen bij de datasets van de beurt, om en om per dataset.

    Niet de vraag die de gebruiker net stelde en niets wat dit gesprek al eerder aanbood (`getoond`);
    hoofdletters en spaties tellen daarbij niet. Zonder geladen dataset: geen vragen.
    """
    bekend = {_vorm(gevraagd), *map(_vorm, getoond)}
    per_dataset = [_beantwoordbaar(dataset_id) for dataset_id in datasets_van(steps)]
    gekozen: list[str] = []
    for vraag in chain.from_iterable(zip_longest(*per_dataset)):
        if len(gekozen) == n:
            break
        if vraag and _vorm(vraag) not in bekend:
            gekozen.append(vraag)
            bekend.add(_vorm(vraag))
    return gekozen
