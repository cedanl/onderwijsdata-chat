"""Vervolgvragen onder een data-antwoord: uit de catalogus, niet van het model (#364).

Het model beslist er niets over: de app biedt ze aan onder elk gewoon antwoord met data (#539). Welke,
beslist code: de voorbeeldvragen uit de catalogus van de datasets die de beurt laadde, alleen als de
chat ze kan beantwoorden. Een voorbeeldvraag valt af als ze

- in de eerste persoon staat ("mijn regio", "onze instelling"): zonder profiel eindigde zo'n vraag
  in een scopeweigering (CH-42);
- een ruwe veldnaam, codewaarde of technische term noemt (AANGEBODENBOOPLEIDING, eindeAanmeldperiode,
  code C0001, sub-resource), of een dataset bij zijn ID (aangeboden-opleidingen, 85423NED);
- naar het antwoord ervoor wijst ("hoe verhoudt dit zich …", "de data"): als knop zegt ze dan niets;
- over po, so of vo gaat ("BO-opleidingen", vmbo, havo): buiten de scope van de chat (#355). Een vo-contextrecord
  (`scopeprofiel.HO_CONTEXT`) houdt zo'n vraag als ze ook hoger onderwijs noemt (`noemt_ho`): dezelfde regel als
  de zoekpoort voor die records (#557, #558);
- om een aantal uit een RIO-register vraagt: get_rio_data levert één pagina en geen totalen (#170);
- haar eigen dataset niet terugvindt met search_catalog: dan vindt het model hem ook niet.

Toetsen kost een zoekactie per vraag; dat gebeurt per dataset één keer per proces, pas als een beurt
de dataset laadt (alle vragen samen kosten zo'n vijftien seconden).

Sinds #615 komen de eerste twee knoppen uit de vraag zelf: dezelfde maat als in het antwoord, met de selectie
die het antwoord citeert, voor een ander schooljaar en als ontwikkeling over de jaren. De derde komt uit de
voorbeeldvragen van de dataset (andere snede). Beide in code: de maat en de selectie staan in de citaties
(agent/citaties.py), de schooljaren in de store; er komt geen model aan te pas (#191).
"""

import json
import re
from functools import cache
from itertools import chain, zip_longest

from tools import catalog, periode, scopeprofiel, store
from tools.ho_markers import noemt_ho

from .citaties import citaties
from .selectie import SCHEIDING, laadkey, stapkeys

MAX_VERVOLGVRAGEN = 3
# Hoeveel knoppen uit de vraagcontext komen (#615); de rest uit de voorbeeldvragen van de dataset.
UIT_VRAAGCONTEXT = 2

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


def _buiten_scope(vraag: str, dataset_id: str | None) -> bool:
    """Gaat de vraag over po, so of vo? Bij een vo-contextrecord niet als ze ook hoger onderwijs noemt (#558)."""
    if not scopeprofiel.PO_SO_VO.search(vraag):
        return False
    return not (dataset_id and scopeprofiel.is_ho_context(dataset_id) and noemt_ho(vraag))


def _leesbaar(vraag: str, dataset_id: str | None = None) -> bool:
    """Een vraag die een gebruiker zo kan stellen, die op zichzelf staat en binnen de scope van de chat valt.

    `dataset_id` is de dataset waar de vraag bij hoort; zonder ID geldt de po/so/vo-uitsluiting altijd.
    """
    return not (
        _EERSTE_PERSOON.search(vraag)
        or _VELDNAAM.search(vraag)
        or _VERWIJZEND.search(vraag)
        or _buiten_scope(vraag, dataset_id)
        or _noemt_dataset_id(vraag)
    )


def _vindt_eigen_dataset(vraag: str, dataset_id: str) -> bool:
    """Zet search_catalog de dataset van de vraag bij zijn treffers?"""
    try:
        envelop = json.loads(catalog.search_catalog(vraag))
    except ValueError:
        return False
    if not isinstance(envelop, dict) or envelop.get("status") != "candidates":  # geen treffers: een melding
        return False
    return any(
        isinstance(t, dict) and scopeprofiel.dataset_id(t) == dataset_id for t in envelop.get("kandidaten") or []
    )


