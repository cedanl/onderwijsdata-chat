"""De bronnen onder een dataantwoord, uit de toolstappen van de beurt (#416, CH-09).

Het model schreef zelf een Bronnen-sectie. Vijf keer dezelfde vraag gaf de ene keer één bron,
de andere keer twee, met een eigen titel of zonder periode. Welke data de beurt las, staat in
de stappen: de app zet die lijst onder het antwoord, en de eigen sectie van het model vervalt,
net als zijn Definities bij een teldefinitie uit de bron (agent/telling.py, #402).

Elke regel linkt naar de bronpagina van zijn dataset (#621), met de documentatie-URL uit de
catalogus: dezelfde link als onder een rapportgrafiek (agent/figuurbron.py, #569).

Een vervolgantwoord zonder toolaanroep heeft geen stappen; noemt het data van de vorige databeurt, dan komen de
bronregels van die data uit de store (`vervolgbronnen`, #975).
"""

import json
import re
from collections.abc import Callable

from tools import collegegeld, financien, inspectie, inspectie_vo, mbo_indicatoren, store, studiekeuze, wo_personeel
from tools.arbeidsmarkt import DATASET
from tools.catalog import bron_titel, documentatie_url
from tools.rio_instelling import ERKENNINGEN
from tools.schemas import (
    TOOL_GET_BESTUURSFINANCIEN,
    TOOL_GET_COLLEGEGELD,
    TOOL_GET_INSPECTIEOORDEEL,
    TOOL_GET_INSPECTIEOORDEEL_VO,
    TOOL_GET_MBO_INDICATOREN,
    TOOL_GET_RIO_INSTELLING,
    TOOL_GET_STUDIEKEUZE,
    TOOL_GET_WO_PERSONEEL,
)
from tools.scopeprofiel import VO_CONTEXT_DEEL
from tools.store import KeyMeta

from .meetwaarden import meetwaarden
from .selectie import SCHEIDING, laadkey, meta_in_woorden, stapkeys

# Een bronregel en de dataset waar hij over gaat; None als de stap die niet noemt.
Bronregel = tuple[str, str | None]

# De eigen Bronnen-sectie van het model: de kop (**Bronnen**, **Bronnen:** of **Bronnen**:) en zijn lijst.
_KOP = r"\*\*Bronnen(?::\*\*|\*\*:?)"
_OPSOMMING = r"[ \t]*[-*+][ \t]"
_GENUMMERD = r"[ \t]*\d+[.)][ \t]"
# Onder een kale kop mogen de bronnen ook als losse regels staan, tot een lege regel, lijst of vetgedrukte kop.
_LOSSE_REGELS = rf"(?:\n(?!{_OPSOMMING}|{_GENUMMERD}|\n|\*\*)[^\n]*)*"


def _lijst(item: str) -> str:
    """Items van één soort, ook met lege regels ertussen, elk met zijn ingesprongen vervolgregels.

    Een regel die zonder inspringen tegen de lijst plakt (een kanttekening) of een lijst van een
    andere soort na een lege regel (vervolgstappen) hoort er niet meer bij.
    """
    return rf"(?:\n+{item}[^\n]*(?:\n[ \t]+\S[^\n]*)*)+"


# Alleen vanaf de eerste van een reeks lege regels: elk beginpunt erbinnen kostte kwadratische tijd
# op een lange reeks, en dat bevroor de event loop voor iedereen.
_EIGEN_BRONNEN = re.compile(
    rf"(?<!\n)\n*^{_KOP}(?:[ \t]*(?=\n|\Z){_LOSSE_REGELS}|[^\n]*)"
    rf"(?:{_lijst(_OPSOMMING)}|{_lijst(_GENUMMERD)})?(?:\n\Z)?",
    re.MULTILINE,
)


def _zonder_sectie(sectie: re.Match[str]) -> str:
    """Plakt er een regel direct onder de sectie, dan houdt die een lege regel boven zich: een eigen alinea."""
    volgt = sectie.string[sectie.end() : sectie.end() + 2]
    return "\n" if len(volgt) == 2 and volgt[0] == "\n" and volgt[1] != "\n" else ""


def _dag(iso: str) -> str:
    """jjjj-mm-dd als dd-mm-jjjj, zoals de andere data in een bronregel ("versie van 08-04-2026")."""
    jaar, maand, dag = iso[:10].split("-")
    return f"{dag}-{maand}-{jaar}"


