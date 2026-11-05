"""Het WOPI-personeelsbestand van UNL lezen uit de records van de draaitabellen, niet uit de getoonde cellen (#936).

UNL publiceert per editie één xlsx (`…WOPI_draaitabellen_tm_{jaar}.xlsx`) met 44 draaitabellen. Elke draaitabel heeft
een eigen cache (`xl/pivotCache/pivotCacheRecords*.xml`) met alle onderliggende records, met BRIN-code en vanaf 1998
(onderzoek 05-11 op #731). De getoonde cellen zijn een weergave: filters op wisselende rijen, verborgen jaren en een
rij "Totaal" die bij een kolomsom dubbel telt (116.924 in plaats van 58.462 fte). Daarom leest dit module alleen de
caches:

- een cache wordt gekozen op de naam van zijn brontabel (`dbPr/@command` in `xl/connections.xml`), nooit op zijn
  nummer: dat verschilt per editie;
- per tabel vier caches: zonder of met het HOOP-gebied Gezondheid (GEZO), en totaal of alleen vrouwen (achtervoegsel
  ` v` aan de naam);
- de velden van elke cache, de 14 BRIN-codes in het jongste jaar en het editiejaar worden gecontroleerd; wijkt er iets
  af, dan is dat een `WopiFout` en geen stille uitkomst.

Het bestand is extern, dus het XML gaat door `defusedxml`. Er staat geen data van UNL in deze repo: de tests gebruiken
een synthetisch bestand met dezelfde XML-vorm (`proefbestand`).
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
from defusedxml import ElementTree

from .._kern.versie import VERSIE

PAGINA = "https://www.universiteitenvannederland.nl/downloadbare-gegevens-personeel"
# Een eerlijke User-Agent: een kale `Mozilla/5.0` geeft 403 (nepbrowserfilter, #721); niets wordt omzeild.
USER_AGENT = f"onderwijsbronnen/{VERSIE} (+https://github.com/cedanl/onderwijsdata-chat)"
_LINK = re.compile(r"""href=["']([^"']*WOPI_draaitabellen_tm_(\d{4})\.xlsx)["']""", re.IGNORECASE)

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

GEZO = ("excl", "incl")
GESLACHT = ("totaal", "vrouwen")
# De 14 universiteiten van UNL; vier wo-instellingen (TUA, PThU, UvH, TU Kampen) zitten niet in WOPI.
AANTAL_UNIVERSITEITEN = 14
# Aard van de aanstelling in de bron; vóór 2003 staat er overal "n.b." (disclaimer van UNL).
_AANSTELLING = {"V": "vast", "T": "tijdelijk", "n.b.": "onbekend"}


class WopiFout(RuntimeError):
    """Het bestand of de pagina heeft niet de vorm die dit module kent; er komt geen uitkomst."""


@dataclass(frozen=True)
class Tabel:
    """Eén WOPI-tabel: de naam van de brontabel zonder en met GEZO, de verwachte velden en de maat."""

    zonder_gezo: str
    met_gezo: str
    velden: frozenset[str]
    maat: str

    def brontabel(self, gezo: str, geslacht: str) -> str:
        naam = self.zonder_gezo if gezo == "excl" else self.met_gezo
        return f"{naam} v" if geslacht == "vrouwen" else naam


TABELLEN: dict[str, Tabel] = {
    # Tabel 1: fte per functiecategorie en universiteit, met vast of tijdelijk.
    "functie": Tabel(
        "DL_reeks_Functie_geslacht_Uni_VT_exGezo",
        "DL_reeks_Functie_geslacht_Uni_VT",
        frozenset(
            {"jaar", "Instcode", "AardAanstelling", "Functie", "instelling", "brincode", "Functieomschrijving", "fte"}
        ),
        "fte",
    ),
    # Tabel 9: personen per leeftijdsklasse en universiteit; de enige tabel met personen per instelling.
    "personen": Tabel(
        "DL_Leeftijd uni geslacht personen_exGezo",
        "DL_Leeftijd uni geslacht personen",
        frozenset({"jaar", "Leeftijd", "instelling", "personen", "instelling_naam", "brincode"}),
        "personen",
    ),
}


@dataclass(frozen=True)
class Herkomst:
    """Waar een lading vandaan komt: de link, de editie en wat het bestand identificeert."""

    url: str
    editiejaar: int
    sha256: str
    bytes: int
    last_modified: str | None = None

    @property
    def peildatum(self) -> str:
        return f"31-12-{self.editiejaar}"


@dataclass(frozen=True)
class Wopi:
    """De tidy records van één editie, per (tabel, gezo, geslacht), met de herkomst."""

    herkomst: Herkomst
    records: dict[tuple[str, str, str], list[dict]] = field(repr=False)

    def rijen(self, tabel: str = "functie", gezo: str = "excl", geslacht: str = "totaal") -> list[dict]:
        _controleer_keuze(tabel, gezo, geslacht)
        return [dict(r) for r in self.records[(tabel, gezo, geslacht)]]

    def frame(self, tabel: str = "functie", gezo: str = "excl", geslacht: str = "totaal"):
        """De records als pandas-DataFrame (vereist pandas: `onderwijsbronnen[analyse]`)."""
        import pandas as pd

        return pd.DataFrame(self.rijen(tabel, gezo, geslacht))


def _controleer_keuze(tabel: str, gezo: str, geslacht: str) -> None:
    if tabel not in TABELLEN:
        raise ValueError(f"onbekende tabel {tabel!r}; kies uit {sorted(TABELLEN)}")
    if gezo not in GEZO:
        raise ValueError(f"gezo moet 'excl' of 'incl' zijn, niet {gezo!r}; nooit gemengd")
    if geslacht not in GESLACHT:
        raise ValueError(f"geslacht moet 'totaal' of 'vrouwen' zijn, niet {geslacht!r}")


# ── ophalen ───────────────────────────────────────────────────────────────────


def bestandslink(html: str, basis: str = PAGINA) -> tuple[str, int]:
    """De absolute link naar de nieuwste editie op de pagina, met het editiejaar.

    De bestandsnaam verschilt per editie en de pagina linkt alleen de nieuwste; de link wordt dus gelezen, nooit
    gebouwd. Meer links: de hoogste editie.
    """
    links = [(int(m[2]), m[1]) for m in _LINK.finditer(html)]
    if not links:
        raise WopiFout(f"geen link naar een WOPI-bestand (…WOPI_draaitabellen_tm_<jaar>.xlsx) op {basis}")
    jaar, link = max(links)
    return urljoin(basis, link), jaar


def haal_op(timeout: float = 60, transport: httpx.BaseTransport | None = None) -> tuple[bytes, Herkomst]:
    """De nieuwste editie van de pagina: de bytes en de herkomst (link, editie, sha256, Last-Modified).

    `transport` alleen voor tests (`httpx.MockTransport`).
    """
    kop = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=kop, transport=transport) as client:
        pagina = client.get(PAGINA)
        pagina.raise_for_status()
        url, jaar = bestandslink(pagina.text, str(pagina.url))
        bestand = client.get(url)
        bestand.raise_for_status()
    inhoud = bestand.content
    herkomst = Herkomst(
        url=url,
        editiejaar=jaar,
        sha256=hashlib.sha256(inhoud).hexdigest(),
        bytes=len(inhoud),
        last_modified=bestand.headers.get("last-modified"),
    )
    return inhoud, herkomst


# ── lezen ─────────────────────────────────────────────────────────────────────


def _xml(archief: zipfile.ZipFile, pad: str):
    try:
        return ElementTree.fromstring(archief.read(pad))
    except KeyError as e:
        raise WopiFout(f"onderdeel {pad} ontbreekt in het bestand") from e


def _waarde(el) -> object:
    """Een celwaarde uit een cache: getal, tekst, of None voor een lege waarde (`<m/>`)."""
    soort = el.tag.removeprefix(_M)
    if soort == "m":
        return None
    if soort == "n":
        return float(el.get("v"))
    return el.get("v")


def _brontabellen(archief: zipfile.ZipFile) -> dict[str, str]:
    """connectionId → naam van de brontabel (`dbPr/@command`)."""
    uit = {}
    for verbinding in _xml(archief, "xl/connections.xml").iter(f"{_M}connection"):
        db = verbinding.find(f"{_M}dbPr")
        if db is not None and db.get("command"):
            uit[verbinding.get("id")] = db.get("command").strip()
    return uit


def _rels(archief: zipfile.ZipFile, pad: str) -> dict[str, str]:
    return {r.get("Id"): r.get("Target") for r in _xml(archief, pad)}


def _caches(archief: zipfile.ZipFile) -> dict[str, tuple[str, str]]:
    """Naam van de brontabel (in kleine letters) → (pad van de cachedefinitie, naam zoals in het bestand)."""
    brontabellen = _brontabellen(archief)
    rels = _rels(archief, "xl/_rels/workbook.xml.rels")
    caches = _xml(archief, "xl/workbook.xml").find(f"{_M}pivotCaches")
    uit: dict[str, tuple[str, str]] = {}
    for cache in caches if caches is not None else []:
        definitie = "xl/" + rels[cache.get(_R_ID)].removeprefix("/xl/")
        bron = _xml(archief, definitie).find(f"{_M}cacheSource")
        naam = brontabellen.get(bron.get("connectionId")) if bron is not None else None
        if naam:
            uit[naam.lower()] = (definitie, naam)
    return uit


def _cache_records(archief: zipfile.ZipFile, definitiepad: str) -> tuple[list[str], list[dict]]:
    """De velden en records van één cache; `<x v="i"/>` verwijst naar de gedeelde waarden van het veld."""
    definitie = _xml(archief, definitiepad)
    velden: list[str] = []
    gedeeld: list[list[object]] = []
    for veld in definitie.find(f"{_M}cacheFields"):
        velden.append(veld.get("name"))
        items = veld.find(f"{_M}sharedItems")
        gedeeld.append([_waarde(e) for e in items] if items is not None else [])
    map_, naam = definitiepad.rsplit("/", 1)
    doel = _rels(archief, f"{map_}/_rels/{naam}.rels")[definitie.get(_R_ID)]
    records = []
    for rij in _xml(archief, f"{map_}/{doel}"):
        record = {}
        for i, el in enumerate(rij):
            record[velden[i]] = gedeeld[i][int(el.get("v"))] if el.tag == f"{_M}x" else _waarde(el)
        records.append(record)
    return velden, records


def _tidy(tabel: str, record: dict) -> dict:
    jaar = int(record["jaar"])
    if tabel == "functie":
        return {
            "jaar": jaar,
            "brin": record["brincode"],
            "instelling": record["instelling"],
            "functie": record["Functie"],
            "functieomschrijving": record["Functieomschrijving"],
            "aanstelling": _AANSTELLING.get(record["AardAanstelling"], "onbekend"),
            "fte": float(record["fte"]),
        }
    return {
        "jaar": jaar,
        "brin": record["brincode"],
        "instelling": record["instelling_naam"],
        "leeftijd": record["Leeftijd"] or "onbekend",
        "personen": int(round(float(record["personen"]))),
    }


def _controleer_cache(naam: str, velden: list[str], records: list[dict], tabel: Tabel, editiejaar: int) -> None:
    if set(velden) != tabel.velden:
        raise WopiFout(f"cache {naam!r} heeft velden {sorted(velden)}, verwacht {sorted(tabel.velden)}")
    if not records:
        raise WopiFout(f"cache {naam!r} is leeg")
    jongste = max(int(r["jaar"]) for r in records)
    if jongste != editiejaar:
        raise WopiFout(f"cache {naam!r} loopt tot {jongste}, maar de editie is {editiejaar}")
    brins = {r["brincode"] for r in records if int(r["jaar"]) == jongste}
    if len(brins) != AANTAL_UNIVERSITEITEN:
        raise WopiFout(f"cache {naam!r} heeft {len(brins)} BRIN-codes in {jongste}, verwacht {AANTAL_UNIVERSITEITEN}")


def lees(inhoud: bytes, herkomst: Herkomst) -> Wopi:
    """De tidy records van alle tabellen en varianten uit de caches van het bestand, gecontroleerd."""
    try:
        archief = zipfile.ZipFile(io.BytesIO(inhoud))
    except zipfile.BadZipFile as e:
        raise WopiFout("het bestand is geen xlsx") from e
    with archief:
        caches = _caches(archief)
        records: dict[tuple[str, str, str], list[dict]] = {}
        for sleutel, tabel in TABELLEN.items():
            for gezo in GEZO:
                for geslacht in GESLACHT:
                    naam = tabel.brontabel(gezo, geslacht)
                    if naam.lower() not in caches:
                        raise WopiFout(f"brontabel {naam!r} ontbreekt in het bestand")
                    pad, gevonden = caches[naam.lower()]
                    velden, ruw = _cache_records(archief, pad)
                    _controleer_cache(gevonden, velden, ruw, tabel, herkomst.editiejaar)
                    records[(sleutel, gezo, geslacht)] = [_tidy(sleutel, r) for r in ruw]
    return Wopi(herkomst, records)


def load(tabel: str = "functie", gezo: str = "excl", geslacht: str = "totaal"):
    """De nieuwste editie van één tabel als pandas-DataFrame (tidy, één rij per record van de draaitabel).

    Args:
        tabel:    "functie" (fte per functie, met vast/tijdelijk) of "personen" (personen per leeftijdsklasse).
        gezo:     "excl" (zonder het HOOP-gebied Gezondheid, standaard) of "incl"; nooit door elkaar.
        geslacht: "totaal" of "vrouwen".
    """
    _controleer_keuze(tabel, gezo, geslacht)
    return lees(*haal_op()).frame(tabel, gezo, geslacht)
