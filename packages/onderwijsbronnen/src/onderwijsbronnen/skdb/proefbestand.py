"""Een synthetische SKDB-export voor tests (#957): dezelfde ZIP-vorm en veldnamen als `/export/json`, verzonnen getallen.

Er staat geen data van LCSK in de repo; deze export heeft twee echte BRIN- en CROHO-codes (zodat koppelen aan het
register te toetsen is) maar alle cijfers zijn verzonnen.
"""

from __future__ import annotations

import io
import json
import zipfile

from .export import Herkomst, herkomst

BESTAND = "export-skdb-26.6-api-v1-all-2026-11-06-json.zip"

INSTELLINGEN = [
    {"instellingSkdb": 1, "instellingCode": "25DW", "instellingNaam": "Hogeschool Utrecht", "instellingSoort": "Hogeschool", "instellingBekostiging": "Bekostigd"},
    {"instellingSkdb": 2, "instellingCode": "21PB", "instellingNaam": "Universiteit Leiden", "instellingSoort": "Universiteit", "instellingBekostiging": "Bekostigd"},
    {"instellingSkdb": 3, "instellingCode": "99XX", "instellingNaam": "Proefhogeschool Particulier", "instellingSoort": "Hogeschool", "instellingBekostiging": "Niet bekostigd"},
    {"instellingSkdb": 4, "instellingCode": "98ZZ", "instellingNaam": "Proefuniversiteit", "instellingSoort": "Universiteit", "instellingBekostiging": "Bekostigd"},
]


# Vooropleidingseisen (RATHO) zoals in de export: havo, vwo, mbo.
_ICT_EISEN = ("Havo met profiel EM, CM, NG, NT.", "Vwo met profiel EM, CM, NG, NT.", "Direct toelaatbaar")
_WO_EISEN = ("Niet toelaatbaar", "Vwo met profiel EM, CM, NG, NT.", "Niet toelaatbaar")


def _opleiding(skdb, brin, inst, code, studiecode, naam, graad, soort, stad, eisen=_ICT_EISEN):
    return {
        "wettelijkeVooropleidingEisenHavo": eisen[0], "wettelijkeVooropleidingEisenVwo": eisen[1],
        "toelatingsEisenMbo": eisen[2],
        "opleidingSkdb": skdb, "instellingCode": brin, "instellingSkdb": inst, "opleidingCode": code,
        "studieOpleidingCodeSkdb": studiecode, "opleidingNaam": naam, "rioNaam": naam, "hoviOpleidingNaam": naam,
        "graad": graad, "soortHo": soort, "bezoekAdresStad": stad, "opleidingBekostiging": "Bekostigd",
    }


OPLEIDINGEN = [
    _opleiding(11, "25DW", 1, 30020, 30020, "ICT", "Bachelor", "HBO", "UTRECHT"),
    _opleiding(12, "25DW", 1, 34560, 34560, "Verpleegkunde", "Bachelor", "HBO", "UTRECHT"),
    _opleiding(21, "21PB", 2, 56604, 56604, "Psychologie", "Bachelor", "WO", "LEIDEN", _WO_EISEN),
    _opleiding(22, "21PB", 2, 56990, 56990, "Biomedische Wetenschappen", "Bachelor", "WO", "LEIDEN", _WO_EISEN),
    _opleiding(31, "99XX", 3, 30020, 30020, "ICT", "Bachelor", "HBO", "'S-HERTOGENBOSCH"),
    # "ict" staat midden in "Conflict": een naamfilter op woordbegin laat deze opleiding buiten een ICT-vraag (#960).
    _opleiding(41, "98ZZ", 4, 60999, 60999, "Conflict Resolution and Governance", "Master", "WO", "AMSTERDAM", _WO_EISEN),
]


def _vorm(skdb, vorm_id, studiecode, brin, code, oordeel, respondenten, studenten, eerstejaars, jaar2, diploma):
    vorm = {1: "Voltijd", 2: "Deeltijd", 3: "Duaal"}[vorm_id]
    return {
        "opleidingSkdb": skdb, "opleidingVormId": vorm_id, "opleidingVorm": vorm, "studieOpleidingCodeSkdb": studiecode,
        "instellingCode": brin, "opleidingCode": code, "algemeenOordeelGewogenGemiddelde": oordeel,
        "algemeenOordeelAantal": respondenten, "studentenAantal": studenten, "eersteJaarAantal": eerstejaars,
        "doorstroomJaar2Perc": jaar2, "opleidingDiplomasPerc": diploma, "accreditatieBesluitDatum": "2025-02-21",
        "docentenGewogenGemiddelde": None if oordeel is None else 3.8,
        "enqueteJaar": None if oordeel is None else 2026, "eenCijferHoMeestRecenteJaar": 2025,
    }


