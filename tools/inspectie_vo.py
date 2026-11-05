"""Inspectieoordelen van vo-scholen, als vo-context voor vervolgonderwijs (#881, vervolg op #877).

De Inspectie publiceert naast het bg-bestand (`tools.inspectie`, mbo) elke maand een peilbestand per school en
onderwijssoort voor po, so en vo (`<peildatum>-oordeel-en-standaard-po-so-vo.ods`, CC0 1.0), in hetzelfde document. Bij
vo is het object van toezicht de onderwijssoort op één vestiging (`Elementtype` ODS): het oordeel geldt voor de havo-
of vwo-afdeling van die vestiging, niet voor de school als geheel en niet voor het bestuur. Zie de "Toelichting open
data oordelen en standaarden 2025/2026", p. 4-6.

Het bestand noemt geen plaats en geen schoolnaam. Die komen uit DUO's adressen van vestigingen in het vo
(`adressen_vo`, de vestigingscode is BRIN + vestigingsnummer); de tool gebruikt alleen code, naam, plaats en gemeente.

De tool staat achter de vo-contextpoort van de beurt (`ho_markers.vo_deel_poort`): de vraag van de gebruiker opent de
vo-context en noemt zelf een vo-niveau, zonder po of (v)so. Code beslist dat, niet het model. Daarna filtert de code de
rijen op vo: po en so (en een speciale school onder vo) komen nooit in het resultaat, ook al staan ze in het bestand.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import httpx
from onderwijsbronnen import duo

from . import fouten, ho_markers, inspectie, scopeprofiel
from .schemas import TOOL_GET_INSPECTIEOORDEEL

logger = logging.getLogger(__name__)

BRONTITEL = "Oordelen per school (po/so/vo)"
ETIKET = f"{scopeprofiel.VO_CONTEXT_DEEL}: oordelen over afdelingen van vo-scholen, geen mbo- of ho-instellingen"

_PO_SO_VO_ODS = re.compile(r'href="([^"]*-oordeel-en-standaard-po-so-vo\.ods)"')
_VO = "VO"
_ONDERWIJSSOORT = "ODS"  # Elementtype: bij vo het object van toezicht (toelichting p. 5)
_SPECIALE_SCHOOL = "SPEC"  # TypeOVT: een speciale school onder vo is vso, en (v)so blijft dicht
# OVTNaam bij vo is de onderwijssoort; de sleutels zijn de waarden in het bestand van 01-11-2026.
ONDERWIJSSOORTEN = {
    "VMBOB": "vmbo-b",
    "VMBOK": "vmbo-k",
    "VMBOGT": "vmbo-gt",
    "HAVO": "havo",
    "VWO": "vwo",
    "PRO": "pro",
}
# Een vo-onderdeel van een mbo-instelling (toelichting p. 6): het oordeel gaat over dat vo-deel, niet over het mbo.
_VO_ONDERDEEL_VAN = {"ROCV": "een roc", "AOCV": "een aoc", "VAKV": "een vakcollege"}
# De waarden van KwaliteitOnderwijs (toelichting p. 5), in deze volgorde in de telling.
OORDELEN = ("Zeer zwak", "Zwak", "Onvoldoende", "Voldoende", "Goed", "Basistoezicht", "Geen eindoordeel")
_GEEN_EINDOORDEEL = "Geen eindoordeel"
# Zo veel vestigingen per resultaat, zodat het onder TOOL_RESULT_MAX_CHARS blijft (Amsterdam heeft er 91 met alle
# afdelingen samen); de telling telt altijd alle.
MAX_VESTIGINGEN = 25

_VESTIGINGEN = ("adressen_vo", "vestigingen")  # DUO: Adressen van vestigingen in het voortgezet onderwijs
_GEMEENTE_ALIASSEN = {"denhaag": "sgravenhage", "denbosch": "shertogenbosch"}

POORT_DICHT = (
    "Geen inspectieoordelen van vo-scholen bij deze vraag. De chat werkt voor mbo, hbo en wo; vo-scholen alleen als "
    "vo-context voor vervolgonderwijs, bij een vraag over doorstroom naar mbo, hbo of wo die zelf het vo noemt "
    "(vmbo, havo, vwo). Code beslist dat op de vraag van de gebruiker. Noem geen oordeel over een vo-school en schat er "
    f"geen; het oordeel over het bestuur van een mbo-instelling staat in {TOOL_GET_INSPECTIEOORDEEL}."
)


@dataclass(frozen=True)
class Afdeling:
    """Het oordeel over één onderwijssoort op één vo-vestiging."""

    vestiging: str  # BRIN + vestigingsnummer, zoals DUO's VESTIGINGSCODE: 24TR03
    onderwijssoort: str  # havo, vwo, vmbo-gt, ...
    oordeel: str
    vastgesteld: str | None
    onderdeel_van: str | None  # "een roc" bij een vo-onderdeel van een mbo-instelling


@dataclass(frozen=True)
class Vestiging:
    code: str
    naam: str
    plaats: str
    gemeente: str


def _po_so_vo_url(client: httpx.Client) -> str:
    return inspectie.bestand_url(client, _PO_SO_VO_ODS, "po-so-vo")


def _tekst(rij: dict, kolom: str) -> str:
    return str(rij.get(kolom) or "").strip()


def _is_vo_afdeling(rij: dict) -> bool:
    """Sector VO en een onderwijssoort als object van toezicht; nooit po, so of een speciale school onder vo."""
    return (
        _tekst(rij, "Sector").upper() == _VO
        and _tekst(rij, "Elementtype") == _ONDERWIJSSOORT
        and _tekst(rij, "TypeOVT") != _SPECIALE_SCHOOL
    )


def meld_onbekend(rijen: list[dict]) -> None:
    """Log een onbekende vo-onderwijssoort (`INSPECTIE_VO_ONBEKEND`), één keer per opgehaald bestand, in plaats van
    die stil over te slaan: dan moet ONDERWIJSSOORTEN bij."""
    onbekend = Counter(
        _tekst(r, "OVTNaam")
        for r in rijen
        if _is_vo_afdeling(r) and _tekst(r, "OVTNaam").upper() not in ONDERWIJSSOORTEN
    )
    for naam, aantal in sorted(onbekend.items()):
        logger.warning("INSPECTIE_VO_ONBEKEND onderwijssoort=%s afdelingen=%d", naam, aantal)


def haal_peilbestand_vo(client: httpx.Client | None = None) -> inspectie.Peilbestand:
    """Het nieuwste po-so-vo-bestand, gelezen; dezelfde weg als het bg-bestand (`inspectie.haal_ods`)."""
    url, rijen = inspectie.haal_ods(_po_so_vo_url, client)
    meld_onbekend(rijen)
    return inspectie.Peilbestand(url, inspectie.peildatum_van(rijen), rijen)


def afdelingen_vo(rijen: list[dict]) -> list[Afdeling]:
    """De vo-afdelingen met een bekende onderwijssoort; po- en so-rijen vallen hier weg, ook als het bestand ze heeft."""
    return [
        Afdeling(
            vestiging=f"{_tekst(rij, 'BRIN')}{_tekst(rij, 'Vestiging')}".upper(),
            onderwijssoort=ONDERWIJSSOORTEN[_tekst(rij, "OVTNaam").upper()],
            oordeel=_tekst(rij, "KwaliteitOnderwijs") or _GEEN_EINDOORDEEL,
            vastgesteld=inspectie.datum(rij.get("Vaststellingsdatum")),
            onderdeel_van=_VO_ONDERDEEL_VAN.get(_tekst(rij, "TypeOVT")),
        )
        for rij in rijen
        if _is_vo_afdeling(rij) and _tekst(rij, "OVTNaam").upper() in ONDERWIJSSOORTEN
    ]


def _sleutel(naam: str) -> str:
    """Spelling-onafhankelijk: 's-Gravenhage = S GRAVENHAGE, Súdwest-Fryslân = SUDWEST-FRYSLAN, Den Haag ook."""
    kaal = unicodedata.normalize("NFKD", str(naam)).encode("ascii", "ignore").decode().casefold()
    kaal = re.sub(r"[^a-z0-9]", "", kaal.removeprefix("gemeente "))
    return _GEMEENTE_ALIASSEN.get(kaal, kaal)


