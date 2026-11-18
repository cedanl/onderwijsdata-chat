"""Welke beurten met data in een rapport komen: de keuze van de gebruiker bij "Genereer rapport" (#908).

Het rapport kreeg alles wat het gesprek ophaalde. Een zijsprong, een verkeerde dataset of een vervangen vraag ging dus
mee, tenzij de gebruiker de afbakening typte. Nu toont de app een checklist van de beurten met data, en de server
rapporteert alleen over de beurten die de gebruiker aanliet. Alles in code, zonder model.

**Een beurt** is een vraag van de gebruiker (`session_data.gebruikersvragen`, 1-based) waarbij minstens één key
ontstond (`session["data_vraag"]`, #733). Een key hoort bij de beurt waarin hij voor het eerst ontstond. Een beurt die
alleen data van een eerdere beurt hergebruikt, heeft geen eigen regel.

**Geen checklist** zonder bewijs per beurt: heeft een key van het gesprek geen vraagnummer (een gesprek van vóór #875,
of een antwoord dat de geschiedenis niet meer haalt), dan weten we niet bij welke beurt hij hoort en blijft het
huidige gedrag staan, het hele gesprek. Een selectie bij zo'n gesprek wordt geweigerd, niet geraden.

**Het filter** bouwt een weergave van het gesprek zonder de uitgezette beurten (`beperk`): hun vraag en antwoord, hun
keys, het rekenbewijs en de figuren die erop rustten. Daarna ziet `agent.report` niets meer van wat de gebruiker
uitzette: de datasets, bronnen, definities, dataversie, controles (#754, #872) en afwijkingen volgen vanzelf uit die
weergave. Bewust een witte lijst van velden: een veld dat hier niet staat, bereikt het rapport niet.

**Eén uitzondering, met reden:** de herkomst van een geselecteerde key blijft zijn hele keten tot de laadaanroep. Bouwt
een beurt voort op de key van een uitgezette beurt, dan komt de bron van die laadaanroep in de bronnen: de data van het
rapport komt er immers vandaan. De uitgezette beurt zelf (vraag, figuur, tabel) blijft weg, en de regel van de
checklist zegt waar een beurt op voortbouwt (`bouwt_voort_op`), zodat de gebruiker dit voor zijn keuze weet.

**Figuren** (#993): per beurt ook de figuren die op haar data rusten (`figuren`, uit `agent.figuurstappen`), met de
titel van de figuur die de server maakte. Een figuur hoort bij de beurt waarin de data van haar `data_key` ontstond,
of anders de key die ze maakte: een latere beurt als "maak hem horizontaal" zonder nieuwe data heeft geen eigen regel,
haar figuur staat bij de beurt van de data. Het rapport bevat alleen de figuren die de gebruiker koos (hoogstens
`MAX_FIGUREN`); een gekozen figuur trekt de beurten van haar keys mee in de selectie.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.errors import Gebruikersfout

from . import figuurstappen
from .datasetcontext import build_recipe, sources_from_recipe
from .selectie import stapkeys
from .session_data import data_lineage, gebruikersvragen, is_vraag, rekenbewijs

# Een vraag in de checklist: genoeg om de beurt te herkennen, op één regel. De volledige tekst blijft in het gesprek.
MAX_VRAAG_TEKENS = 200

LEGE_SELECTIE = "Kies minstens één vraag met data voor het rapport. Zonder data kan ik geen rapport maken."
VEROUDERDE_SELECTIE = "Je keuze past niet meer bij dit gesprek. Sluit het venster en open het opnieuw."

# Zoveel figuren uit het gesprek neemt een rapport hoogstens over (besluit 10-11, #993).
MAX_FIGUREN = 4
TE_VEEL_FIGUREN = f"Kies hoogstens {MAX_FIGUREN} figuren voor het rapport."
ZONDER_TITEL = "Figuur zonder titel"


@dataclass(frozen=True)
class Keuze:
    """Wat de gebruiker voor het rapport koos: de beurten (None is het hele gesprek) en de figuren, in volgorde."""

    beurten: frozenset[int] | None = None
    figuren: tuple[str, ...] = ()


def beurten_met_data(session: dict) -> list[dict]:
    """De checklist van een gesprek: per beurt met data `beurt`, `vraag`, `bronnen`, `bouwt_voort_op` en `figuren`.

    `bronnen` zijn de bronregels van de data van die beurt, zoals het rapport ze noemt (catalogustitel en dataset-ID,
    uit code). `figuren` zijn de figuren van die beurt als `{id, titel}`, in de volgorde waarin ze ontstonden. Leeg als
    het gesprek geen beurten met data heeft, of als niet elke key bij een beurt te plaatsen is.
    """
    nummers = _vraagnummers(session)
    per_beurt: dict[int, list[str]] = {}
    for key, nummer in nummers.items():
        per_beurt.setdefault(nummer, []).append(key)
    figuren: dict[int, list[dict]] = {}
    for stap in figuurstappen.stappen(session):
        if (thuis := _thuisbeurt(stap, nummers)) is not None:
            figuren.setdefault(thuis, []).append({"id": stap["id"], "titel": stap.get("titel") or ZONDER_TITEL})
    vragen = gebruikersvragen(session)
    return [
        {
            "beurt": nummer,
            "vraag": _kort(vragen[nummer - 1]),
            "bronnen": _bronnen(session, keys),
            "bouwt_voort_op": sorted(
                {
                    vorig
                    for key in keys
                    for ouder in _voorouders(session, key)
                    if (vorig := nummers.get(ouder)) is not None and vorig != nummer
                }
            ),
            "figuren": figuren.get(nummer, []),
        }
        for nummer, keys in sorted(per_beurt.items())
    ]


def kies(session: dict, beurten: object, figuren: object = None) -> Keuze:
    """De beurten en figuren die de gebruiker koos, gecontroleerd tegen het gesprek; de client wordt niet vertrouwd.

    `beurten` None betekent het hele gesprek: er is geen selectie gestuurd, of alle beurten staan aan (ook doordat een
    gekozen figuur haar beurt meetrok), zodat het rapport hetzelfde is als zonder selectie. `figuren` zijn ids uit de
    checklist; zonder (een oudere client) of leeg komt er geen figuur in het rapport. Een lege selectie, een onbekend
    nummer of id, iets dat geen lijst getallen of ids is, meer dan `MAX_FIGUREN` figuren en een selectie bij een gesprek
    zonder checklist worden geweigerd (`Gebruikersfout`). Onbekende nummers negeren zou stil een ander rapport geven dan
    de gebruiker op zijn scherm kiest.
    """
    items = beurten_met_data(session) if beurten is not None or figuren else []
    gekozen_figuren = _gekozen_figuren(items, figuren)
    if beurten is None:
        return Keuze(None, gekozen_figuren)
    if not isinstance(beurten, list) or not all(type(n) is int for n in beurten):
        raise Gebruikersfout(VEROUDERDE_SELECTIE)
    bekend = {item["beurt"] for item in items}
    if not set(beurten) <= bekend:
        raise Gebruikersfout(VEROUDERDE_SELECTIE)
    # Een gekozen figuur trekt de beurten van haar keys mee (besluit 10-11).
    gekozen = set(beurten) | _beurten_van_figuren(session, gekozen_figuren)
    if not gekozen:
        raise Gebruikersfout(LEGE_SELECTIE)
    return Keuze(None if gekozen == bekend else frozenset(gekozen), gekozen_figuren)


def _gekozen_figuren(items: list[dict], figuren: object) -> tuple[str, ...]:
    """De gekozen figuur-ids, gecontroleerd tegen de checklist; leeg zonder keuze."""
    if figuren is None or figuren == []:
        return ()
    if not isinstance(figuren, list) or not all(isinstance(f, str) for f in figuren):
        raise Gebruikersfout(VEROUDERDE_SELECTIE)
    if len(figuren) > MAX_FIGUREN:
        raise Gebruikersfout(TE_VEEL_FIGUREN)
    bekend = {figuur["id"] for item in items for figuur in item["figuren"]}
    if len(set(figuren)) != len(figuren) or not set(figuren) <= bekend:
        raise Gebruikersfout(VEROUDERDE_SELECTIE)
    return tuple(figuren)


def _beurten_van_figuren(session: dict, ids: tuple[str, ...]) -> set[int]:
    nummers = _vraagnummers(session)
    return {b for stap in figuurstappen.stappen(session) if stap["id"] in ids for b in _beurten_van(stap, nummers)}


def _thuisbeurt(stap: dict, nummers: dict[str, int]) -> int | None:
    """De beurt van de eerste key van de stap die een beurt heeft: haar data_key, anders de key die ze maakte."""
    return next((nummers[k] for k in stap.get("keys") or [] if k in nummers), None)


def _beurten_van(stap: dict, nummers: dict[str, int]) -> set[int]:
    """De beurten van alle keys waar de figuur op rust, ook die van een script dat een andere key las."""
    return {nummers[k] for k in stap.get("keys") or [] if k in nummers}


def beperk(session: dict, beurten: frozenset[int]) -> dict:
    """Het gesprek zonder de uitgezette beurten, als sessie voor `agent.report.generate`.

    De overgebleven vragen krijgen opnieuw een nummer vanaf 1, zodat "Ontstaan bij vraag N" in de rapportprompt
    klopt. Een witte lijst: alleen de velden die het rapport leest.
    """
    nummers = _vraagnummers(session)
    if not nummers or not set(beurten) <= set(nummers.values()):
        raise Gebruikersfout(VEROUDERDE_SELECTIE)
    uit = set(nummers.values()) - beurten
    gekozen = [key for key in session["data_keys"] if nummers[key] in beurten]
    # De keys waarop het rapport rust: de gekozen en waar zij van afstammen (hun herkomst, zie boven).
    toegestaan = {*gekozen, *(ouder for key in gekozen for ouder in _voorouders(session, key))}
    provenance = session.get("data_provenance") or {}
    return {
        "username": session.get("username"),
        "chat_settings": session.get("chat_settings"),
        "messages": _zonder_beurten(session.get("messages") or [], uit),
        "data_keys": gekozen,
        "data_vraag": {key: nummers[key] - sum(1 for u in uit if u < nummers[key]) for key in gekozen},
        "data_provenance": {key: call for key, call in provenance.items() if key in toegestaan},
        "rekenbewijs": [b for b in rekenbewijs(session) if _rust_op(b) <= toegestaan and _rust_op(b)],
        # De figuren die op de overgebleven beurten rusten; welke ervan in het rapport komen, kiest de gebruiker.
        "figuurstappen": [
            s for s in figuurstappen.stappen(session) if (b := _beurten_van(s, nummers)) and b <= beurten
        ],
        "turns": [],
    }


def _vraagnummers(session: dict) -> dict[str, int]:
    """Per key van het gesprek zijn beurt, of niets als één key er geen heeft (zie boven: dan geen checklist)."""
    keys = list(session.get("data_keys") or [])
    nummers = session.get("data_vraag") or {}
    aantal = len(gebruikersvragen(session))
    if not keys or any(type(nummers.get(key)) is not int or not 1 <= nummers[key] <= aantal for key in keys):
        return {}
    return {key: nummers[key] for key in keys}


def _voorouders(session: dict, key: str) -> list[str]:
    """De keys waarvan `key` is afgeleid, van zijn ouder tot de laadkey (de aanroep noemt zijn ouder in `data_key`)."""
    provenance = session.get("data_provenance") or {}
    ouders: list[str] = []
    while key in provenance and len(ouders) < len(provenance):
        ouder = (provenance[key].get("arguments") or {}).get("data_key")
        if not isinstance(ouder, str) or ouder in ouders:
            break
        ouders.append(ouder)
        key = ouder
    return ouders


def _bronnen(session: dict, keys: list[str]) -> list[str]:
    datasets = [{"data_key": key, "herkomst": data_lineage(session, key)} for key in keys]
    return sources_from_recipe(build_recipe(datasets))


def _rust_op(bewijs: dict) -> set[str]:
    """De keys waarop een rekenuitkomst rust: wat de stap las en de key die zij kreeg."""
    argument = (bewijs.get("argumenten") or {}).get("data_key")
    return {*stapkeys(bewijs["resultaat"]), *([argument] if isinstance(argument, str) else [])}


def _zonder_beurten(berichten: list[dict], uit: set[int]) -> list[dict]:
    """De berichten zonder de uitgezette beurten: elke vraag met alles wat erna komt tot de volgende vraag."""
    over: list[dict] = []
    nummer = 0
    weg = False
    for bericht in berichten:
        if is_vraag(bericht):
            nummer += 1
            weg = nummer in uit
        if not weg:
            over.append(bericht)
    return over


def _kort(vraag: str) -> str:
    tekst = " ".join(vraag.split())
    return tekst if len(tekst) <= MAX_VRAAG_TEKENS else tekst[: MAX_VRAAG_TEKENS - 1] + "…"
