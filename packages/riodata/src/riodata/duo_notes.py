"""Parser voor de brontekst (`notes`) van DUO CKAN-datasets.

DUO beschrijft per dataset in markdown-secties (Selecties, Periode, Toelichting, ...)
wat er precies geteld wordt en welke publicatieregels gelden. Deze module bewaart
die tekst volledig en parseert er gecontroleerde velden uit.

Principes:
- Een veld dat niet uit de tekst volgt blijft ``None``; er wordt niets afgeleid.
- Elke geparseerde regel draagt zijn bronpassage.
- Wat verwacht wordt maar niet te parseren is, komt in ``parse_fouten``.
"""
from __future__ import annotations

import hashlib
import re

PORTAL_BASE = "https://onderwijsdata.duo.nl"

_SECTIE_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_ZIN_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_PUBLICATIEREGEL_RE = re.compile(
    r"aantallen kleiner dan (\d+) \(([\d,\s]+)\)\s+allemaal worden weergegeven door (\d+)"
)
_MAAT_RE = re.compile(r"Bij het (aantal [a-z\- ]+?) is gebruik gemaakt van een AVG filter")
_PEILDATUM_RE = re.compile(r"peildatum (\d{1,2} [a-z]+)")
_ONTDUBBELING_RE = re.compile(r"binnen het gehele ([a-z ]+?) slechts één keer worden geteld")
_UITSLUITING_RE = re.compile(r"niet meegeteld|buiten beschouwing")


def parse_notes(notes: str | None) -> dict:
    """Splits notes in secties (verbatim) en parseer teldefinitie en publicatieregels."""
    tekst = (notes or "").replace("\r", "")
    secties = _secties(tekst)
    fouten: list[str] = []

    teldefinitie = _teldefinitie(secties, fouten)
    publicatieregels = _publicatieregels(tekst, secties, fouten)

    if not secties:
        status = "ongestructureerd"
    else:
        status = "gedeeltelijk" if fouten else "ok"

    return {
        "secties": secties,
        "teldefinitie": teldefinitie,
        "publicatieregels": publicatieregels,
        "parse_status": status,
        "parse_fouten": fouten,
    }


def details_from_pkg(pkg: dict) -> dict:
    """Bouw de details-velden voor een CKAN package (``package_show``-resultaat)."""
    notes = pkg.get("notes") or ""
    parsed = parse_notes(notes)
    provenance = {
        "bron_url": f"{PORTAL_BASE}/dataset/{pkg['name']}",
        "metadata_modified": pkg.get("metadata_modified"),
        "notes_sha256": hashlib.sha256(notes.encode("utf-8")).hexdigest(),
    }
    for regel in parsed["publicatieregels"]:
        regel["toepassingsgebied"]["dataset"] = pkg["name"]
    return {
        "_details": {"notes": notes, "secties": parsed["secties"]},
        "_teldefinitie": parsed["teldefinitie"],
        "_publicatieregels": parsed["publicatieregels"],
        "_zoekkaart": zoekkaart(parsed["teldefinitie"], parsed["publicatieregels"]),
        "_notes_provenance": {
            **provenance,
            "parse_status": parsed["parse_status"],
            "parse_fouten": parsed["parse_fouten"],
        },
    }


def zoekkaart(teldefinitie: dict, publicatieregels: list[dict]) -> dict:
    """Compacte weergave: telverschil en kritieke beperking zonder de volledige notes."""
    return {
        "teleenheid": teldefinitie["teleenheid"],
        "inschrijvingstype": teldefinitie["inschrijvingstype"],
        "peildatum": teldefinitie["peildatum"],
        "uitsluitingen": [u["tekst"] for u in teldefinitie["uitsluitingen"]],
        "publicatieregels": [
            f"{r['bereik'][0]}–{r['bereik'][1]} gepubliceerd als {r['gepubliceerd_als']}"
            for r in publicatieregels
        ],
    }


def zoekkaart_tijd(tijd: dict) -> dict:
    """Compacte tijdclaims voor de zoekkaart, afgeleid uit ``_tijd`` (één bron, geen kopie).

    Conflicten staan er altijd bij, zodat zoekkaart en details elkaar niet stil tegenspreken.
    """
    periode = tijd.get("periode") or {}
    dekking = tijd.get("data_dekking") or {}
    hp = tijd.get("historie_prognose")
    uit = {
        "periode": periode.get("waarde") or (f"{dekking['van']}-{dekking['tot']}" if dekking else None),
        "soort": periode.get("soort"),
        "peildatum": (tijd.get("peildatum") or {}).get("waarde")
        or "; ".join((tijd.get("peildatum") or {}).get("bronnen") or []) or None,
        "verversing": (tijd.get("verversing") or {}).get("waarde"),
        "voorlopig": ((tijd.get("editie") or {}).get("voorlopig")) or [],
        "conflicten": [c["reviewstatus"] for c in tijd.get("claims_in_conflict") or []],
    }
    if hp:
        uit["historie_prognose"] = f"kolom {hp['kolom']}: historie {hp['historie']}, prognose {hp['prognose']}"
    if dekking.get("resources_verschillen"):
        uit["let_op"] = "resources dekken verschillende jaren; zie _tijd.data_dekking"
    return uit