def lees_vestigingen() -> dict[str, Vestiging]:
    """DUO's vo-vestigingen per vestigingscode."""
    df = duo.load(*_VESTIGINGEN)
    uit: dict[str, Vestiging] = {}
    for rij in df.to_dict(orient="records"):
        code = str(rij.get("VESTIGINGSCODE") or "").strip().upper()
        if code:
            uit[code] = Vestiging(
                code=code,
                naam=str(rij.get("VESTIGINGSNAAM") or "").strip(),
                plaats=str(rij.get("PLAATSNAAM") or "").strip(),
                gemeente=str(rij.get("GEMEENTENAAM") or "").strip(),
            )
    return uit


@lru_cache(maxsize=1)
def _peilbestand_van(dag: str) -> inspectie.Peilbestand:
    return haal_peilbestand_vo()


@lru_cache(maxsize=1)
def _vestigingen_van(dag: str) -> dict[str, Vestiging]:
    return lees_vestigingen()


def peilbestand() -> inspectie.Peilbestand:
    """Het nieuwste po-so-vo-bestand, één keer per dag opgehaald, zoals het bg-bestand."""
    return _peilbestand_van(date.today().isoformat())


def vestigingen() -> dict[str, Vestiging]:
    """DUO's vo-vestigingen, één keer per dag opgehaald."""
    return _vestigingen_van(date.today().isoformat())


