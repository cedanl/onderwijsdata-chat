"""Inspectie-oordelen per mbo-bestuur, uit de open data van de Onderwijsinspectie (#749, onderzoek #722).

De Inspectie publiceert per schooljaar elke maand een peilbestand per bevoegd gezag
(`<peildatum>-oordeel-en-standaard-bg.ods`, CC0 1.0). Mbo staat daarin bij de besturen waarvan
`SectorenBijBestuur` MBO noemt: op 1 oktober 2026 164 van de 1392, van wie 126 alleen mbo hebben en 38 ook po, vo
of ho (gemengd). Het oordeel geldt per bestuur, niet per instelling of opleiding; bij een gemengd bestuur gaat het
niet vanzelf over het mbo-deel.

De bestandsnaam en het document-ID wisselen per maand. Daarom volgt de code de pagina's: het overzicht, de nieuwste
schooljaarpagina met een document, het nieuwste document, en daarin het bg-bestand. Een ODS-bestand is een zip met
XML: de standaardbibliotheek leest het, zonder ODF-engine. Het bestuursnummer staat als formuletekst met nullen
(`="00008"`); DUO's `BEVOEGD GEZAG NUMMER` is een getal. Beide gaan naar int.

Welke kolommen de standaarden van een bestuur zijn, hangt af van het onderzoekskader in de kolom `Kader` (#874): zie
`KADERS` hieronder, met de bron van de namen.
"""

from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from xml.etree import ElementTree

import httpx

from data import instellingen
from data.instellingen import get_adres_lookup

from . import fouten

logger = logging.getLogger(__name__)

BASIS = "https://www.onderwijsinspectie.nl"
OVERZICHT = f"{BASIS}/trends-en-ontwikkelingen/onderwijsdata/oordelen"
LICENTIE = "CC0 1.0 Universal (publiek domein)"
_TIMEOUT_S = 60
# De site weigert geen gewone client, maar een herkenbare naam maakt het verkeer bij de Inspectie terug te vinden.
_HEADERS = {"User-Agent": "openEDUdata+ (onderwijsdata-chat)"}

_JAARPAGINA = re.compile(r'href="(/trends-en-ontwikkelingen/onderwijsdata/oordelen/oordelen-(20\d{2})-20\d{2})"')
_DOCUMENT = re.compile(r'href="(/documenten/(\d{4})/(\d{2})/(\d{2})/oordelen-[^"]+)"')
_BG_ODS = re.compile(r'href="([^"]*-oordeel-en-standaard-bg\.ods)"')

_ODS_TABEL = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_ODS_OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
_ODS_TEKST = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"
# Lege staartcellen en -rijen staan in ODS als "herhaal 16384 keer".
_MAX_HERHALING = 1000

MBO = "MBO"

# Welke kolommen bij welk onderzoekskader horen, en hoe de standaarden heten (#874). De namen komen uit de variabelenlijst
# van het bg-bestand in de "Toelichting open data oordelen en standaarden 2025/2026" van de Inspectie (september 2025,
# p. 12-13), geraadpleegd op 02-11-2026:
# https://www.onderwijsinspectie.nl/site/binaries/site-content/collections/documents/2025/09/02/toelichting-open-data-oordelen-en-standaarden-2025-2026/Toelichting_open_data_oordelen_en_standaarden_2025_2026.pdf
# BKA1-3 staan met dezelfde namen in het Onderzoekskader 2021 voor het mbo, versie 2026, p. 29, geraadpleegd op
# 02-11-2026:
# https://www.onderwijsinspectie.nl/site/binaries/site-content/collections/documents/2021/07/01/onderzoekskader-2021-middelbaar-beroepsonderwijs/kader-mbo-2026.pdf
#
# - FinancieelBeheer, KwaliteitszorgEnAmbitie en Onderwijsresultaten zijn oordelen per kwaliteitsgebied (toelichting
#   p. 11-12); Onderwijsresultaten krijgen alleen samenwerkingsverbanden passend onderwijs.
# - BST2017 (onderzoekskader 2017): de standaarden KA1-3 onder Kwaliteitszorg en ambitie en FB1-3 onder Financieel
#   beheer. Dat de BST-sets uit de kaders 2017 en 2021 komen, staat in de "Toelichting open data standaarden schooljaar
#   2021/2022" (p. 12); in het peilbestand van 01-10-2026 zijn alle BST2017-vaststellingen van 17-11-2017 tot
#   21-09-2021.
# - BST2021 (onderzoekskader 2021): één kwaliteitsgebied, Besturing, kwaliteitszorg en ambitie, met BKA1-3; het
#   financieel beheer valt daaronder (kader mbo, p. 28). Het eindoordeel staat in Eindoordeel.
# - BST21_V25: de toelichting noemt de code niet. Het is het kader 2021 in de jaarversie van 2025: dezelfde kolommen
#   BKA1-3, en in het peilbestand van 01-10-2026 zijn alle 86 vaststellingen van 10-11-2025 of later (de versie 2025
#   gold vanaf 1 augustus 2025; vergelijk PO2021_V23 in de toelichting).
# - OR1 en RPO1-3 zijn standaarden van samenwerkingsverbanden (BSTSWV2021), geen mbo-besturen.
# - Een leeg Kader zijn "oudere onderzoeken (voor 2021)" (toelichting p. 12): geen standaarden, wel kwaliteitsgebieden.
KWALITEITSGEBIEDEN = {  # kolom → naam van het kwaliteitsgebied
    "FinancieelBeheer": "Financieel beheer",
    "KwaliteitszorgEnAmbitie": "Kwaliteitszorg en ambitie",
    "Onderwijsresultaten": "Onderwijsresultaten",
}