def _actualiteit(known: KeyMeta) -> str:
    """Hoe actueel een CBS-tabel is: wanneer CBS hem bijwerkte en wanneer de app hem ophaalde (#864)."""
    if known.bron != "cbs":
        return ""
    bijgewerkt = f"bijgewerkt door CBS op {_dag(known.bijgewerkt_op)}, " if known.bijgewerkt_op else ""
    return f", {bijgewerkt}opgehaald op {known.opgehaald_op.astimezone():%d-%m-%Y}"


def _metabron(known: KeyMeta) -> Bronregel:
    """Een geladen dataset in woorden, met zijn ID, uit haar meta: ook als de store de tabel kwijt is (#986)."""
    tekst = meta_in_woorden(known)
    # Zonder catalogustitel is de titel het ID al.
    tekst = tekst if known.dataset in tekst else f"{tekst} ({known.dataset})"
    return tekst + _actualiteit(known), str(known.dataset)


def _datasetbron(key: str) -> Bronregel | None:
    """De geladen dataset achter een key in woorden, met zijn ID; None als hij onbekend is (CH-30)."""
    known = store.meta(laadkey(key))
    return _metabron(known) if known else None


def _registerbron(tool: str, result: str) -> list[Bronregel]:
    """Een opzoeking in het RIO-register (get_rio_instelling) laadt niets in de store, maar leest wel data."""
    if tool != TOOL_GET_RIO_INSTELLING:
        return []
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, dict) or not isinstance(titel := parsed.get("catalogus_titel"), str):
        return []
    bron = str(parsed.get("bron") or "RIO")
    tekst = titel if titel.startswith(bron) else f"{bron}{SCHEIDING}{titel}"
    return [(f"{tekst}, peildatum {parsed['peildatum']}" if parsed.get("peildatum") else tekst, ERKENNINGEN)]


# Bronnen buiten de catalogus die een bestand lezen: het Inspectie-oordeel (#749), de vo-oordelen met het etiket van de
# vo-context (#881), de mbo-indicatoren van DUO (#727), de tabel met het wettelijk collegegeld uit de wettekst (#729) en
# de financiële verantwoording van DUO per bestuur (#935).
_BESTANDSBRONNEN = {
    TOOL_GET_INSPECTIEOORDEEL: f"{inspectie.BRONNAAM}{SCHEIDING}{inspectie.BRONTITEL}",
    TOOL_GET_INSPECTIEOORDEEL_VO: f"{inspectie.BRONNAAM}{SCHEIDING}{inspectie_vo.BRONTITEL}, {VO_CONTEXT_DEEL}",
    TOOL_GET_MBO_INDICATOREN: f"{mbo_indicatoren.BRONNAAM}{SCHEIDING}{mbo_indicatoren.BRONTITEL}",
    TOOL_GET_COLLEGEGELD: f"{collegegeld.BRONNAAM}{SCHEIDING}{collegegeld.BRONTITEL}",
    # De vaste bronregel komt uit de tool zelf (`bron.regel`), met de GEZO-variant erin (#936).
    TOOL_GET_WO_PERSONEEL: f"{wo_personeel.BRONNAAM}{SCHEIDING}{wo_personeel.BRONTITEL}",
    TOOL_GET_BESTUURSFINANCIEN: f"{financien.BRONNAAM}{SCHEIDING}{financien.BRONTITEL}",
    # De bronregel komt uit de tool zelf (`bron.regel`), met het versienummer en de verplichte zin van LCSK (#957).
    TOOL_GET_STUDIEKEUZE: f"{studiekeuze.BRONNAAM}{SCHEIDING}{studiekeuze.BRONTITEL}",
}
# Welke velden van `bron` in de bronregel komen, en met welk woord ervoor.
_BRONVELDEN = {"editie": "editie", "peildatum": "peildatum", "versie": "versie van", "opgehaald": "opgehaald op"}


def _bestand(tool: str, result: str) -> dict | None:
    """De `bron` van een tool die een bestand leest, met editie, peildatum en link naar het bestand."""
    if tool not in _BESTANDSBRONNEN:
        return None
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return None
    bron = parsed.get("bron") if isinstance(parsed, dict) else None
    return bron if isinstance(bron, dict) else None


