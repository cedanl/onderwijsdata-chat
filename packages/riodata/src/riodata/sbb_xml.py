"""Brongetrouwe SBB-dossierlaag: veilig XML parsen naar dossiers, kerntaken en werkprocessen.

Gebouwd op het XSD "Herziening dossiers 2026" van kwalificatie-mijn.s-bb.nl (geen targetNamespace,
wortel ``<sbb>`` met ``domeinen``, ``sectorkamers``, ``competenties`` en ``dossiers``). Alleen dat
XSD is gecontroleerd; een echt XML-bestand was bij ontwikkeling niet beschikbaar (te groot om op te
halen), dus de tekstinhoud van de elementen is niet tegen echte data getoetst. Andere
bestandsvarianten (bijv. "Dossiers geldig vanaf 2015") kunnen een andere structuur hebben: de
parser geeft dan een ``SbbXmlFout`` of een waarschuwing, geen stille gok.

Veiligheid: inputomvang is begrensd en elke DTD (``DOCTYPE``, ``ENTITY``) wordt op parserniveau
geweigerd, onafhankelijk van de encoding; er zijn dus geen externe entiteiten en geen entity-expansie.

    from riodata import sbb, sbb_xml
    d = sbb_xml.parse_dossiers(sbb.fetch_xml(...), editie="herziening_dossiers_2026")
    sbb_xml.koppel_crebo("25078", d)       # exacte codekoppeling, nooit op naamgelijkenis
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from xml.parsers import expat
from dataclasses import dataclass, field

MAX_BYTES = 200 * 1024 * 1024


class SbbXmlFout(Exception):
    """Onveilige, te grote of structureel onverwachte XML."""


@dataclass(frozen=True)
class SbbDossiers:
    editie: str
    dossiers: tuple[dict, ...]
    domeinen: tuple[dict, ...] = ()
    sectorkamers: tuple[dict, ...] = ()
    competenties: dict = field(default_factory=dict)
    kennis: dict = field(default_factory=dict)
    waarschuwingen: tuple[str, ...] = ()
    bron_url: str | None = None


def _lokaal(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kinderen(el, naam: str):
    return [c for c in el if _lokaal(c.tag) == naam]


def _kind(el, naam: str):
    k = _kinderen(el, naam)
    return k[0] if k else None


def _pad(el, *namen):
    """Volg een rij kindnamen; ``None`` zodra een stap ontbreekt."""
    for n in namen:
        if el is None:
            return None
        el = _kind(el, n)
    return el


def _tekst(el) -> str | None:
    if el is None:
        return None
    t = re.sub(r"\s+", " ", "".join(el.itertext())).strip()
    return t or None


def _attr(el, *namen) -> dict:
    return {n.lower(): el.get(n) for n in namen if el.get(n) is not None}


def _veilig_parsen(content: bytes, max_bytes: int) -> ET.Element:
    """Parseer met expat en weiger elke DTD, ongeacht de encoding van het bestand.

    De weigering gebeurt op de parsergebeurtenis (``StartDoctypeDecl``, ``EntityDecl``), niet op een
    bytezoektocht: ook UTF-16 of een DOCTYPE na een lange proloog wordt zo gevonden, en er is geen
    entity-expansie of extern ophalen.
    """
    if len(content) > max_bytes:
        raise SbbXmlFout(f"XML is {len(content)} bytes; limiet is {max_bytes}")
    parser = expat.ParserCreate(namespace_separator="}")
    stack: list[ET.Element] = []
    root: list[ET.Element] = []

    def weiger(*_args):
        raise SbbXmlFout("DOCTYPE/ENTITY is niet toegestaan (veiligheid)")

    def start(naam, attrs):
        el = ET.Element(naam, attrs)
        if stack:
            stack[-1].append(el)
        else:
            root.append(el)
        stack.append(el)

    def einde(_naam):
        stack.pop()

    def tekst(data):
        if not stack:
            return
        kinderen = list(stack[-1])
        if kinderen:
            kinderen[-1].tail = (kinderen[-1].tail or "") + data
        else:
            stack[-1].text = (stack[-1].text or "") + data

    parser.StartDoctypeDeclHandler = weiger
    parser.EntityDeclHandler = weiger
    parser.NotationDeclHandler = weiger
    parser.ExternalEntityRefHandler = weiger
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.StartElementHandler = start
    parser.EndElementHandler = einde
    parser.CharacterDataHandler = tekst
    try:
        parser.Parse(content, True)
    except SbbXmlFout:
        raise
    except expat.ExpatError as e:
        raise SbbXmlFout(f"XML niet te parseren: {e}") from e
    if not root:
        raise SbbXmlFout("XML niet te parseren: geen wortelelement")
    return root[0]


def _crebo(el) -> dict:
    return {
        "crebo": _tekst(el),
        "ministerie": el.get("ministerie"),
        "prijsfactor": el.get("prijsfactor"),
        "geldig_vanaf": el.get("Geldig_vanaf"),
        "einde_instroom": el.get("Datum_einde_instroom"),
        "einde_opleiding": el.get("Datum_einde_opleiding"),
    }


def _werkproces(wp, hoofd: dict) -> dict:
    return {
        **_attr(wp, "nr", "titel", "hoofdstuk"),
        "omschrijving": _tekst(_kind(wp, "werkprocesomschrijving")),
        "resultaat": _tekst(_kind(wp, "werkprocesresultaat")),
        "gedrag": _tekst(_kind(wp, "werkprocesgedrag")),
        "competentie_refs": [c.get("referentie") for c in _kinderen(_kind(wp, "werkprocescompetenties"), "competentie")]
        if _kind(wp, "werkprocescompetenties") is not None else [],
    }


def _kerntaak(kt, werkprocessen_pad: tuple[str, ...]) -> dict:
    wps = kt
    for stap in werkprocessen_pad:
        wps = _kind(wps, stap) if wps is not None else None
    return {
        **_attr(kt, "nr", "titel", "hoofdstuk"),
        "complexiteit": _tekst(_kind(kt, "complexiteit")),
        "verantwoordelijkheid": _tekst(_kind(kt, "verantwoordelijkheid")),
        "werkprocessen": [_werkproces(w, {}) for w in _kinderen(wps, "werkproces")] if wps is not None else [],
    }


def _dossier(d, waarschuwingen: list[str]) -> dict:
    nr = d.get("nr")
    taken = _pad(d, "basis", "basistaken", "basiskerntaken")
    profielen = []
    for p in _kinderen(_kind(d, "profielen"), "profiel") if _kind(d, "profielen") is not None else []:
        info = _kind(p, "creboinformatie")
        omschr = _kind(p, "omschrijving")
        profielen.append({
            **_attr(p, "nr", "titel", "niveau", "beroepsgroep"),
            "crebos": [_crebo(c) for c in _kinderen(info, "crebo")] if info is not None else [],
            "soort_opleiding": _tekst(_kind(omschr, "soortopleiding")) if omschr is not None else None,
            "profielkerntaken": [_kerntaak(k, ("profielwerkprocessen",))
                                 for k in _kinderen(_kind(p, "profielkerntaken"), "kerntaak")]
            if _kind(p, "profielkerntaken") is not None else [],
        })
    crebos = _kind(d, "dossiercrebos")
    sk = _pad(d, "voorblad", "omschrijving", "penvoerder", "sectorkamer")
    if nr is None:
        waarschuwingen.append(f"Dossier zonder nr: {d.get('titel')!r}")
    return {
        **_attr(d, "nr", "titel", "versie", "status", "referentiedomein"),
        "sectorkamer_ref": sk.get("referentie") if sk is not None else None,
        "dossiercrebos": [_crebo(c) for c in _kinderen(crebos, "dossiercrebo")] if crebos is not None else [],
        "basiskerntaken": [_kerntaak(k, ("basiswerkprocessen",)) for k in _kinderen(taken, "kerntaak")]
        if taken is not None else [],
        "profielen": profielen,
    }


def parse_dossiers(content: bytes, editie: str, *, bron_url: str | None = None, max_bytes: int = MAX_BYTES) -> SbbDossiers:
    """Parseer een SBB-dossier-XML naar dossiers met behoud van hiërarchie en officiële nummers."""
    root = _veilig_parsen(content, max_bytes)
    if _lokaal(root.tag) != "sbb":
        raise SbbXmlFout(f"Verwachte wortel <sbb>, gevonden <{_lokaal(root.tag)}>")
    waarschuwingen: list[str] = []
    dossiers_el = _kind(root, "dossiers")
    if dossiers_el is None:
        raise SbbXmlFout(f"Geen <dossiers> onder <sbb>; aanwezig: {[_lokaal(c.tag) for c in root]}")
    dossiers = [_dossier(d, waarschuwingen) for d in _kinderen(dossiers_el, "dossier")]
    if not dossiers:
        waarschuwingen.append("<dossiers> bevat geen <dossier>")

    def lijst(naam, kind, *attrs):
        el = _kind(root, naam)
        return tuple(_attr(x, *attrs) for x in _kinderen(el, kind)) if el is not None else ()

    kennis = {}
    for d in _kinderen(dossiers_el, "dossier"):
        for k in _kinderen(_kind(d, "kennisenvaardigheden"), "kennisofvaardigheid") if _kind(d, "kennisenvaardigheden") is not None else []:
            kennis[(d.get("nr"), k.get("nr"))] = k.get("titel")
    comp_el = _kind(root, "competenties")
    competenties = {c.get("nr"): {"titel": c.get("titel"), "code": c.get("code")}
                    for c in _kinderen(comp_el, "competentie")} if comp_el is not None else {}
    return SbbDossiers(
        editie=editie, dossiers=tuple(dossiers),
        domeinen=lijst("domeinen", "domein", "nr", "titel", "crebo", "prijsfactor"),
        sectorkamers=lijst("sectorkamers", "sectorkamer", "nr", "titel"),
        competenties=competenties, kennis=kennis,
        waarschuwingen=tuple(waarschuwingen), bron_url=bron_url,
    )


def koppel_crebo(code: str, d: SbbDossiers) -> dict:
    """Koppel een CREBO-code aan dossiers op exacte code (dossier- of profielcrebo).

    Returns ``{"status": found|not_found|ambiguous, "code", "editie", "matches"}``; elke match heeft
    dossiernummer, titel, versie, status en de geldigheidsvelden van de gevonden crebo-regel.
    """
    sleutel = str(code).strip()
    matches = []
    for dos in d.dossiers:
        regels = [("dossiercrebo", c) for c in dos["dossiercrebos"]]
        regels += [("profiel:" + (p.get("nr") or "?"), c) for p in dos["profielen"] for c in p["crebos"]]
        for waar, c in regels:
            if c["crebo"] == sleutel:
                matches.append({"dossier_nr": dos.get("nr"), "dossier_titel": dos.get("titel"),
                                "dossier_versie": dos.get("versie"), "dossier_status": dos.get("status"),
                                "gevonden_in": waar, **{k: v for k, v in c.items() if k != "crebo"}})
    status = "not_found" if not matches else "found" if len(matches) == 1 else "ambiguous"
    return {"status": status, "code": sleutel, "editie": d.editie, "matches": matches}


def passages(d: SbbDossiers) -> list[dict]:
    """Doorzoekbare passages met volledige dossiercontext en herleidbaar pad (voor bronverwijzing).

    Elke passage bevat ``editie``, ``dossier_nr``, ``dossier_titel``, ``pad`` (leesbaar), ``niveau``
    (kerntaak/werkproces/profiel) en ``tekst``. Er wordt niet gerangschikt; dat hoort bij de zoeklaag.
    """
    uit = []

    def voeg(dos, niveau, pad, nr, tekst):
        if tekst:
            uit.append({"editie": d.editie, "dossier_nr": dos.get("nr"), "dossier_titel": dos.get("titel"),
                        "niveau": niveau, "pad": pad, "nr": nr, "tekst": tekst})

    for dos in d.dossiers:
        basis = f"dossier {dos.get('nr')} {dos.get('titel')}"
        for kt in dos["basiskerntaken"]:
            kpad = f"{basis} > kerntaak {kt.get('nr')} {kt.get('titel')}"
            voeg(dos, "kerntaak", kpad, kt.get("nr"), " ".join(filter(None, [kt["complexiteit"], kt["verantwoordelijkheid"]])))
            for wp in kt["werkprocessen"]:
                voeg(dos, "werkproces", f"{kpad} > werkproces {wp.get('nr')} {wp.get('titel')}", wp.get("nr"),
                     " ".join(filter(None, [wp["omschrijving"], wp["resultaat"], wp["gedrag"]])))
        for p in dos["profielen"]:
            ppad = f"{basis} > profiel {p.get('nr')} {p.get('titel')}"
            for kt in p["profielkerntaken"]:
                kpad = f"{ppad} > kerntaak {kt.get('nr')} {kt.get('titel')}"
                voeg(dos, "kerntaak", kpad, kt.get("nr"), " ".join(filter(None, [kt["complexiteit"], kt["verantwoordelijkheid"]])))
                for wp in kt["werkprocessen"]:
                    voeg(dos, "werkproces", f"{kpad} > werkproces {wp.get('nr')} {wp.get('titel')}", wp.get("nr"),
                         " ".join(filter(None, [wp["omschrijving"], wp["resultaat"], wp["gedrag"]])))
    return uit