@dataclass(frozen=True)
class Kader:
    naam: str
    standaarden: dict[str, str]  # kolom → naam van de standaard


_KADER_2017 = Kader(
    "Onderzoekskader 2017",
    {
        "KA1": "Kwaliteitszorg",
        "KA2": "Kwaliteitscultuur",
        "KA3": "Verantwoording en dialoog",
        "FB1": "Continuïteit",
        "FB2": "Doelmatigheid",
        "FB3": "Rechtmatigheid",
    },
)
_KADER_2021 = Kader(
    "Onderzoekskader 2021",
    {
        "BKA1": "Visie, ambities en doelen",
        "BKA2": "Uitvoering en kwaliteitscultuur",
        "BKA3": "Evaluatie, verantwoording en dialoog",
    },
)
# De waarden van de kolom Kader bij mbo-besturen.
KADERS = {"BST2017": _KADER_2017, "BST2021": _KADER_2021, "BST21_V25": _KADER_2021}

# Elke kolom van het bg-bestand (toelichting p. 10-13, kop van het peilbestand van 01-10-2026). Een kolom die hier niet
# staat, is nieuw bij de Inspectie: misschien een nieuwe standaard die de tool nog niet leest.
_SWV_STANDAARDEN = {"OR1", "RPO1", "RPO2", "RPO3"}
_GEGEVENS = {"Peildatum", "Bestuursnummer", "Bestuursnaam", "SectorenBijBestuur", "Eindoordeel", "Kader"}
_FINANCIEEL = {"FinancielePositie"}
# Bij elk oordeel (eind, financieel, kwaliteitszorg en ambitie, onderwijsresultaten) vier kolommen over het onderzoek.
_ONDERZOEK = {
    f"{veld}{oordeel}"
    for veld in ("Vaststellingsdatum", "Publicatiedatum", "Onderzoeksnummer", "TypeOnderzoekCode")
    for oordeel in ("Eindoordeel", "Financieel", "KwAmb", "Onderwijsres")
}
BEKENDE_KOLOMMEN = frozenset(
    _GEGEVENS
    | _FINANCIEEL
    | _ONDERZOEK
    | set(KWALITEITSGEBIEDEN)
    | {kolom for kader in KADERS.values() for kolom in kader.standaarden}
    | _SWV_STANDAARDEN
)


class InspectieOnbereikbaar(RuntimeError):
    """De pagina's leiden niet naar een bg-bestand, of een bestand is niet te lezen."""


@dataclass(frozen=True)
class Peilbestand:
    url: str
    peildatum: str  # zoals de Inspectie hem schrijft: 01-10-2026
    rijen: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Oordeel:
    bestuursnummer: int
    bestuursnaam: str
    sectoren: tuple[str, ...]
    eindoordeel: str | None
    vastgesteld: str | None
    kader: str | None  # de code uit de kolom Kader, bijvoorbeeld BST2021; None bij een leeg Kader
    kwaliteitsgebieden: dict[str, str]
    standaarden: dict[str, str]
    peildatum: str
    url: str

    @property
    def gemengd(self) -> bool:
        """Heeft het bestuur ook po, vo of ho? Dan gaat het oordeel over het hele bestuur, niet alleen over mbo."""
        return set(self.sectoren) != {MBO}


