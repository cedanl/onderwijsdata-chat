"""Een vaste regel met de afbakening waarop een antwoord rust, uit code (#620, R-07 en R-08).

Na de keuze "Universiteit Utrecht" (21PD) schreef het antwoord "Utrecht had in 2023/24 38.288 studenten": het
getal klopte, de naam was verkort en naast Hogeschool Utrecht dubbelzinnig. Op "Waarom zijn er meer studenten
informatica?" rustte het antwoord op wo, informatica en landelijk, maar dat stond alleen in losse tekst. Legt de
selectie van de beurt een afbakening vast die de gebruiker niet noemde, dan opent het antwoord met één regel
"**Uitgangspunt:** …": de instelling met haar volledige naam en code, de CBS-dimensies op één waarde en de
periode. Alleen uit de toolstappen, geen modeltekst (#191), net als de interpretatiezin (#514). Een eigen
berekening (run_analysis) telt met de selectie die ze las: haar uitvoer komt uit het script van het model.
"""

import json
import re
from dataclasses import dataclass, field

from tools import instelling, store
from tools.catalog import bron_naam
from tools.herlaad import STAP_ANALYSE
from tools.maten import ALLE
from tools.schemas import TOOL_GET_MAAT
from tools.store import KeyMeta

from .dimensielabels import vaste_waarden
from .grounding import bewijs_getallen, checked_numbers, getallen_met_positie
from .selectie import SCHEIDING, bladeren, keten, laadkey, periode_in_woorden, stapkeys

KOP = "**Uitgangspunt:**"
# Meer instellingen is een vergelijking of een overzicht: een opsomming daarvan is geen uitgangspunt.
_MAX_INSTELLINGEN = 3
_JAARTAL = re.compile(r"(?<!\w)(\d{4})(?!\d)")


@dataclass
class _Afbakening:
    """Wat de selecties uit één dataset vastleggen."""

    instellingen: dict[str, str] = field(default_factory=dict)  # code → naam; "" als get_maat geen naam gaf
    waarden: list[str] = field(default_factory=list)  # sector en vorm van get_maat, CBS-dimensielabels
    perioden: list[KeyMeta] = field(default_factory=list)


@dataclass(frozen=True)
class _Deel:
    tekst: str
    genoemd: bool  # de gebruiker noemde het, of bij een instelling: de modeltekst noemt haar volledig


def _json(result: str) -> dict:
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _maatdataset(parsed: dict) -> str:
    """De dataset van een get_maat-resultaat, uit zijn recept of zijn key."""
    if isinstance(recept := parsed.get("recept"), dict) and isinstance(recept.get("dataset"), str):
        return recept["dataset"]
    known = store.meta(laadkey(key)) if isinstance(key := parsed.get("data_key"), str) else None
    return known.dataset if known else ""


def _uit_maten(steps: list[tuple[str, str]], per: dict[str, _Afbakening]) -> None:
    """De afbakening die get_maat koos: de instelling uit het register, anders de sector; de vorm tenzij alle."""
    for tool, result in steps:
        if tool != TOOL_GET_MAAT or not (parsed := _json(result)):
            continue
        afbakening = per.setdefault(_maatdataset(parsed), _Afbakening())
        if isinstance(inst := parsed.get("instelling"), dict) and inst.get("instellingscode"):
            afbakening.instellingen.setdefault(str(inst["instellingscode"]), str(inst.get("naam") or ""))
        elif isinstance(sector := parsed.get("sector"), str) and sector:
            afbakening.waarden.append(sector)
        if isinstance(vorm := parsed.get("vorm"), str) and vorm and vorm != ALLE:
            afbakening.waarden.append(vorm)


def _is_selectie(known: KeyMeta) -> bool:
    """Een CBS-key is al een selectie (de filters gaan mee naar de bron); van DUO alleen wat ervan is afgeleid."""
    return known.bron == "cbs" or (known.bron == "duo" and known.afgeleid_van is not None)


def _instellingen(key: str, known: KeyMeta) -> dict[str, str]:
    """Code → naam van de instellingen in een selectie, zoals de geladen DUO-data ze noemt.

    Een code die daar niet met een naam in staat, valt weg: de regel noemt alleen instellingen uit de bron.
    """
    if not known.instellingen or len(known.instellingen) > _MAX_INSTELLINGEN or not known.instellingskolom:
        return {}
    df = store.get(laadkey(key))
    if df is None or instelling.codekolom(df.columns) != known.instellingskolom:
        return {}
    namen = instelling.namen(df, known.instellingskolom)
    return {code: namen[code] for code in known.instellingen if code in namen}


def _berekening(key: str) -> str | None:
    """De eerste eigen berekening (run_analysis) in de afleiding van `key`, vanaf de laadkey; None als er geen is."""
    return next((k for k in reversed(keten(key)) if (m := store.meta(k)) and m.stap == STAP_ANALYSE), None)


def _bronselecties(key: str, gezien: frozenset[str] = frozenset()) -> list[str]:
    """De selecties waarop `key` rust.

    De instellingen en schooljaren van een eigen berekening, en van wat daarop verder bouwt, komen uit de rijen die
    het script van het model teruggaf. In hun plaats tellen de selecties die de berekening las (`gelezen`).
    """
    if (berekening := _berekening(key)) is None:
        return [key]
    if berekening in gezien or not (known := store.meta(berekening)):
        return []
    return [bron for k in known.gelezen or () for bron in _bronselecties(k, gezien | {berekening})]