@cache
def _beantwoordbaar(dataset_id: str) -> tuple[str, ...]:
    """De voorbeeldvragen van één dataset die de chat kan beantwoorden; leeg als hij er geen heeft."""
    rio = catalog.leverancier(dataset_id) == "RIO"
    with catalog.stil():
        return tuple(
            vraag
            for vraag in catalog.voorbeeldvragen().get(dataset_id, [])
            if _leesbaar(vraag, dataset_id)
            and not (rio and _AANTAL.search(vraag))
            and _vindt_eigen_dataset(vraag, dataset_id)
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


# --- uit de vraagcontext (#615) ---

# Een schooljaar in een selectie uit de citaties: CBS "2021/'22", DUO "2021/2022", of een los jaar.
_SCHOOLJAAR = re.compile(r"\b(20\d{2})(?:/'?\d{2,4})?\b")
_TIJDDIMENSIE = re.compile(r"^(?:perioden|periode|studiejaar|jaar)$", re.IGNORECASE)


def _selectiedelen(selectie: str) -> tuple[set[int], list[str]]:
    """De schooljaren in een geciteerde selectie, en de andere delen die geen totaal zijn ("Vrouwen")."""
    jaren: set[int] = set()
    delen: list[str] = []
    for deel in selectie.split(SCHEIDING):
        naam, _, waarde = deel.partition(":")
        waarde = waarde.strip()
        if _TIJDDIMENSIE.match(naam.strip()) or _SCHOOLJAAR.search(waarde):
            jaren.update(int(m.group(1)) for m in _SCHOOLJAAR.finditer(waarde))
        elif waarde and "totaal" not in waarde.casefold():
            delen.append(waarde)
    return jaren, delen


def _onderwerp(maat: str, delen: list[str], eenheid: str | None) -> tuple[str, bool]:
    """ "mbo studenten (vrouwen)" en of het een aantal is (dan "hoeveel … waren er")."""
    kern = maat[0].lower() + maat[1:] if maat[:1].isupper() and not maat[:2].isupper() else maat
    if delen:
        kern += f" ({', '.join(d[0].lower() + d[1:] if not d[:2].isupper() else d for d in delen)})"
    return kern, (eenheid or "").casefold() in {"aantal", "aantallen"}


def kandidaten_uit_context(cites: list[dict], meta_van) -> list[str]:
    """Vervolgvragen uit de vraag zelf (#615): de eerste geciteerde maat met een leesbare titel en een bron met
    schooljaren. Eerst het nieuwste schooljaar dat het antwoord niet noemt, dan de ontwikkeling over de jaren.

    `meta_van(data_key)` geeft de KeyMeta van de bron (store.meta op de laadkey); de kolomtitels daarin maken
    van MboStudenten_1 "Mbo studenten". Zonder titel uit de bron (DUO, RIO) of zonder schooljaren: geen
    contextvragen, dan komen alle knoppen uit de dataset zoals voorheen.
    """
    for c in cites:
        if not (c.get("vastgesteld") and c.get("maat") and c.get("data_key")):
            continue
        meta = meta_van(c["data_key"])
        jaren = tuple(meta.schooljaren or ()) if meta else ()
        # Alleen een titel uit de bron (CBS DataProperties) is een onderwerp; een kolomnaam als AANTAL niet.
        maat = (meta.kolomtitels or {}).get(c["maat"]) if meta else None
        if len(jaren) < 2 or not maat:
            continue
        genoemd, delen = _selectiedelen(c.get("selectie") or "")
        onderwerp, aantal = _onderwerp(maat, delen, c.get("eenheid"))
        vragen: list[str] = []
        if nieuw := [j for j in jaren if j not in genoemd]:
            jaar = periode.label(max(nieuw))
            vragen.append(
                f"Hoeveel {onderwerp} waren er in {jaar}?" if aantal else f"Hoe hoog was {onderwerp} in {jaar}?"
            )
        if len(jaren) >= 3 and len(genoemd & set(jaren)) < 3:
            span = f"{periode.label(jaren[0])} tot en met {periode.label(jaren[-1])}"
            vragen.append(
                f"Hoe ontwikkelde het aantal {onderwerp} zich van {span}?"
                if aantal
                else f"Hoe ontwikkelde {onderwerp} zich van {span}?"
            )
        return vragen[:UIT_VRAAGCONTEXT]
    return []


def uit_vraagcontext(steps: list[tuple[str, str]], tekst: str) -> list[str]:
    """De contextvragen bij een antwoordtekst: uit zijn citaties en de store (#615)."""
    if not tekst:
        return []
    return kandidaten_uit_context(citaties(tekst, steps), lambda key: store.meta(laadkey(key)))


def kies(
    steps: list[tuple[str, str]], gevraagd: str, getoond: list[str], n: int = MAX_VERVOLGVRAGEN, tekst: str = ""
) -> list[str]:
    """Tot `n` vervolgvragen: eerst (tot twee) uit de vraagcontext van `tekst` (#615), dan uit de
    voorbeeldvragen van de datasets van de beurt, om en om per dataset.

    Niet de vraag die de gebruiker net stelde en niets wat dit gesprek al eerder aanbood (`getoond`);
    hoofdletters en spaties tellen daarbij niet. Zonder geladen dataset: geen vragen.
    """
    bekend = {_vorm(gevraagd), *map(_vorm, getoond)}
    per_dataset = [_beantwoordbaar(dataset_id) for dataset_id in datasets_van(steps)]
    if not per_dataset:
        return []
    gekozen: list[str] = []
    for vraag in chain(uit_vraagcontext(steps, tekst), chain.from_iterable(zip_longest(*per_dataset))):
        if len(gekozen) == n:
            break
        if vraag and _vorm(vraag) not in bekend:
            gekozen.append(vraag)
            bekend.add(_vorm(vraag))
    return gekozen
