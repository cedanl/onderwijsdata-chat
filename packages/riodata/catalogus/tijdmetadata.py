"""Leg tijdmetadata van DUO-datasets vast als aparte, herleidbare claims (`_tijd`).

Alleen datasets waarvan de CKAN-beschrijving (``package_show``) is gelezen staan hier; elke claim
heeft een bronzin of -veld. Waarnemingsperiode, prognosehorizon, editie, peildatum en verversing zijn
aparte velden, en tegenstrijdige bronclaims blijven naast elkaar staan met reviewstatus.

Gebruik:
    uv run python catalogus/tijdmetadata.py

Uitbreiden: lees de ``notes`` en ``extras`` van een dataset, voeg een invoer toe aan ``TIJD`` en draai
het script opnieuw. Geen invoer betekent: niet gecontroleerd (niet: geen tijdmetadata).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "src" / "riodata" / "data"
BESTANDEN = ("duo_resources.json", "duo_resources_enriched.json")
OPGEHAALD = "2026-10-05"
CKAN = "https://onderwijsdata.duo.nl/api/3/action/package_show?id="

TIJD: dict[str, dict] = {
    "studentprognoses-mbo-per-instelling": {
        "periode": "2021-2040",
        "frequentie": "Twee keer per jaar (februari/maart en april/mei)",
        "_tijd": {
            "bron": {"url": CKAN + "studentprognoses-mbo-per-instelling",
                     "metadata_modified": "2026-04-29T12:20:34", "opgehaald_op": OPGEHAALD},
            "periode": {
                "waarde": "2021-2040",
                "soort": "prognose",
                "bronzin": "Deze gegevens hebben betrekking op de periode 2021-2040",
                "opmerking": "De notes spreken van historische studentenaantallen en een prognose binnen deze "
                             "periode; de grens staat niet in de metadata maar wel per rij in de data (kolom Type).",
            },
            "historie_prognose": {
                "kolom": "Type",
                "historie": "2021-2025",
                "prognose": "2026-2040",
                "versiekolom": "Versie",
                "versies_in_bestand": ["2"],
                "bron": f"data: mbo-studentenprognose_instelling en _onderwijslocatie volledig gelezen op {OPGEHAALD}",
                "let_op": "Filter op Type om historische en voorspelde rijen niet op te tellen.",
            },
            "editie": {
                "publicatiedatum": "2026-04-29",
                "versies": "versie 1 = publicatie februari/maart, versie 2 = publicatie april/mei (kenmerk in het bestand)",
                "bronzin": "De publicatiedatum is 29-04-2026.",
            },
            "peildatum": {
                "bronnen": ["1-cijfer mbo: 2025-10-01", "Bevolkingsaantallen CBS: 2025-01-01"],
                "bronzin": "1-cijfer mbo (peildatum 01-10-2025), Bevolkingsaantallen CBS (peildatum 01-01-2025)",
            },
            "verversing": {
                "waarde": "twee keer per jaar",
                "bronzin": "de publicatie van de gegevens vindt twee keer per jaar plaats in februari/maart en in april/mei",
            },
            "claims_in_conflict": [
                {"veld": "verversing", "waarde": "jaarlijks",
                 "bron": "CKAN extras.frequency = .../frequency/ANNUAL",
                 "reviewstatus": "conflict: notes zeggen twee keer per jaar; de notes zijn gevolgd"},
            ],
            "eerdere_catalogusclaims": [
                {"veld": "periode", "waarde": "2021-2030", "reviewstatus": "onjuist volgens bron (2021-2040)"},
                {"veld": "frequentie", "waarde": "Jaarlijks", "reviewstatus": "conflict met notes (twee keer per jaar)"},
            ],
            "reviewstatus": f"bronverificatie {OPGEHAALD}",
        },
    },
    "mbo_opleidingsaanbod": {
        "periode": "Actueel aanbod (open cohorten met aanmeldperiode die nog loopt), dagelijks geactualiseerd",
        "frequentie": "Dagelijks",
        "_tijd": {
            "bron": {"url": CKAN + "mbo_opleidingsaanbod",
                     "metadata_modified": "2026-10-03T02:35:06", "opgehaald_op": OPGEHAALD},
            "periode": {
                "waarde": None,
                "soort": "actueel overzicht (geen waarnemingsperiode)",
                "bronzin": "de actuele aangeboden opleidingen met de bijbehorende cohorten waarvan de status open is "
                           "en waarvan de aanmeldperiode nog niet is verstreken",
            },
            "editie": None,
            "peildatum": None,
            "verversing": {"waarde": "dagelijks", "bronzin": "Het mbo opleidingsaanbod wordt dagelijks geactualiseerd."},
            "claims_in_conflict": [],
            "eerdere_catalogusclaims": [
                {"veld": "frequentie", "waarde": "Onbekend",
                 "reviewstatus": "onvolledig: CKAN heeft geen frequency-extra, de notes (sectie Periode) wel"},
                {"veld": "periode", "waarde": "Jaarlijks bijgewerkt (zie dataset voor peilmoment)",
                 "reviewstatus": "onjuist volgens bron (dagelijks geactualiseerd)"},
            ],
            "reviewstatus": f"bronverificatie {OPGEHAALD}",
        },
    },
}


def _ho_1cijfer(ckan_id: str, metadata_modified: str, eenheid: str, catalogus_periode: str) -> dict:
    """p01-p04: laatste vijf studie-/diplomajaren, jaarlijks, peildatum 1 oktober (notes, sectie Periode)."""
    return {
        "periode": f"Laatste vijf {eenheid} (zie data_dekking)",
        "frequentie": "Jaarlijks",
        "_tijd": {
            "bron": {"url": CKAN + ckan_id, "metadata_modified": metadata_modified, "opgehaald_op": OPGEHAALD},
            "periode": {
                "waarde": None,
                "soort": f"waarneming: laatste vijf {eenheid}",
                "bronzin": f"De bestanden geven informatie over de laatste vijf {eenheid}.",
                "opmerking": "De notes noemen geen jaartallen; data_dekking geeft de jaren uit de data.",
            },
            "editie": None,
            "peildatum": {"waarde": "1 oktober",
                          "bronzin": "op basis van de nieuwste versie van 1cijfer hoger onderwijs met peildatum 1 oktober"},
            "verversing": {"waarde": "jaarlijks",
                           "bronzin": "De bestanden worden één keer per jaar geactualiseerd"},
            "claims_in_conflict": [],
            "eerdere_catalogusclaims": [
                {"veld": "periode", "waarde": catalogus_periode,
                 "reviewstatus": "niet in de bron: de notes noemen geen jaartallen"
                                 + ("; DIPLOMAJAAR is in de bron niet als studiejaar gedefinieerd" if eenheid == "diplomajaren" else "")},
            ],
            "reviewstatus": f"bronverificatie {OPGEHAALD}",
        },
    }


def _mbo_1cijfer(ckan_id: str, metadata_modified: str, catalogus_periode: str) -> dict:
    """1-cijfer-mbo-datasets: periode 2021-2025, peildatum 1 oktober, 2025 voorlopig (notes)."""
    eerder = [] if catalogus_periode == "2021-2025" else [
        {"veld": "periode", "waarde": catalogus_periode, "reviewstatus": "onvolledig: de notes noemen 2021-2025"}]
    return {
        "periode": "2021-2025",
        "frequentie": "Jaarlijks",
        "_tijd": {
            "bron": {"url": CKAN + ckan_id, "metadata_modified": metadata_modified, "opgehaald_op": OPGEHAALD},
            "periode": {"waarde": "2021-2025", "soort": "waarneming",
                        "bronzin": "Deze gegevens hebben betrekking op de periode 2021-2025."},
            "editie": {"voorlopig": ["2025"],
                       "bronzin": "De gegevens over 1 oktober 2025 betreffen voorlopige cijfers. De gegevens over "
                                  "alle andere studiejaren betreffen definitieve cijfers."},
            "peildatum": {"waarde": "1 oktober van het studiejaar",
                          "bronzin": "op peildatum 1 oktober van het studiejaar"},
            "verversing": {"waarde": "jaarlijks", "bronzin": "CKAN extras.frequency = .../frequency/ANNUAL",
                           "opmerking": "alleen de CKAN-extra; de notes noemen geen frequentie"},
            "claims_in_conflict": [],
            "eerdere_catalogusclaims": eerder,
            "reviewstatus": f"bronverificatie {OPGEHAALD}",
        },
    }


def _adressen(ckan_id: str, metadata_modified: str) -> dict:
    return {
        "periode": "Actuele stand in RIO bij aanmaak van de levering",
        "frequentie": "Maandelijks",
        "_tijd": {
            "bron": {"url": CKAN + ckan_id, "metadata_modified": metadata_modified, "opgehaald_op": OPGEHAALD},
            "periode": {"waarde": None, "soort": "actueel overzicht (geen waarnemingsperiode)",
                        "bronzin": "Actuele stand van zaken in RIO op het moment van aanmaak van de adreslevering."},
            "editie": None,
            "peildatum": {"waarde": "moment van aanmaak van de levering", "bronzin": "op het moment van aanmaak van de adreslevering"},
            "verversing": {"waarde": "maandelijks", "bronzin": "CKAN extras.frequency = .../frequency/MONTHLY",
                           "opmerking": "alleen de CKAN-extra; de notes noemen geen frequentie"},
            "claims_in_conflict": [],
            "eerdere_catalogusclaims": [
                {"veld": "periode", "waarde": "Jaarlijks bijgewerkt (zie dataset voor peilmoment)",
                 "reviewstatus": "onjuist volgens bron (actuele stand, maandelijkse CKAN-frequentie)"},
                {"veld": "frequentie", "waarde": "Onbekend", "reviewstatus": "onvolledig: CKAN-frequency is MONTHLY"},
            ],
            "reviewstatus": f"bronverificatie {OPGEHAALD}",
        },
    }


TIJD.update({
    "p01hoinges": _ho_1cijfer("p01hoinges", "2026-07-10T11:37:18", "studiejaren", "2021/'22-2025/'26"),
    "p02ho1ejrs": _ho_1cijfer("p02ho1ejrs", "2026-07-10T11:37:44", "studiejaren", "2021/'22-2025/'26"),
    "p03hoinschr": _ho_1cijfer("p03hoinschr", "2026-07-10T11:37:51", "studiejaren", "2021/'22-2025/'26"),
    "p04hogdipl": _ho_1cijfer("p04hogdipl", "2026-07-10T11:39:38", "diplomajaren", "2020/'21-2024/'25"),
    "mbo-studenten-per-instelling": _mbo_1cijfer("mbo-studenten-per-instelling", "2026-02-02T09:53:31", "2021-2025"),
    "mbo-studenten-per-sectorkamer-en-leerweg": _mbo_1cijfer(
        "mbo-studenten-per-sectorkamer-en-leerweg", "2026-02-02T09:56:39", "Jaarlijks bijgewerkt (zie dataset voor peilmoment)"),
    "instromende-mbo-studenten": _mbo_1cijfer(
        "instromende-mbo-studenten", "2026-02-02T10:10:24", "Jaarlijks bijgewerkt (zie dataset voor peilmoment)"),
    "gediplomeerde-mbo-studenten": _mbo_1cijfer(
        "gediplomeerde-mbo-studenten", "2026-02-02T09:48:33", "Jaarlijks bijgewerkt (zie dataset voor peilmoment)"),
    "adressen_mbo": _adressen("adressen_mbo", "2026-10-02T16:32:27"),
    "adressen_ho": _adressen("adressen_ho", "2026-10-02T16:30:44"),
})

_JAAR_RE = re.compile(r"^(STUDIEJAAR|DIPLOMAJAAR|JAAR|SCHOOLJAAR)$", re.I)
_WIJD_RE = re.compile(r"^(?:JAAR_|DIPMAN|DIPVROUW)(\d{4})$", re.I)
_NAAM_RE = re.compile(r"^(\d{4})\s")


def data_dekking(ckan_id: str, snapshot: dict) -> dict | None:
    """Jaren per resource uit de schema-snapshot: periodekolom (volledige scan), brede
    JAAR_YYYY-kolommen of een jaartal vooraan de resourcenaam. Geen bewijs → None."""
    ds = snapshot.get("datasets", {}).get(ckan_id)
    if not ds:
        return None
    per_resource = {}
    for r in ds["resources"]:
        w = r.get("waarden") or {}
        jaren, hoe = None, None
        for k in r["kolommen"]:
            info = (w.get("kolommen") or {}).get(k["naam"], {})
            if _JAAR_RE.match(k["naam"]) and w.get("volledig") and "min" in info:
                jaren, hoe = (int(info["min"]), int(info["max"])), f"kolom {k['naam']} (volledige scan)"
                break
        if not jaren:
            wijd = [int(m.group(1)) for k in r["kolommen"] if (m := _WIJD_RE.match(k["naam"]))]
            if wijd:
                jaren, hoe = (min(wijd), max(wijd)), "jaartal in kolomnamen (bijv. JAAR_2021, DIPMAN2021)"
        if not jaren and (m := _NAAM_RE.match(r["naam"])):
            jaren, hoe = (int(m.group(1)), int(m.group(1))), "jaartal in resourcenaam"
        if jaren:
            per_resource[r["resource_id"]] = {"naam": r["naam"], "van": jaren[0], "tot": jaren[1], "bron": hoe}
    if not per_resource:
        return None
    return {
        "van": min(x["van"] for x in per_resource.values()),
        "tot": max(x["tot"] for x in per_resource.values()),
        "resources_verschillen": len({(x["van"], x["tot"]) for x in per_resource.values()}) > 1,
        "per_resource": per_resource,
        "bron": "duo_resource_schemas.json",
    }


def conflicten(tijd: dict, dekking: dict | None) -> list[dict]:
    """Expliciete conflictmelding als de bronperiode (YYYY-YYYY) niet past bij de data."""
    waarde = (tijd.get("periode") or {}).get("waarde")
    if not dekking or not waarde or not re.fullmatch(r"\d{4}-\d{4}", waarde):
        return []
    van, tot = (int(x) for x in waarde.split("-"))
    if (van, tot) == (dekking["van"], dekking["tot"]):
        return []
    return [{"veld": "periode", "waarde": f"{dekking['van']}-{dekking['tot']}", "bron": "data_dekking",
             "reviewstatus": f"conflict: bron noemt {waarde}, data loopt van {dekking['van']} tot {dekking['tot']}"}]


def _snapshot() -> dict:
    pad = DATA / "duo_resource_schemas.json"
    return json.loads(pad.read_text(encoding="utf-8")) if pad.exists() else {}


def pas_toe(records: list[dict]) -> int:
    n = 0
    for r in records:
        t = TIJD.get(r.get("_ckan_id"))
        if not t:
            continue
        tijd = json.loads(json.dumps(t["_tijd"]))
        dekking = data_dekking(r["_ckan_id"], _snapshot())
        tijd["data_dekking"] = dekking
        tijd["claims_in_conflict"] = [
            c for c in tijd["claims_in_conflict"] if c.get("bron") != "data_dekking"
        ] + conflicten(tijd, dekking)
        periode = t["periode"]
        if "(zie data_dekking)" in periode and dekking:
            soort = "diplomajaren" if "diploma" in periode else "studiejaren (startjaar)"
            periode = f"{soort} {dekking['van']}-{dekking['tot']} (laatste vijf, volgens de data)"
            for claim in tijd["eerdere_catalogusclaims"]:
                claim["reviewstatus"] += f"; de data loopt van {dekking['van']} tot {dekking['tot']}"
        r["periode"], r["frequentie"], r["_tijd"] = periode, t["frequentie"], tijd
        n += 1
    return n


def main() -> None:
    for naam in BESTANDEN:
        pad = DATA / naam
        tekst = pad.read_text(encoding="utf-8")
        records = json.loads(tekst)
        n = pas_toe(records)
        pad.write_text(json.dumps(records, ensure_ascii=False, indent=2) + ("\n" if tekst.endswith("\n") else ""),
                       encoding="utf-8")
        print(f"{naam}: {n} records bijgewerkt")


if __name__ == "__main__":
    main()