def _soorten(onderwijssoorten: list[str] | str | None) -> tuple[list[str], list[str]]:
    """De gevraagde onderwijssoorten in de spelling van de tool, en wat er niet bij hoort."""
    gevraagd = [onderwijssoorten] if isinstance(onderwijssoorten, str) else list(onderwijssoorten or [])
    bekend = {_sleutel(s): s for s in ONDERWIJSSOORTEN.values()}
    gekozen = [bekend[_sleutel(s)] for s in gevraagd if _sleutel(s) in bekend]
    return list(dict.fromkeys(gekozen)), [s for s in gevraagd if _sleutel(s) not in bekend]


def _telling(afdelingen: list[Afdeling]) -> dict[str, dict[str, int]]:
    """Per onderwijssoort het aantal afdelingen per oordeel, in de volgorde van ONDERWIJSSOORTEN en OORDELEN."""
    per_soort: dict[str, Counter[str]] = {}
    for a in afdelingen:
        per_soort.setdefault(a.onderwijssoort, Counter())[a.oordeel] += 1
    volgorde = {o: i for i, o in enumerate(OORDELEN)}
    return {
        soort: dict(sorted(per_soort[soort].items(), key=lambda kv: (volgorde.get(kv[0], len(OORDELEN)), kv[0])))
        for soort in ONDERWIJSSOORTEN.values()
        if soort in per_soort
    }


def _plaatsnaam(naam: str) -> str:
    """DUO schrijft hoofdletters zonder apostrof: S GRAVENHAGE wordt 's-Gravenhage."""
    return re.sub(r"^S ", "'s-", naam.title())


def _vestigingsregel(v: Vestiging, afdelingen: list[Afdeling]) -> dict:
    """Compact, want een grote gemeente heeft tientallen vestigingen: per afdeling "Voldoende (09-06-2026)"."""
    uit: dict = {
        "naam": v.naam,
        "vestiging": v.code,
        "plaats": _plaatsnaam(v.plaats),
        "afdelingen": {
            a.onderwijssoort: f"{a.oordeel} ({a.vastgesteld})" if a.vastgesteld else a.oordeel for a in afdelingen
        },
    }
    if onderdeel := afdelingen[0].onderdeel_van:
        uit["onderdeel_van"] = onderdeel
    return uit


def _noten(afdelingen: list[Afdeling], getoond: int, totaal: int) -> list[str]:
    noten = [
        "De bron zegt niet waar studenten vandaan komen: noem dit de vo-scholen in de gemeente, niet de scholen waar "
        "de studenten van een instelling vandaan komen."
    ]
    if onderdelen := sorted({a.onderdeel_van for a in afdelingen if a.onderdeel_van}):
        noten.append(
            f"Een of meer afdelingen zijn het vo-onderdeel van {' of '.join(onderdelen)}: dat oordeel gaat over het "
            "vo-deel, niet over het mbo. Zeg dat in het antwoord."
        )
    if all(a.oordeel == _GEEN_EINDOORDEEL for a in afdelingen):
        noten.append("Geen van deze afdelingen heeft een eindoordeel: noem geen oordeel en schat er geen.")
    if getoond < totaal:
        noten.append(
            f"Afgekapt: {getoond} van de {totaal} vestigingen staan erin, de telling telt alle {totaal}. Noem geen "
            "vestiging die er niet in staat; verfijn met onderwijssoorten."
        )
    return noten