def _met_hash(regel: str, result: str) -> str:
    """De bronregel van de Studiekeuzedatabase met de sha256 van de geladen export uit de store (#981): niet uit het
    toolresultaat, waar de cijferreeksen van een hash als bewijsgetal zouden gelden."""
    for key in stapkeys(result):
        if gevonden := studiekeuze.lading(store.meta(laadkey(key))):
            return studiekeuze.met_hash(regel, gevonden[1])
    return regel


def _bestandsbron(tool: str, result: str) -> list[Bronregel]:
    if (bron := _bestand(tool, result)) is None:
        return []
    if isinstance(regel := bron.get("regel"), str) and regel:
        # Een bron met een voorgeschreven bronregel (WOPI: "WOPI 2025, Universiteiten van Nederland, …", #936).
        return [(_met_hash(regel, result), None)]
    delen = [_BESTANDSBRONNEN[tool]]
    delen += [f"{woord} {bron[veld]}" for veld, woord in _BRONVELDEN.items() if bron.get(veld)]
    return [(", ".join(delen), None)]


def _stapbronnen(tool: str, result: str) -> list[Bronregel]:
    # Een tool met een eigen bronregel (WOPI, de financien) noemt haar bron zelf; haar tabel in de store (#956) geeft
    # geen tweede regel. Een selectie op die tabel heeft wel de regel uit de store.
    bestand = _bestandsbron(tool, result)
    datasets = [] if bestand else [bron for key in stapkeys(result) if (bron := _datasetbron(key))]
    # Een UWV- of ROA-resultaat van vóór #577 heeft geen tabel in de store: dan is zijn bron die van zijn
    # citaties (agent/meetwaarden.py), en zijn dataset die van de tool. Met een data_key staat de bron, met
    # peildatum of versie, al in `datasets`. Een tool met een eigen bronregel (het collegegeld, #970) heeft die al.
    buiten_de_store = [
        (w.bron, DATASET.get(tool)) for w in meetwaarden(result, tool) if w.bron and not w.data_key and not bestand
    ]
    return datasets + buiten_de_store + _registerbron(tool, result) + bestand


def _bronregels(steps: list[tuple[str, str]]) -> dict[str, str | None]:
    """Elke bronregel één keer, in volgorde van eerste gebruik, met de dataset van dat eerste gebruik."""
    regels: dict[str, str | None] = {}
    for tool, result in steps:
        for tekst, dataset in _stapbronnen(tool, result):
            regels.setdefault(tekst, dataset)
    return regels


def bronnen_van(steps: list[tuple[str, str]]) -> list[str]:
    """Elke geladen dataset en elke bron buiten de store één keer, in volgorde van eerste gebruik.

    Leeg als de beurt geen data las. Alleen de stappen tellen, niet wat het model schreef.
    """
    return list(_bronregels(steps))


def bronlinks_van(steps: list[tuple[str, str]]) -> dict[str, str]:
    """Bronregel → link naar de bronpagina (#621), voor dezelfde stappen en regels als `bronnen_van`.

    De link is de documentatie-URL van de dataset in de catalogus, alleen als http(s)-adres. Een regel
    zonder dataset die de catalogus kent, of zonder zo'n link, staat er niet in: die blijft tekst, geen gok.
    """
    links = {
        tekst: url for tekst, dataset in _bronregels(steps).items() if dataset and (url := documentatie_url(dataset))
    }
    # Het Inspectie-oordeel, de mbo-indicatoren en het collegegeld staan niet in de catalogus: hun link is het bestand of
    # de wettekst zelf (#749, #727, #729).
    for tool, result in steps:
        bron, regels = _bestand(tool, result), _bestandsbron(tool, result)
        if bron and regels and str(bron.get("url") or "").startswith("https://"):
            links.setdefault(regels[0][0], str(bron["url"]))
    return links


# --- een vervolgantwoord zonder eigen datastap (#975) ---

# Hoe een antwoord een bron voluit noemt, naast haar label (DUO, CBS, SKDB) en dataset-ID: haar leverancier en de
# termen die alleen zij heeft. Een antwoord over een koppeling met de Studiekeuzedatabase noemde "NSE-oordeel" en geen
# van haar namen (#986).
_LEVERANCIERS = {
    "skdb": (
        studiekeuze.BRONNAAM,
        "LCSK",
        "NSE",
        "Nationale Studenten Enquête",
        "Studentenenquête",
        "numerus fixus",
        "studiekeuze",
    ),
    "unl": (wo_personeel.BRONNAAM, "WOPI"),
}