OPLEIDINGVORMEN = [
    _vorm(11, 1, 30020, "25DW", 30020, 3.6123, 120, 900, 250, 70.04, 45.55),
    _vorm(11, 2, 30020, "25DW", 30020, 3.7, 40, 120, 20, None, None),
    _vorm(12, 1, 34560, "25DW", 34560, 3.9, 200, 1500, 400, 80.0, 60.0),
    _vorm(21, 1, 56604, "21PB", 56604, 4.05, 500, 2500, 600, 88.3, 70.1),
    _vorm(22, 1, 56990, "21PB", 56990, None, None, 400, 71, 90.0, 80.0),
    _vorm(31, 1, 30020, "99XX", 30020, 4.2, 15, 60, 12, None, None),
    _vorm(41, 1, 60999, "98ZZ", 60999, None, None, 80, 30, None, None),
]

STUDIES = [
    {"studieOpleidingCodeSkdb": 30020, "studieNaam": "ICT", "graad": "Bachelor", "soortHo": "HBO", "aansluitingStudieBaan": "goede", "opleidingType": "hbo - ict"},
    {"studieOpleidingCodeSkdb": 34560, "studieNaam": "Opleiding tot Verpleegkundige", "graad": "Bachelor", "soortHo": "HBO", "aansluitingStudieBaan": "zeer goede"},
    {"studieOpleidingCodeSkdb": 56604, "studieNaam": "Psychologie", "graad": "Bachelor", "soortHo": "WO", "aansluitingStudieBaan": "(missing, data wordt op dit niveau niet getoond)"},
    {"studieOpleidingCodeSkdb": 56990, "studieNaam": "Biomedische Wetenschappen", "graad": "Bachelor", "soortHo": "WO"},
    {"studieOpleidingCodeSkdb": 60260, "studieNaam": "Psychologie", "graad": "Master", "soortHo": "WO"},
    {"studieOpleidingCodeSkdb": 60999, "studieNaam": "Conflict Resolution and Governance", "graad": "Master", "soortHo": "WO"},
]


def _studievorm(code, vorm_id, graad, soort, rubriek, oordeel, eerstejaars):
    return {
        "studieOpleidingCodeSkdb": code, "studieVormId": vorm_id, "studieVorm": {1: "Voltijd", 2: "Deeltijd"}[vorm_id],
        "graad": graad, "soortHo": soort, "rubriekCode": rubriek, "algemeenOordeelGewogenGemiddelde": oordeel,
        "algemeenOordeelAantal": 1000, "eersteJaarAantal": eerstejaars, "doorstroomJaar2Perc": 75.55,
        "opleidingDiplomasPerc": 50.0,
    }


STUDIEVORMEN = [
    _studievorm(30020, 1, "Bachelor", "HBO", 48100, 3.5333, 5000),
    _studievorm(30020, 2, "Bachelor", "HBO", 48100, 3.66, 300),
    _studievorm(34560, 1, "Bachelor", "HBO", 72300, 3.8, 6000),
    _studievorm(56604, 1, "Bachelor", "WO", 31100, 3.93, 5064),
    _studievorm(56990, 1, "Bachelor", "WO", None, 4.0, 500),
]

SOI_VORMEN = [
    {"soiId": "48100-HBO-Bachelor", "studieVormId": 1, "rubriekNaam": "informatica", "maandSalarisMediaan": 3295, "werkloosPerc": 2.528, "baanOpNiveauPerc": 80.0, "vastContractPerc": 55.5},
    {"soiId": "48100-HBO-Bachelor", "studieVormId": 2, "rubriekNaam": "informatica"},
    {"soiId": "72300-HBO-Bachelor", "studieVormId": 1, "rubriekNaam": "verpleegkunde", "maandSalarisMediaan": 3100.5, "werkloosPerc": 0.5},
    {"soiId": "31100-WO-Bachelor", "studieVormId": 1, "rubriekNaam": "psychologie"},
]