def bestuursnummer(waarde) -> int | None:
    """Het bestuursnummer als int: `="00008"`, `00008`, 8 en 8.0 zijn hetzelfde; None als het geen nummer is."""
    if isinstance(waarde, bool) or waarde is None:
        return None
    if isinstance(waarde, int):
        return waarde
    if isinstance(waarde, float):
        return int(waarde) if waarde.is_integer() else None
    tekst = re.sub(r'[="\'\s]', "", str(waarde))
    tekst = tekst.removesuffix(".0")
    return int(tekst) if tekst.isdigit() else None


def datum(waarde) -> str | None:
    """Een datum van de Inspectie (20230906) als 06-09-2023; een andere vorm blijft zoals hij is."""
    tekst = str(waarde or "").strip()
    if re.fullmatch(r"\d{8}", tekst):
        return f"{tekst[6:]}-{tekst[4:6]}-{tekst[:4]}"
    return tekst or None


def sectoren(waarde) -> tuple[str, ...]:
    """`VO-MBO` → ("VO", "MBO")."""
    return tuple(s for s in re.split(r"[-,/\s]+", str(waarde or "").upper()) if s)


def _cel(cel) -> str:
    waarde = cel.get(_ODS_OFFICE + "value") or cel.get(_ODS_OFFICE + "date-value")
    if waarde is not None:
        return waarde
    return "\n".join("".join(p.itertext()) for p in cel.iter(_ODS_TEKST))


def rijwaarden(rij: ElementTree.Element) -> list[str]:
    """De celwaarden van één ODS-rij, met herhaalde cellen uitgeschreven en zonder lege staart."""
    waarden: list[str] = []
    for cel in rij:
        if cel.tag in (_ODS_TABEL + "table-cell", _ODS_TABEL + "covered-table-cell"):
            waarden += [_cel(cel)] * min(int(cel.get(_ODS_TABEL + "number-columns-repeated", "1")), _MAX_HERHALING)
    while waarden and not waarden[-1]:
        waarden.pop()
    return waarden


