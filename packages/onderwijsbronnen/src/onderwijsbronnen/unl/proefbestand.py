"""Een synthetisch WOPI-bestand met dezelfde XML-vorm als dat van UNL, voor tests en voorbeelden (#936).

Er staat geen data van UNL in deze repo (licentie, #731 §8). Dit bestand bouwt een xlsx met alleen wat `wopi.lees`
leest: `xl/connections.xml` met de namen van de brontabellen, `xl/workbook.xml` met de draaitabelcaches, en per cache
een definitie (velden met gedeelde waarden) en records (`<x v="…"/>` naar een gedeelde waarde, `<n v="…"/>` voor de
maat, `<m/>` voor leeg). De caches staan in een andere volgorde dan in het echte bestand, met een cache van een
andere tabel vooraan: wie op nummer kiest in plaats van op naam, leest de verkeerde.

De getallen zijn verzonnen, maar zo gekozen dat de controlewaarden uit het onderzoek (#731) uitkomen: Universiteit
Utrecht 6.184,36 fte zonder GEZO, waarvan 3.584,05 wetenschappelijk; landelijk 58.462,07 fte zonder en 61.371,30 met
GEZO; personen 66.723 zonder en 70.266 met GEZO (peildatum 31-12-2025).
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from xml.sax.saxutils import quoteattr

from .wopi import TABELLEN, Herkomst

EDITIEJAAR = 2025
URL = f"https://www.universiteitenvannederland.nl/files/publications/Proef_WOPI_draaitabellen_tm_{EDITIEJAAR}.xlsx"

# (BRIN, afkorting in WOPI, naam in WOPI)
UNIVERSITEITEN = (
    ("21PE", "EUR", "Erasmus Universiteit Rotterdam"),
    ("21PB", "LEI", "Universiteit Leiden"),
    ("22NC", "OU", "Open Universiteit"),
    ("21PM", "RU", "Radboud Universiteit Nijmegen"),
    ("21PC", "RUG", "Rijksuniversiteit Groningen"),
    ("21PN", "TiU", "Tilburg University"),
    ("21PF", "TUD", "Technische Universiteit Delft"),
    ("21PG", "TUE", "Technische Universiteit Eindhoven"),
    ("21PJ", "UM", "Universiteit Maastricht"),
    ("21PH", "UT", "Universiteit Twente"),
    ("21PD", "UU", "Universiteit Utrecht"),
    ("21PK", "UVA", "Universiteit van Amsterdam"),
    ("21PL", "VU", "Vrije Universiteit"),
    ("21PI", "WU", "Wageningen Universiteit"),
)
_OMSCHRIJVING = {
    "HGL": "Hoogleraar",
    "UHD": "Universitair hoofddocent",
    "UD": "Universitair docent",
    "OWPOW": "Docent",
    "OWPOZ": "Onderzoeker",
    "OVWP": "Overig Wetenschappelijk personeel",
    "PROM": "Promovendus",
    "OBP": "Ondersteunend en beheerspersoneel (OBP)",
}

# 2025, zonder GEZO: (functie, aard, fte).
_UU_2025 = [
    ("OBP", "V", 2000.31), ("OBP", "T", 600.00), ("HGL", "V", 400.00), ("UHD", "V", 450.00), ("UD", "V", 1000.00),
    ("UD", "T", 100.05), ("OWPOW", "T", 300.00), ("OWPOZ", "T", 200.00), ("OVWP", "T", 134.00), ("PROM", "T", 1000.00),
]
_ANDER_2025 = [("OBP", "V", 1800.00), ("HGL", "V", 300.00), ("UD", "V", 700.00), ("PROM", "T", 1200.00)]
_OU_2025 = [("OBP", "V", 2077.71), ("HGL", "V", 300.00), ("UD", "V", 700.00), ("PROM", "T", 1200.00)]
# Het HOOP-gebied Gezondheid, alleen in de variant met GEZO.
_GEZO_2025 = {"21PD": [("OBP", "V", 420.20), ("HGL", "V", 445.15)], "21PJ": [("OBP", "V", 1000.00), ("PROM", "T", 1043.88)]}

# 2025, zonder GEZO: (leeftijd, personen); None is een lege leeftijdsklasse in de bron.
_UU_PERSONEN = [("<25", 1000), ("25-29", 2076), ("30-34", 4000)]
_ANDER_PERSONEN = [("<25", 600), ("25-29", 2000), ("30-34", 2000)]
_OU_PERSONEN = [("<25", 447), ("25-29", 2000), ("30-34", 2000)]
_GEZO_PERSONEN = {"21PD": [("30-34", 1006)], "21PJ": [("30-34", 2537)]}

# Eerdere jaren als fractie van 2025. Vóór 2003 is de aard van de aanstelling onbekend en vóór 2005 bestaan
# docent (OWPOW) en onderzoeker (OWPOZ) niet; personen per universiteit pas vanaf 2005.
_JAREN_FTE = {2002: 0.7, 2005: 0.8, 2024: 0.98, EDITIEJAAR: 1.0}
_JAREN_PERSONEN = {2005: 0.8, 2024: 0.98, EDITIEJAAR: 1.0}


def _functierijen(gezo: str) -> list[tuple[int, str, str, str, float]]:
    """(jaar, brin, functie, aard, fte) voor alle jaren, met de GEZO-rijen erbij bij `incl`."""
    basis = []
    for brin, _, _ in UNIVERSITEITEN:
        rijen = _UU_2025 if brin == "21PD" else _OU_2025 if brin == "22NC" else _ANDER_2025
        basis += [(brin, *r) for r in rijen]
        if gezo == "incl":
            basis += [(brin, *r) for r in _GEZO_2025.get(brin, [])]
    uit: dict[tuple, float] = {}
    for jaar, factor in _JAREN_FTE.items():
        for brin, functie, aard, fte in basis:
            if jaar < 2005 and functie in ("OWPOW", "OWPOZ"):
                functie = "UD"
            aard = "n.b." if jaar < 2003 else aard
            sleutel = (jaar, brin, functie, aard)
            uit[sleutel] = round(uit.get(sleutel, 0.0) + round(fte * factor, 2), 2)
    return [(*k, v) for k, v in uit.items()]


def _personenrijen(gezo: str) -> list[tuple[int, str, str | None, int]]:
    uit: dict[tuple, int] = {}
    for brin, _, _ in UNIVERSITEITEN:
        rijen = _UU_PERSONEN if brin == "21PD" else _OU_PERSONEN if brin == "22NC" else _ANDER_PERSONEN
        rijen = rijen + (_GEZO_PERSONEN.get(brin, []) if gezo == "incl" else [])
        for jaar, factor in _JAREN_PERSONEN.items():
            for leeftijd, aantal in rijen:
                sleutel = (jaar, brin, leeftijd)
                uit[sleutel] = uit.get(sleutel, 0) + round(aantal * factor)
    uit[(2005, "21PD", None)] = 3
    return [(*k, v) for k, v in uit.items()]


def _records(tabel: str, gezo: str, geslacht: str) -> list[dict]:
    namen = {brin: (afk, naam) for brin, afk, naam in UNIVERSITEITEN}
    deel = 0.5 if geslacht == "vrouwen" else 1.0
    if tabel == "functie":
        return [
            {
                "jaar": float(jaar), "Instcode": namen[brin][0], "AardAanstelling": aard, "Functie": functie,
                "instelling": namen[brin][1], "brincode": brin, "Functieomschrijving": _OMSCHRIJVING[functie],
                "fte": round(fte * deel, 2),
            }
            for jaar, brin, functie, aard, fte in _functierijen(gezo)
        ]
    return [
        {
            "jaar": float(jaar), "Leeftijd": leeftijd, "instelling": namen[brin][0],
            "personen": float(int(aantal * deel)), "instelling_naam": namen[brin][1], "brincode": brin,
        }
        for jaar, brin, leeftijd, aantal in _personenrijen(gezo)
    ]


_MAAT = {"fte", "personen"}


def _item(waarde: object) -> str:
    if waarde is None:
        return "<m/>"
    if isinstance(waarde, float):
        return f'<n v="{waarde!r}"/>'
    return f"<s v={quoteattr(str(waarde))}/>"


def _cache_xml(records: list[dict]) -> tuple[str, str]:
    """(definitie, records) van één cache: gedeelde waarden voor elk veld behalve de maat."""
    velden = list(records[0])
    gedeeld = {v: list(dict.fromkeys(r[v] for r in records)) for v in velden if v not in _MAAT}
    kop = "".join(
        f'<cacheField name={quoteattr(v)}><sharedItems>{"".join(_item(w) for w in gedeeld[v])}</sharedItems></cacheField>'
        if v in gedeeld
        else f"<cacheField name={quoteattr(v)}><sharedItems/></cacheField>"
        for v in velden
    )
    definitie = (
        f'<pivotCacheDefinition xmlns="{_NS}" xmlns:r="{_NS_R}" r:id="rId1" recordCount="{len(records)}">'
        f'<cacheSource type="external" connectionId="{{verbinding}}"/><cacheFields count="{len(velden)}">{kop}'
        "</cacheFields></pivotCacheDefinition>"
    )
    rijen = "".join(
        "<r>"
        + "".join(f'<x v="{gedeeld[v].index(r[v])}"/>' if v in gedeeld else _item(r[v]) for v in velden)
        + "</r>"
        for r in records
    )
    return definitie, f'<pivotCacheRecords xmlns="{_NS}" count="{len(records)}">{rijen}</pivotCacheRecords>'


_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_T_CACHE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheDefinition"
_T_RECORDS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheRecords"


def _lokaas() -> list[dict]:
    """Een cache van een andere tabel (salarisgroep), met dezelfde soort velden: hij hoort niet gelezen te worden."""
    return [
        {"jaar": float(EDITIEJAAR), "instelling": afk, "schaal": "11", "fte": 1.0, "instelling_naam": naam,
         "brincode": brin}
        for brin, afk, naam in UNIVERSITEITEN
    ]


def caches(overschrijf: dict[str, list[dict]] | None = None) -> dict[str, list[dict]]:
    """Brontabel → records van het standaard proefbestand; `overschrijf` vervangt of voegt caches toe."""
    uit = {"DL schaal uni_exGezo": _lokaas()}
    for tabel, spec in TABELLEN.items():
        for gezo in ("incl", "excl"):
            for geslacht in ("vrouwen", "totaal"):
                naam = spec.brontabel(gezo, geslacht)
                # Zoals in het echte bestand: één naam met een hoofdletter (`personen_ExGezo`).
                naam = naam.replace("personen_exGezo", "personen_ExGezo") if geslacht == "totaal" else naam
                uit[naam] = _records(tabel, gezo, geslacht)
    return {**uit, **(overschrijf or {})}


def maak(per_brontabel: dict[str, list[dict]] | None = None) -> bytes:
    """Een xlsx met de caches van `per_brontabel` (standaard: `caches()`); een lege lijst wordt een lege cache."""
    per_brontabel = caches() if per_brontabel is None else per_brontabel
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archief:
        verbindingen, caches_xml, rels = [], [], []
        for i, (naam, records) in enumerate(per_brontabel.items(), start=1):
            verbinding = 100 + i  # een ander nummer dan de cache: koppelen gaat via connectionId
            verbindingen.append(
                f'<connection id="{verbinding}" name="WOPI_basis_vanaf 2003{i}" type="1">'
                f'<dbPr connection="DSN=MS Access Database" command={quoteattr(naam)}/></connection>'
            )
            caches_xml.append(f'<pivotCache cacheId="{i - 1}" r:id="rId{i}"/>')
            rels.append(f'<Relationship Id="rId{i}" Type="{_T_CACHE}" Target="pivotCache/pivotCacheDefinition{i}.xml"/>')
            definitie, rijen = _cache_xml(records) if records else _lege_cache()
            archief.writestr(f"xl/pivotCache/pivotCacheDefinition{i}.xml", definitie.replace("{verbinding}", str(verbinding)))
            archief.writestr(f"xl/pivotCache/pivotCacheRecords{i}.xml", rijen)
            archief.writestr(
                f"xl/pivotCache/_rels/pivotCacheDefinition{i}.xml.rels",
                f'<Relationships xmlns="{_NS_REL}"><Relationship Id="rId1" Type="{_T_RECORDS}" '
                f'Target="pivotCacheRecords{i}.xml"/></Relationships>',
            )
        archief.writestr("xl/connections.xml", f'<connections xmlns="{_NS}">{"".join(verbindingen)}</connections>')
        archief.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{_NS}" xmlns:r="{_NS_R}"><pivotCaches>{"".join(caches_xml)}</pivotCaches></workbook>',
        )
        archief.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{_NS_REL}">{"".join(rels)}</Relationships>')
    return buffer.getvalue()


def _lege_cache() -> tuple[str, str]:
    return (
        f'<pivotCacheDefinition xmlns="{_NS}" xmlns:r="{_NS_R}" r:id="rId1" recordCount="0">'
        '<cacheSource type="external" connectionId="{verbinding}"/><cacheFields count="0"/></pivotCacheDefinition>',
        f'<pivotCacheRecords xmlns="{_NS}" count="0"/>',
    )


def herkomst(inhoud: bytes, editiejaar: int = EDITIEJAAR) -> Herkomst:
    """De herkomst bij een proefbestand, zoals `haal_op` haar zou geven."""
    return Herkomst(
        url=URL,
        editiejaar=editiejaar,
        sha256=hashlib.sha256(inhoud).hexdigest(),
        bytes=len(inhoud),
        last_modified="Thu, 28 May 2026 10:45:00 GMT",
    )


def standaard() -> tuple[bytes, Herkomst]:
    """Het standaard proefbestand met zijn herkomst: wat `haal_op()` in een test teruggeeft."""
    inhoud = maak()
    return inhoud, herkomst(inhoud)
