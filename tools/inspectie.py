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
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from xml.etree import ElementTree

import httpx

from data import instellingen
from data.instellingen import get_adres_lookup

from . import fouten

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
# De standaarden op bestuursniveau, met hun kolom in het bestand.
STANDAARDEN = {
    "Financieel beheer": "FinancieelBeheer",
    "Kwaliteitszorg en ambitie": "KwaliteitszorgEnAmbitie",
    "Onderwijsresultaten": "Onderwijsresultaten",
}


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
        waarden: list[str] = []
        for cel in rij:
            if cel.tag in (_ODS_TABEL + "table-cell", _ODS_TABEL + "covered-table-cell"):
                waarden += [_cel(cel)] * min(int(cel.get(_ODS_TABEL + "number-columns-repeated", "1")), _MAX_HERHALING)
        while waarden and not waarden[-1]:
            waarden.pop()
        if waarden:
            tabel += [waarden] * min(int(rij.get(_ODS_TABEL + "number-rows-repeated", "1")), _MAX_HERHALING)
    if not tabel:
        return []
    kop, *rest = tabel
    return [dict(zip(kop, [*rij, *[""] * (len(kop) - len(rij))], strict=False)) for rij in rest]


def _haal(client: httpx.Client, url: str) -> httpx.Response:
    antwoord = client.get(url if url.startswith("http") else BASIS + url)
    antwoord.raise_for_status()
    return antwoord


def _bg_url(client: httpx.Client) -> str:
    """De URL van het nieuwste bg-bestand: nieuwste schooljaar met een document, nieuwste document, bg-bestand."""
    overzicht = _haal(client, OVERZICHT).text
    jaren = sorted({(int(jaar), pad) for pad, jaar in _JAARPAGINA.findall(overzicht)}, reverse=True)
    for _, pad in jaren[:2]:  # het nieuwe schooljaar kan nog zonder document zijn
        documenten = sorted({(d[1:], d[0]) for d in _DOCUMENT.findall(_haal(client, pad).text)}, reverse=True)
        for _, document in documenten:
            if gevonden := _BG_ODS.search(_haal(client, document).text):
                return gevonden.group(1)
    raise InspectieOnbereikbaar("geen bg-bestand gevonden via de schooljaarpagina's van de Inspectie")


def haal_peilbestand(client: httpx.Client | None = None) -> Peilbestand:
    """Het nieuwste bg-bestand, gelezen; zonder `client` een eigen verbinding met timeout en herkenbare naam."""
    eigen = client is None
    client = client or httpx.Client(headers=_HEADERS, timeout=_TIMEOUT_S, follow_redirects=True)
    try:
        url = _bg_url(client)
        rijen = lees_ods(_haal(client, url).content)
    except httpx.HTTPError as e:
        raise InspectieOnbereikbaar(f"de Inspectie antwoordde niet ({type(e).__name__})") from e
    finally:
        if eigen:
            client.close()
    peildatum = str(next((r["Peildatum"] for r in rijen if r.get("Peildatum")), ""))
    return Peilbestand(url, peildatum, rijen)


@lru_cache(maxsize=1)
def _peilbestand_van(dag: str) -> Peilbestand:
    return haal_peilbestand()


def peilbestand() -> Peilbestand:
    """Het nieuwste bestand, één keer per dag opgehaald: de Inspectie publiceert maandelijks."""
    return _peilbestand_van(date.today().isoformat())


def oordelen_mbo(bestand: Peilbestand) -> dict[int, Oordeel]:
    """Per bestuursnummer het oordeel van de besturen waarvan de sectoren MBO noemen."""
    uit: dict[int, Oordeel] = {}
    for rij in bestand.rijen:
        nummer = bestuursnummer(rij.get("Bestuursnummer"))
        sector = sectoren(rij.get("SectorenBijBestuur"))
        if nummer is None or MBO not in sector:
            continue
        uit[nummer] = Oordeel(
            bestuursnummer=nummer,
            bestuursnaam=str(rij.get("Bestuursnaam") or "").strip(),
            sectoren=sector,
            eindoordeel=str(rij.get("Eindoordeel") or "").strip() or None,
            vastgesteld=datum(rij.get("VaststellingsdatumEindoordeel")),
            standaarden={naam: w for naam, kolom in STANDAARDEN.items() if (w := str(rij.get(kolom) or "").strip())},
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
            "oordeel per bestuur: de kwaliteit van hbo- en wo-opleidingen beoordeelt de NVAO, en die bron zit niet in "
            "deze app."
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