DOORSTROOM_BM = [
    {"bachelorStudieOpleidingCodeSkdb": 56604, "masterStudieOpleidingCodeSkdb": 60260, "masterNaam": "Psychologie", "masterOpleidingCode": 60260, "doorstroomBachelorMasterAantal": 743, "doorstroomBachelorMasterPerc": 20.7, "doorstroomBachelorMasterRang": 2},
    {"bachelorStudieOpleidingCodeSkdb": 56604, "masterStudieOpleidingCodeSkdb": 66604, "masterNaam": "Psychology", "masterOpleidingCode": 66604, "doorstroomBachelorMasterAantal": 1572, "doorstroomBachelorMasterPerc": 43.91, "doorstroomBachelorMasterRang": 1},
]

DOORSTROOM_MBO = [
    {"doorstroomMboHboId": "b0589-34560", "mboKwalificatieId": "b0589", "mboNaam": "Mbo-Verpleegkundige", "studieNaam": "Opleiding tot Verpleegkundige", "studieOpleidingCodeSkdb": 34560, "graad": "Bachelor", "afgestudeerdenMboAantal": 8060, "doorstroomMboHboAantal": 571, "doorstroomMboHboPerc": 7.08, "doorstroomMboHboRang": 1},
    {"doorstroomMboHboId": "b0589-30020", "mboKwalificatieId": "b0589", "mboNaam": "Mbo-Verpleegkundige", "studieNaam": "ICT", "studieOpleidingCodeSkdb": 30020, "graad": "Bachelor", "afgestudeerdenMboAantal": 8060, "doorstroomMboHboAantal": 5, "doorstroomMboHboPerc": 0.06, "doorstroomMboHboRang": 2},
    {"doorstroomMboHboId": "b0100-30020", "mboKwalificatieId": "b0100", "mboNaam": "Software Developer", "studieNaam": "ICT", "studieOpleidingCodeSkdb": 30020, "graad": "Bachelor", "afgestudeerdenMboAantal": 3000, "doorstroomMboHboAantal": 600, "doorstroomMboHboPerc": 20.0, "doorstroomMboHboRang": 1},
]

LOTING = [
    {"instellingCode": "21PB", "opleidingCode": 56990, "opleidingNaam": "Biomedische Wetenschappen", "opleidingVorm": "Voltijd", "voerTaal": "Voertaal-overstijgend", "studieJaar": 2026, "capaciteit": 60, "kerenMeedoenAantal": 2, "aanmeldDatumUiterlijk": "15 januari", "lotingUrl": "https://example.org/bmw"},
    {"instellingCode": "21PB", "opleidingCode": 56990, "opleidingNaam": "Biomedische Wetenschappen", "opleidingVorm": "Voltijd", "voerTaal": "Voertaal-overstijgend", "studieJaar": 2027, "capaciteit": 71, "kerenMeedoenAantal": 2, "aanmeldDatumUiterlijk": "15 januari", "lotingUrl": "https://example.org/bmw"},
]

# De beschrijving van de export (#978): dezelfde velden als `exporttabellen` en `exportkolommen` van LCSK, met verzonnen
# omschrijvingen. De echte omschrijvingen zijn het gegevenswoordenboek van LCSK en staan niet in de repo.
EXPORTTABELLEN = [
    {"Tabel": "instellingen", "Endpoint": "/instellingen/{instellingSkdb}", "Omschrijving": "Proef: een instelling"},
    {"Tabel": "vestigingen", "Endpoint": "/instellingen/{instellingSkdb}/vestigingen/{vestigingSkdb}", "Omschrijving": "Proef: een vestiging"},
    {"Tabel": "tracks", "Endpoint": "/instellingen/{instellingSkdb}/vestigingen/{vestigingSkdb}/tracks/{hoviProductId}", "Omschrijving": "Proef: een track"},
    {"Tabel": "opleidingen", "Endpoint": "/opleidingen/{opleidingSkdb}", "Omschrijving": "Proef: een opleiding"},
    {"Tabel": "opleidingvormen", "Endpoint": "/opleidingen/{opleidingSkdb}/vormen/{opleidingVormId}", "Omschrijving": "Proef: een opleiding per vorm"},
    {"Tabel": "collegegelden", "Endpoint": "/opleidingen/{opleidingSkdb}/vormen/{opleidingVormId}/collegegelden/{collegeGeldId}", "Omschrijving": "Proef: wettelijk collegegeld"},
    {"Tabel": "studieadvies", "Endpoint": "/opleidingen/{opleidingSkdb}/programmas/{hoviProductId}/vormen/{hoviProductVorm}/studieadviezen/{studieAdviesId}", "Omschrijving": "Proef: studieadvies"},
    {"Tabel": "studies", "Endpoint": "/studies/{studieOpleidingCodeSkdb}", "Omschrijving": "Proef: een landelijke studie"},
    {"Tabel": "lotingopleidingendecentraleselecties", "Endpoint": "/instellingen/{instellingSkdb}/lotingopleidingendecentraleselecties/{lotingOpleidingDecentraleSelectieId}", "Omschrijving": "Proef: numerus fixus"},
]