def _uit_selecties(steps: list[tuple[str, str]], per: dict[str, _Afbakening]) -> None:
    """De afbakening in de bladselecties van de beurt: de keys waar geen andere key van de beurt van is afgeleid."""
    bladen = bladeren([k for _, result in steps for k in stapkeys(result)])
    for key in dict.fromkeys(bron for blad in bladen for bron in _bronselecties(blad)):
        if not (known := store.meta(key)) or not _is_selectie(known):
            continue
        afbakening = per.setdefault(known.dataset, _Afbakening())
        for code, naam in _instellingen(key, known).items():
            afbakening.instellingen.setdefault(code, naam)
        afbakening.waarden += vaste_waarden(key)
        afbakening.perioden.append(known)


def _dragende_stappen(tekst: str, steps: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """De stappen waarop de getallen in het antwoord rusten, zoals de grenzen in het Telling-blok (#414).

    Een selectie die na een herkansing is vervangen (Aeres in plaats van de HU, #143) is geen uitgangspunt. Rust
    geen getal op een stap, dan gelden alle stappen van de beurt. Uit de modeltekst komen alleen de getallen die
    de stappen aanwijzen, geen tekst.
    """
    getallen = {cijfers for _, cijfers, _ in getallen_met_positie(tekst)}
    return [stap for stap in steps if getallen & bewijs_getallen(stap[1])] or steps


def _afbakeningen(steps: list[tuple[str, str]]) -> dict[str, _Afbakening]:
    per: dict[str, _Afbakening] = {}
    _uit_maten(steps, per)
    _uit_selecties(steps, per)
    return per


def _woord_in(tekst: str, woord: str) -> bool:
    return bool(woord) and re.search(rf"(?<!\w){re.escape(woord)}(?!\w)", tekst, re.IGNORECASE) is not None


def _periode_genoemd(vraag: str, known: KeyMeta) -> bool:
    """Noemt de vraag een jaar in de periode: het begin- of eindjaar van een van haar schooljaren?"""
    jaren = set(known.schooljaren or ()) | {j + 1 for j in known.schooljaren or ()}
    return any(int(jaar) in jaren for jaar in _JAARTAL.findall(vraag))


def _delen(afbakening: _Afbakening, vraag: str, tekst: str, met_instellingen: bool) -> list[_Deel]:
    """De onderdelen van één dataset, zonder dubbele en zonder gecontroleerd getal (dat kreeg een citatie)."""
    delen = [
        _Deel(f"{naam} ({code})" if naam else code, _woord_in(tekst, naam) or _woord_in(tekst, code))
        for code, naam in (afbakening.instellingen.items() if met_instellingen else ())
    ]
    delen += [_Deel(waarde, _woord_in(vraag, waarde)) for waarde in afbakening.waarden]
    delen += [
        _Deel(jaren, _periode_genoemd(vraag, known))
        for known in afbakening.perioden
        if (jaren := periode_in_woorden(known))
    ]
    uniek: dict[str, _Deel] = {}
    for deel in delen:
        if not checked_numbers(deel.tekst):
            uniek.setdefault(deel.tekst.casefold(), deel)
    return list(uniek.values())


def _bronnaam(dataset: str) -> str:
    naam = bron_naam(dataset)
    return dataset if checked_numbers(naam) else naam


def _weergave(groepen: dict[str, list[_Deel]]) -> list[str]:
    """De onderdelen in volgorde; bij meer datasets eerst wat ze delen, daarna per dataset de rest met haar naam."""
    lijsten = [[d.tekst for d in delen] for delen in groepen.values()]
    if len(lijsten) == 1:
        return lijsten[0]
    gedeeld = [t for t in lijsten[0] if all(t in lijst for lijst in lijsten[1:])]
    uit = list(gedeeld)
    for dataset, lijst in zip(groepen, lijsten, strict=True):
        if eigen := ", ".join(t for t in lijst if t not in gedeeld):
            uit.append(f"{_bronnaam(dataset)}: {eigen}" if dataset else eigen)
    return [deel for deel in uit if not checked_numbers(deel)]


def uitgangspunt(vraag: str, tekst: str, steps: list[tuple[str, str]]) -> str | None:
    """De Uitgangspunt-regel, of None als de selectie niets vastlegt of de gebruiker alles al noemde.

    `vraag` is de vraag van deze beurt met de gekozen verduidelijkingsopties. `tekst` beslist alleen of het model de
    instelling al volledig noemde (naam of code) en op welke stappen zijn getallen rusten; de regel zelf komt
    helemaal uit de toolstappen.
    """
    afbakeningen = _afbakeningen(_dragende_stappen(tekst, steps))
    codes = {code for a in afbakeningen.values() for code in a.instellingen}
    met_instellingen = len(codes) <= _MAX_INSTELLINGEN
    groepen = {
        dataset: delen
        for dataset, afbakening in afbakeningen.items()
        if (delen := _delen(afbakening, vraag, tekst, met_instellingen))
    }
    if all(deel.genoemd for delen in groepen.values() for deel in delen) or not (weergave := _weergave(groepen)):
        return None
    return f"{KOP} {SCHEIDING.join(weergave)}"


def met_uitgangspunt(tekst: str, vraag: str, steps: list[tuple[str, str]]) -> str:
    """Het antwoord met de Uitgangspunt-regel ervoor, als de selectie iets vastlegt dat de gebruiker niet noemde."""
    regel = uitgangspunt(vraag, tekst, steps) if tekst.strip() else None
    return f"{regel}\n\n{tekst}" if regel else tekst