# ── intern ────────────────────────────────────────────────────────────────────

def _secties(tekst: str) -> dict[str, str]:
    delen = _SECTIE_RE.split(tekst)
    # delen = [voorwoord, kop1, body1, kop2, body2, ...]
    return {delen[i]: delen[i + 1].strip() for i in range(1, len(delen) - 1, 2)}


def _zinnen(tekst: str) -> list[str]:
    return [z.strip() for z in _ZIN_RE.split(" ".join(tekst.split())) if z.strip()]


def _passage(tekst: str, begin: str, eind: str) -> str | None:
    """Zinnen vanaf de eerste zin met `begin` t/m de eerste zin met `eind` daarna."""
    zinnen = _zinnen(tekst)
    start = next((i for i, z in enumerate(zinnen) if begin in z or eind in z), None)
    if start is None:
        return None
    stop = next((i for i in range(start, len(zinnen)) if eind in zinnen[i]), start)
    return " ".join(zinnen[start : stop + 1])


def _teldefinitie(secties: dict[str, str], fouten: list[str]) -> dict:
    # DUO gebruikt 'Selectie', 'Selecties' en 'Selectiecriteria' als kop.
    selecties = next((body for kop, body in secties.items() if kop.lower().startswith("selectie")), None)
    leeg = {
        "teleenheid": None,
        "inschrijvingstype": None,
        "ontdubbelingsdomein": None,
        "peildatum": None,
        "uitsluitingen": [],
        "selectie": None,
    }
    if selecties is None:
        # Niet elke dataset beschrijft zijn telregels in een eigen sectie: onbekend blijft onbekend.
        return leeg

    platte_tekst = " ".join(selecties.split())
    label = re.match(r"([^:]{3,80}):\s", platte_tekst)

    if "natuurlijke personen" in platte_tekst and "één keer" in platte_tekst:
        teleenheid = "personen"
    elif label and label.group(1).lower().startswith("inschrijvingen"):
        teleenheid = "inschrijvingen"
    else:
        teleenheid = None

    if re.search(r"hoofd- als de echte neveninschrijvingen|hoofd- en (echte )?neveninschrijvingen", platte_tekst):
        inschrijvingstype = "hoofd- en neveninschrijvingen"
    elif "hoofdinschrijvingen" in platte_tekst:
        inschrijvingstype = "hoofdinschrijvingen"
    else:
        inschrijvingstype = None

    peildatum = _PEILDATUM_RE.search(platte_tekst) or _PEILDATUM_RE.search(
        " ".join(secties.get("Bronnen", "").split())
    )
    ontdubbeling = _ONTDUBBELING_RE.search(platte_tekst)

    return {
        "teleenheid": teleenheid,
        "inschrijvingstype": inschrijvingstype,
        "ontdubbelingsdomein": (
            {
                "waarde": ontdubbeling.group(1),
                "bronpassage": next(z for z in _zinnen(selecties) if "één keer" in z),
            }
            if ontdubbeling
            else None
        ),
        "peildatum": peildatum.group(1) if peildatum else None,
        "uitsluitingen": [
            {"tekst": z, "sectie": "Selecties"}
            for z in _zinnen(selecties)
            if _UITSLUITING_RE.search(z)
        ],
        "selectie": selecties,
    }


def _publicatieregels(tekst: str, secties: dict[str, str], fouten: list[str]) -> list[dict]:
    sectienaam, bron = next(
        ((naam, body) for naam, body in secties.items() if _PUBLICATIEREGEL_RE.search(" ".join(body.split()))),
        ("Toelichting", secties.get("Toelichting", "")),
    )
    platte_tekst = " ".join(bron.split())
    regels = []
    for m in _PUBLICATIEREGEL_RE.finditer(platte_tekst):
        waarden = [int(x) for x in re.findall(r"\d+", m.group(2))]
        maat = _MAAT_RE.search(platte_tekst)
        regels.append(
            {
                "type": "kleine_aantallen_weergegeven_als",
                "bereik": [min(waarden), max(waarden)],
                "gepubliceerd_als": int(m.group(3)),
                "maat": maat.group(1) if maat else None,
                # De bron noemt geen resource of kolom: dat blijft expliciet onbekend.
                "toepassingsgebied": {
                    "dataset": None,
                    "resources": "niet gespecificeerd in bron",
                    "meetkolom": None,
                },
                "bronpassage": _passage(bron, "AVG filter", "weergegeven door"),
                "sectie": sectienaam,
            }
        )
    if not regels and re.search(r"AVG[- ]filter|kleiner dan \d", tekst):
        fouten.append("publicatieregel genoemd in notes maar niet geparseerd")
    if len({(r["bereik"][0], r["bereik"][1], r["gepubliceerd_als"]) for r in regels}) > 1:
        fouten.append("bronconflict: meerdere verschillende publicatieregels")
    return regels