def lees_ods(inhoud: bytes) -> list[dict]:
    """De rijen van het eerste blad als dicts, met de eerste rij als kop."""
    try:
        with zipfile.ZipFile(io.BytesIO(inhoud)) as z:
            wortel = ElementTree.fromstring(z.read("content.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as e:
        raise InspectieOnbereikbaar(f"het bg-bestand is geen leesbaar ODS-bestand ({type(e).__name__})") from e
    blad = next(wortel.iter(_ODS_TABEL + "table"), None)
    if blad is None:
        return []
    tabel: list[list[str]] = []
    for rij in blad.iter(_ODS_TABEL + "table-row"):
        if waarden := rijwaarden(rij):
            tabel += [waarden] * min(int(rij.get(_ODS_TABEL + "number-rows-repeated", "1")), _MAX_HERHALING)
    if not tabel:
        return []
    kop, *rest = tabel
    return [dict(zip(kop, [*rij, *[""] * (len(kop) - len(rij))], strict=False)) for rij in rest]


def _haal(client: httpx.Client, url: str) -> httpx.Response:
    antwoord = client.get(url if url.startswith("http") else BASIS + url)
    antwoord.raise_for_status()
    return antwoord


def bestand_url(client: httpx.Client, bestand: re.Pattern[str], naam: str) -> str:
    """De URL van het nieuwste bestand van deze soort: nieuwste schooljaar met een document, nieuwste document, en
    daarin het bestand. Elk document heeft het bg-bestand en het po-so-vo-bestand (#881)."""
    overzicht = _haal(client, OVERZICHT).text
    jaren = sorted({(int(jaar), pad) for pad, jaar in _JAARPAGINA.findall(overzicht)}, reverse=True)
    for _, pad in jaren[:2]:  # het nieuwe schooljaar kan nog zonder document zijn
        documenten = sorted({(d[1:], d[0]) for d in _DOCUMENT.findall(_haal(client, pad).text)}, reverse=True)
        for _, document in documenten:
            if gevonden := bestand.search(_haal(client, document).text):
                return gevonden.group(1)
    raise InspectieOnbereikbaar(f"geen {naam}-bestand gevonden via de schooljaarpagina's van de Inspectie")


def _bg_url(client: httpx.Client) -> str:
    return bestand_url(client, _BG_ODS, "bg")


def haal_ods(vind_url: Callable[[httpx.Client], str], client: httpx.Client | None = None) -> tuple[str, list[dict]]:
    """De URL en de rijen van het bestand dat `vind_url` aanwijst; zonder `client` een eigen verbinding met timeout
    en herkenbare naam. Gedeeld met de vo-oordelen (`tools.inspectie_vo`, #881)."""
    eigen = client is None
    client = client or httpx.Client(headers=_HEADERS, timeout=_TIMEOUT_S, follow_redirects=True)
    try:
        url = vind_url(client)
        return url, lees_ods(_haal(client, url).content)
    except httpx.HTTPError as e:
        raise InspectieOnbereikbaar(f"de Inspectie antwoordde niet ({type(e).__name__})") from e
    finally:
        if eigen:
            client.close()


def peildatum_van(rijen: list[dict]) -> str:
    """De peildatum zoals de Inspectie hem schrijft (01-10-2026): de eerste gevulde in het bestand."""
    return str(next((r["Peildatum"] for r in rijen if r.get("Peildatum")), ""))


def haal_peilbestand(client: httpx.Client | None = None) -> Peilbestand:
    """Het nieuwste bg-bestand, gelezen."""
    url, rijen = haal_ods(_bg_url, client)
    meld_onbekend(rijen)
    return Peilbestand(url, peildatum_van(rijen), rijen)


def _is_mbo(rij: dict) -> bool:
    return MBO in sectoren(rij.get("SectorenBijBestuur"))


def _kadercode(rij: dict) -> str | None:
    return str(rij.get("Kader") or "").strip() or None


def meld_onbekend(rijen: list[dict]) -> None:
    """Log een nieuwe kolom of een onbekend kader bij een mbo-bestuur, in plaats van die stil over te slaan (#874).

    Eén keer per opgehaald bestand (dus per dag): de standaarden van zo'n kader toont de tool niet, en wie het log leest,
    weet dan dat `KADERS` of `BEKENDE_KOLOMMEN` bij moet.
    """
    if nieuw := sorted(set(rijen[0] if rijen else ()) - BEKENDE_KOLOMMEN):
        logger.warning("INSPECTIE_KADER_ONBEKEND kolommen=%s", ",".join(nieuw))
    onbekend: dict[str, int] = {}
    for rij in rijen:
        if _is_mbo(rij) and (code := _kadercode(rij)) is not None and code not in KADERS:
            onbekend[code] = onbekend.get(code, 0) + 1
    for code, aantal in sorted(onbekend.items()):
        logger.warning("INSPECTIE_KADER_ONBEKEND kader=%s besturen=%d", code, aantal)


@lru_cache(maxsize=1)
def _peilbestand_van(dag: str) -> Peilbestand:
    return haal_peilbestand()


def peilbestand() -> Peilbestand:
    """Het nieuwste bestand, één keer per dag opgehaald: de Inspectie publiceert maandelijks."""
    return _peilbestand_van(date.today().isoformat())


def _gevuld(rij: dict, namen_per_kolom: dict[str, str]) -> dict[str, str]:
    """{naam: waarde} voor de kolommen die in deze rij een waarde hebben."""
    return {naam: w for kolom, naam in namen_per_kolom.items() if (w := str(rij.get(kolom) or "").strip())}


def _standaarden_van(rij: dict) -> dict[str, str]:
    """De standaarden van het kader van deze rij, met hun naam; leeg bij een leeg of onbekend kader."""
    kader = KADERS.get(_kadercode(rij) or "")
    return _gevuld(rij, kader.standaarden) if kader else {}


def oordelen_mbo(bestand: Peilbestand) -> dict[int, Oordeel]:
    """Per bestuursnummer het oordeel van de besturen waarvan de sectoren MBO noemen."""
    uit: dict[int, Oordeel] = {}
    for rij in bestand.rijen:
        nummer = bestuursnummer(rij.get("Bestuursnummer"))
        if nummer is None or not _is_mbo(rij):
            continue
        uit[nummer] = Oordeel(
            bestuursnummer=nummer,
            bestuursnaam=str(rij.get("Bestuursnaam") or "").strip(),
            sectoren=sectoren(rij.get("SectorenBijBestuur")),
            eindoordeel=str(rij.get("Eindoordeel") or "").strip() or None,
            vastgesteld=datum(rij.get("VaststellingsdatumEindoordeel")),
            kader=_kadercode(rij),
            kwaliteitsgebieden=_gevuld(rij, KWALITEITSGEBIEDEN),
            standaarden=_standaarden_van(rij),
            peildatum=str(rij.get("Peildatum") or bestand.peildatum),
            url=bestand.url,
        )
    return uit


def bestuur_van(instellingscode: str) -> int | None:
    """Het bestuursnummer (BEVOEGD GEZAG NUMMER) van een instelling volgens DUO's adressenbestand; None zonder."""
    return (get_adres_lookup().get(str(instellingscode or "").strip()) or {}).get("bevoegd_gezag")


def oordeel_voor_instelling(instellingscode: str, bestand: Peilbestand | None = None) -> Oordeel | None:
    """Het oordeel van het bestuur van een mbo-instelling; None als de instelling of het bestuur er niet in staat."""
    nummer = bestuur_van(instellingscode)
    if nummer is None:
        return None
    return oordelen_mbo(bestand or peilbestand()).get(nummer)


BRONNAAM = "Onderwijsinspectie"
BRONTITEL = "Oordelen per bevoegd gezag"
_GEEN_EINDOORDEEL = {None, "Geen eindoordeel"}
_SECTORNAMEN = {"PO": "po", "VO": "vo", "MBO": "mbo", "HO": "ho", "SO": "so"}


def _kader(code: str | None) -> dict | None:
    """Het onderzoekskader in de uitkomst: standaarden uit verschillende kaders zijn niet te vergelijken (#874)."""
    if code is None:
        return None
    if (kader := KADERS.get(code)) is None:
        return {"code": code, "naam": None}
    return {
        "code": code,
        "naam": kader.naam,
        "betekenis": f"Beoordeeld volgens het {kader.naam}. Standaarden uit verschillende onderzoekskaders zijn niet "
        "met elkaar te vergelijken.",
    }


def _uitkomst(inst: dict, o: Oordeel) -> dict:
    uit: dict = {
        "instelling": {"naam": inst["naam"], "instellingscode": inst["instellingscode"]},
        "bestuur": {
            "naam": o.bestuursnaam,
            "nummer": o.bestuursnummer,
            "sectoren": [_SECTORNAMEN.get(s, s) for s in o.sectoren],
        },
        "eindoordeel": o.eindoordeel,
        "vastgesteld": o.vastgesteld,
        "kader": _kader(o.kader),
        "kwaliteitsgebieden": o.kwaliteitsgebieden,
        "standaarden": o.standaarden,
        "peildatum": o.peildatum,
        "gemengd": o.gemengd,
        "betekenis": "Het oordeel geldt per bestuur (bevoegd gezag), niet per instelling, vestiging of opleiding.",
        "bron": {"naam": f"{BRONNAAM}, {BRONTITEL}", "url": o.url, "licentie": LICENTIE, "peildatum": o.peildatum},
    }
    noten = []
    if o.gemengd:
        andere = ", ".join(_SECTORNAMEN.get(s, s) for s in o.sectoren if s != MBO)
        noten.append(
            f"Het bestuur heeft naast mbo ook {andere}: het oordeel geldt voor het hele bestuur, niet alleen voor het "
            "mbo-deel. Zeg dat in het antwoord."
        )
    if o.eindoordeel in _GEEN_EINDOORDEEL:
        noten.append("De Inspectie gaf dit bestuur (nog) geen eindoordeel: noem geen oordeel en schat er geen.")
    if o.kader is not None and o.kader not in KADERS:
        noten.append(
            f"Het onderzoekskader {o.kader} kent deze app niet: de standaarden van dit bestuur zijn niet getoond. Noem "
            "geen standaarden en schat er geen."
        )
    if noten:
        uit["noot"] = " ".join(noten)
    return uit


def get_inspectieoordeel(instelling: str) -> str:
    """Het Inspectie-oordeel van het bestuur van een mbo-instelling, met peildatum en bron (#749)."""
    profiel = instellingen.instellingsprofiel(str(instelling or ""))
    if profiel is None:
        return (
            f"Onbekende instelling {instelling!r}: het register kent deze naam of alias niet. Geen gok; controleer de "
            "naam, bijvoorbeeld met get_rio_instelling."
        )
    if profiel.get("sector") != "mbo":
        return (
            f"{profiel['naam']} is een {profiel.get('sector')}-instelling. De Inspectie geeft het hoger onderwijs geen "
            "oordeel per bestuur: de kwaliteit van hbo- en wo-opleidingen beoordeelt de NVAO. De accreditatiedatums per "
            "opleiding staan in get_accreditatie (DUO); de NVAO-oordelen zelf zitten (nog) niet in deze app."
        )
    try:
        bestand = peilbestand()
    except InspectieOnbereikbaar as e:
        oorzaak = e.__cause__ if isinstance(e.__cause__, Exception) else e
        return fouten.bronfout(BRONNAAM, oorzaak, f" Instelling '{profiel['naam']}'.")
    oordeel = oordeel_voor_instelling(profiel["instellingscode"], bestand)
    if oordeel is None:
        return (
            f"Voor {profiel['naam']} ({profiel['instellingscode']}) staat geen bestuur met mbo in het peilbestand van "
            f"de Inspectie van {bestand.peildatum}. Noem geen oordeel."
        )
    return json.dumps(_uitkomst(profiel, oordeel), ensure_ascii=False, separators=(",", ":"))