def _uitkomst(gemeente: str, soorten: list[str], bestand: inspectie.Peilbestand, gevonden: list[tuple]) -> dict:
    """`gevonden`: (vestiging, haar afdelingen), alle vestigingen van de gemeente met een gevraagde afdeling."""
    alle = [a for _, afdelingen in gevonden for a in afdelingen]
    getoond = gevonden[:MAX_VESTIGINGEN]
    return {
        "gemeente": gemeente,
        "context": ETIKET,
        "onderwijssoorten": soorten or list(ONDERWIJSSOORTEN.values()),
        "peildatum": bestand.peildatum,
        "vestigingen_totaal": len(gevonden),
        "telling": _telling(alle),
        "vestigingen": [_vestigingsregel(v, afdelingen) for v, afdelingen in getoond],
        "betekenis": "Het oordeel geldt per onderwijssoort (afdeling) op één vestiging, niet voor de school als geheel "
        "en niet voor het bestuur; achter het oordeel staat de vaststellingsdatum. 'Geen eindoordeel' is geen onvoldoende: de afdeling is nog niet onderzocht, is "
        "gefuseerd of afgesplitst, of haar laatste oordeel Voldoende of Goed is ouder dan vier jaar. 'Basistoezicht' "
        "volgt vanzelf op een verlopen oordeel Goed.",
        "bron": {
            "naam": f"{inspectie.BRONNAAM}, {BRONTITEL}, {scopeprofiel.VO_CONTEXT_DEEL}",
            "url": bestand.url,
            "licentie": inspectie.LICENTIE,
            "peildatum": bestand.peildatum,
        },
        "noot": " ".join(_noten(alle, len(getoond), len(gevonden))),
    }


def _onbekende_gemeente(gemeente: str, alle: dict[str, Vestiging]) -> str:
    namen = sorted({v.gemeente for v in alle.values()})
    suggesties = difflib.get_close_matches(str(gemeente).upper(), namen, n=3, cutoff=0.7)
    hint = f" Bedoel je {', '.join(map(_plaatsnaam, suggesties))}?" if suggesties else ""
    return (
        f"Geen vo-vestiging in de gemeente {gemeente!r} volgens DUO (adressen van vestigingen in het vo).{hint} Geef de "
        "naam van een gemeente, geen plaats of regio, en noem geen oordeel."
    )


def get_inspectieoordeel_vo(gemeente: str, onderwijssoorten: list[str] | str | None = None) -> str:
    """De inspectieoordelen van de vo-afdelingen in één gemeente, als vo-context voor vervolgonderwijs (#881)."""
    if not ho_markers.vo_deel_poort():
        return POORT_DICHT
    soorten, onbekend = _soorten(onderwijssoorten)
    if onbekend:
        return (
            f"Onbekende onderwijssoort {', '.join(map(repr, onbekend))}: de tool kent alleen de vo-afdelingen "
            f"{', '.join(ONDERWIJSSOORTEN.values())}. Po en (v)so staan er bewust niet in."
        )
    try:
        bestand = peilbestand()
    except inspectie.InspectieOnbereikbaar as e:
        oorzaak = e.__cause__ if isinstance(e.__cause__, Exception) else e
        return fouten.bronfout(inspectie.BRONNAAM, oorzaak, f" Gemeente '{gemeente}'.")
    try:
        alle = vestigingen()
    except Exception as e:
        return fouten.bronfout("DUO", e, " Adressen van vestigingen in het vo.")
    sleutel = _sleutel(gemeente)
    in_gemeente = {code: v for code, v in alle.items() if _sleutel(v.gemeente) == sleutel}
    if not in_gemeente:
        return _onbekende_gemeente(gemeente, alle)
    per_vestiging: dict[str, list[Afdeling]] = {}
    for a in afdelingen_vo(bestand.rijen):
        if a.vestiging in in_gemeente and (not soorten or a.onderwijssoort in soorten):
            per_vestiging.setdefault(a.vestiging, []).append(a)
    if not per_vestiging:
        welke = f" {'/'.join(soorten)}" if soorten else ""
        return (
            f"In het peilbestand van de Inspectie van {bestand.peildatum} staat in de gemeente {gemeente} geen "
            f"vo-afdeling{welke}. Noem geen oordeel."
        )
    gevonden = sorted(
        ((in_gemeente[c], afd) for c, afd in per_vestiging.items()), key=lambda va: (va[0].naam.casefold(), va[0].code)
    )
    gemeentenaam = _plaatsnaam(next(iter(in_gemeente.values())).gemeente)
    return json.dumps(_uitkomst(gemeentenaam, soorten, bestand, gevonden), ensure_ascii=False, separators=(",", ":"))
