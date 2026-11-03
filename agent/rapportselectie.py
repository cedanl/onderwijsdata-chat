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
keys, het rekenbewijs en de kaarten die erop rustten. Daarna ziet `agent.report` niets meer van wat de gebruiker
uitzette: de datasets, bronnen, definities, dataversie, controles (#754, #872) en afwijkingen volgen vanzelf uit die
weergave. Bewust een witte lijst van velden: een veld dat hier niet staat, bereikt het rapport niet.

**Eén uitzondering, met reden:** de herkomst van een geselecteerde key blijft zijn hele keten tot de laadaanroep. Bouwt
een beurt voort op de key van een uitgezette beurt, dan komt de bron van die laadaanroep in de bronnen: de data van het
rapport komt er immers vandaan. De uitgezette beurt zelf (vraag, figuur, tabel) blijft weg, en de regel van de
checklist zegt waar een beurt op voortbouwt (`bouwt_voort_op`), zodat de gebruiker dit voor zijn keuze weet.
"""

from __future__ import annotations

from core.errors import Gebruikersfout

from .datasetcontext import build_recipe, sources_from_recipe
from .kaarten import kaarten_in_gesprek
from .selectie import stapkeys
from .session_data import data_lineage, gebruikersvragen, is_vraag, rekenbewijs

# Een vraag in de checklist: genoeg om de beurt te herkennen, op één regel. De volledige tekst blijft in het gesprek.
MAX_VRAAG_TEKENS = 200

LEGE_SELECTIE = "Kies minstens één vraag met data voor het rapport. Zonder data kan ik geen rapport maken."
VEROUDERDE_SELECTIE = "Je keuze past niet meer bij dit gesprek. Sluit het venster en open het opnieuw."


def beurten_met_data(session: dict) -> list[dict]:
    """De checklist van een gesprek: per beurt met data `beurt`, `vraag`, `bronnen` en `bouwt_voort_op`.

    `bronnen` zijn de bronregels van de data van die beurt, zoals het rapport ze noemt (catalogustitel en dataset-ID,
    uit code). Leeg als het gesprek geen beurten met data heeft, of als niet elke key bij een beurt te plaatsen is.
    """
    nummers = _vraagnummers(session)
    per_beurt: dict[int, list[str]] = {}
    for key, nummer in nummers.items():
        per_beurt.setdefault(nummer, []).append(key)
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
        }
        for nummer, keys in sorted(per_beurt.items())
    ]


def kies(session: dict, beurten: object) -> frozenset[int] | None:
    """De beurten die de gebruiker koos, gecontroleerd tegen het gesprek; de client wordt niet vertrouwd.

    None betekent het hele gesprek: er is geen selectie gestuurd, of alle beurten staan aan, zodat het rapport
    hetzelfde is als zonder selectie. Een lege selectie, een onbekend nummer, iets dat geen lijst getallen is en een
    selectie bij een gesprek zonder checklist worden geweigerd (`Gebruikersfout`). Onbekende nummers negeren zou stil
    een ander rapport geven dan de gebruiker op zijn scherm kiest.
    """
    if beurten is None:
        return None
    if not isinstance(beurten, list) or not all(type(n) is int for n in beurten):
        raise Gebruikersfout(VEROUDERDE_SELECTIE)
    if not beurten:
        raise Gebruikersfout(LEGE_SELECTIE)
    bekend = {item["beurt"] for item in beurten_met_data(session)}
    if not set(beurten) <= bekend:
        raise Gebruikersfout(VEROUDERDE_SELECTIE)
    return None if set(beurten) == bekend else frozenset(beurten)


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
        "kaarten": {key: kaart for key, kaart in kaarten_in_gesprek(session).items() if key in gekozen},
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