def _kolommen(tabel: str, *kolommen: tuple[str, str]) -> list[dict]:
    return [{"Tabel": tabel, "Kolom": k, "Type": t, "Omschrijving": f"Proef: {k}"} for k, t in kolommen]


EXPORTKOLOMMEN = [
    *_kolommen("instellingen", ("instellingSkdb", "number"), ("instellingCode", "string"), ("instellingNaam", "string")),
    *_kolommen(
        "vestigingen", ("instellingSkdb", "number"), ("vestigingSkdb", "number"), ("gemeenteCode", "number"),
        ("studentenAantal", "number"),
    ),
    *_kolommen("tracks", ("instellingSkdb", "number"), ("vestigingSkdb", "number"), ("hoviProductId", "string"), ("trackNaam", "string")),
    *_kolommen(
        "opleidingen", ("opleidingSkdb", "number"), ("instellingSkdb", "number"), ("instellingCode", "string"),
        ("opleidingCode", "number"), ("studieOpleidingCodeSkdb", "number"),
    ),
    *_kolommen(
        "opleidingvormen", ("opleidingSkdb", "number"), ("opleidingVormId", "number"), ("enqueteJaar", "number"),
        ("algemeenOordeelGewogenGemiddelde", "number"), ("eersteJaarAantal", "number"),
    ),
    *_kolommen("collegegelden", ("opleidingSkdb", "number"), ("opleidingVormId", "number"), ("collegeGeldId", "number"), ("collegeGeldBedrag", "number")),
    *_kolommen(
        "studieadvies", ("opleidingSkdb", "number"), ("hoviProductId", "string"), ("hoviProductVorm", "string"),
        ("studieAdviesId", "number"), ("minimumEcts", "number"), ("studieAdviesBindend", "boolean"),
    ),
    *_kolommen("studies", ("studieOpleidingCodeSkdb", "number"), ("studieNaam", "string")),
    *_kolommen(
        "lotingopleidingendecentraleselecties", ("instellingSkdb", "number"), ("lotingOpleidingDecentraleSelectieId", "number"),
        ("opleidingCode", "number"), ("studieJaar", "number"), ("capaciteit", "number"),
    ),
]

TABELLEN = {
    "exporttabellen": EXPORTTABELLEN,
    "exportkolommen": EXPORTKOLOMMEN,
    "instellingen": INSTELLINGEN,
    "opleidingen": OPLEIDINGEN,
    "opleidingvormen": OPLEIDINGVORMEN,
    "studies": STUDIES,
    "studievormen": STUDIEVORMEN,
    "standaardonderwijsindelingvorm": SOI_VORMEN,
    "doorstroombachelormaster": DOORSTROOM_BM,
    "doorstroommbohbo": DOORSTROOM_MBO,
    "lotingopleidingendecentralesele": LOTING,  # zoals in de echte export: de naam is ingekort
}


def zip_bytes(tabellen: dict[str, list[dict]] | None = None, weglaten: tuple[str, ...] = ()) -> bytes:
    """De ZIP met `data/<tabel>.json` per tabel; `weglaten` haalt tabellen weg (voor de vormtoets)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for naam, rijen in (tabellen or TABELLEN).items():
            if naam not in weglaten:
                z.writestr(f"data/{naam}.json", json.dumps(rijen, ensure_ascii=False))
    return buffer.getvalue()


def standaard() -> tuple[bytes, Herkomst]:
    """De proefexport met haar herkomst, zoals `haal_op()` ze geeft."""
    inhoud = zip_bytes()
    return inhoud, herkomst(inhoud, BESTAND)