def _namen(known: KeyMeta) -> list[str]:
    """Waaraan een antwoord een geladen dataset herkent: bronlabel, dataset-ID, catalogustitel en leverancier."""
    namen = [known.bron, str(known.dataset).rsplit(":", 1)[-1], *_LEVERANCIERS.get(known.bron, ())]
    if (titel := bron_titel(str(known.dataset))) != known.dataset:
        namen.append(titel)
    return namen


def _noemt(tekst: str, naam: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(naam)}(?!\w)", tekst, re.IGNORECASE) is not None


def koppeling(key: str) -> list[KeyMeta]:
    """De geladen tabellen waar `key` uit bestaat, met hun meta: bij een koppeling elke tabel die ze las, ook een die de
    store intussen kwijt is (store.bronnen, #985); bij een geladen tabel die tabel zelf. Een koppeling is een geheel."""
    return [known for _, known in store.bronnen(key)]


def _genoemd(tekst: str, key: str, groep: list[KeyMeta]) -> bool:
    """Noemt het antwoord de key of een van de tabellen waar hij uit bestaat?"""
    metas = [known for known in (store.meta(key), *groep) if known]
    return any(_noemt(tekst, naam) for known in metas for naam in _namen(known))


def _eerdere_bronregels(tekst: str, keys: list[str]) -> dict[str, str | None]:
    regels: dict[str, str | None] = {}
    for key in keys:
        if _genoemd(tekst, key, groep := koppeling(key)):
            for known in groep:
                regels.setdefault(*_metabron(known))
    return regels


def vervolgbronnen(tekst: str, keys: list[str]) -> tuple[list[str], dict[str, str]]:
    """De bronregels en hun links voor een antwoord zonder eigen datastap: van de eerder geladen datasets die het noemt.

    Review 08-C2: na een koppeling van de Studiekeuzedatabase aan DUO vroeg de gebruiker welke sleutels de koppeling
    gebruikte. Het antwoord besprak de analyse en noemde LCSK, maar de beurt las niets, dus de bronlijst bleef leeg: geen
    versie, geen verplichte zin van LCSK. `keys` zijn de keys van de vorige beurt die data laadde
    (session_data.vorige_databeurt); een dataset telt mee als het antwoord hem noemt, met zijn bronlabel, dataset-ID,
    catalogustitel, leverancier of een term die alleen die bron heeft ("NSE", "numerus fixus"). Dat vraagt de prompt bij
    elke claim met data. Een losse vraag die geen bron noemt, krijgt geen bronregel. Een koppeling telt als geheel (#986):
    noemt het antwoord een van haar tabellen, dan krijgt het de regels van alle, want "NSE-oordeel, BRIN en DUO" rust ook
    op de Studiekeuzedatabase. De regel komt uit de meta in de store, ook van een tabel die de store intussen kwijt is,
    dus met de versie en de verplichte zin van LCSK (studiekeuze._bewaar).
    """
    regels = _eerdere_bronregels(tekst, keys)
    links = {regel: url for regel, dataset in regels.items() if dataset and (url := documentatie_url(dataset))}
    return list(regels), links


def zonder_bronnensectie(tekst: str) -> str:
    """Het antwoord zonder de eigen Bronnen-sectie van het model."""
    return _EIGEN_BRONNEN.sub(_zonder_sectie, tekst)


def zonder_eigen_bronnen(tekst: str, bronnen: list[str]) -> str:
    """Het antwoord zonder de eigen Bronnen-sectie van het model, als de app de bronnen zelf geeft."""
    return zonder_bronnensectie(tekst) if bronnen else tekst


def buiten_bronnensectie(tekst: str, omzetten: Callable[[str], str]) -> str:
    """`omzetten` op het antwoord, niet op de eigen Bronnen-sectie van het model: een brontitel is een citaat."""
    stukken, vorige = [], 0
    for sectie in _EIGEN_BRONNEN.finditer(tekst):
        stukken += [omzetten(tekst[vorige : sectie.start()]), sectie.group(0)]
        vorige = sectie.end()
    return "".join([*stukken, omzetten(tekst[vorige:])])
