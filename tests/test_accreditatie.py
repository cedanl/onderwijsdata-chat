"""Accreditatiedata per ho-opleiding uit DUO's Overzicht Erkenningen ho (#726, stap A).

De tool zoekt de instelling in het register en de opleiding op naam of CROHO-code, en geeft de datums die DUO over de
accreditatie registreert, elk met zijn betekenis uit code. Twee valkuilen uit het onderzoek: de inleverdatum is de
uiterste indiening voor de volgende beoordeling, nooit een einddatum; de vervaldatum hoort alleen bij een nieuwe
opleiding. Er zit geen NVAO-oordeel in, en dat zegt de tool zelf.

Een kleine synthetische fixture via het gewone DUO-laadpad (riodata's `load` gepatcht): geen echte download.
"""

import json
from datetime import date

import pandas as pd
import pytest

import tools
from agent.bronvermelding import bronlinks_van, bronnen_van
from tools import accreditatie
from tools.catalog import documentatie_url
from tools.schemas import TOOL_GET_ACCREDITATIE

_LEEG = dict.fromkeys(accreditatie.DATUMS) | {accreditatie.UITSTELREDEN: None}


def _rij(instelling, croho, naam, niveau="HBO-BA", status="ACTUEEL", vorm="VOLTIJD", **datums) -> dict:
    return {
        "INSTELLINGSCODE": instelling,
        "INSTELLINGSNAAM": "x",
        "VESTIGINGSCODE": f"{instelling}00",
        "ERKENDEOPLEIDINGSCODE": croho,
        "OPLEIDINGSEENHEID_NAAM": naam,
        "NIVEAU": niveau,
        "VORM": vorm,
        "STATUS": status,
        "BEGINDATUM_RECORD": datums.pop("begin_record", "2024-09-01"),
        "EINDDATUM_RECORD": datums.pop("einde_record", None),
        **_LEEG,
        **{f"ACCREDITATIE_{k.upper()}": v for k, v in datums.items()},
    }


# CROHO als getal, zoals pandas een kolom zonder tekstschema leest: 4181 moet "04181" worden.
_RIJEN = [
    _rij("25DW", 4181, "Laboratoriumtechniek", besluitdatum="2025-02-21", begindatum="2025-09-01",
         inleverdatum="2099-11-01"),
    _rij("25DW", 4181, "Laboratoriumtechniek", vorm="DEELTIJD", besluitdatum="2025-02-21", begindatum="2025-09-01",
         inleverdatum="2099-11-01"),
    _rij("25DW", 34035, "Bedrijfskunde", besluitdatum="2019-06-03", begindatum="2019-06-03",
         inleverdatum="2020-05-01", voorwaardendatum="2021-06-03", uitsteldatum="2027-05-02",
         uitstelreden="ART_5_16_LID_4", intrekkingsdatum="2028-01-01", afbouwdatum="2030-09-01",
         vervaldatum="2025-06-03"),
    _rij("25DW", 80074, "Bedrijfskunde", niveau="HBO-AD", besluitdatum="2024-01-10", inleverdatum="2029-05-01"),
    _rij("25DW", 4568, "Oude lerarenopleiding", status="HISTORISCH", einde_record="2008-01-01",
         besluitdatum="2002-01-01"),
    _rij("25DW", 39999, "Nieuwe opleiding", status="TOEKOMSTIG", begin_record="2027-09-01",
         besluitdatum="2026-09-21", vervaldatum="2032-01-14", inleverdatum="2031-11-01"),
    _rij("25DW", 30020, "ICT", besluitdatum="2025-02-21", inleverdatum="2030-11-01"),
    _rij("25DW", 30020, "ICT", vorm="DEELTIJD", besluitdatum="2024-02-21", inleverdatum="2030-11-01"),
    _rij("21PD", 56551, "Geneeskunde", niveau="WO-BA", besluitdatum="2023-03-01", inleverdatum="2029-05-01"),
    _rij("21PD", 50206, "Scheikunde", niveau="WO-BA", besluitdatum="2020-03-01", uitstelreden="ART_5_16_LID_4"),
    # N14 uit de review (#1005): een verlenging die op het peilmoment van 10-11-2026 al voorbij is.
    _rij("21PB", 56604, "Psychologie", niveau="WO-BA", besluitdatum="2019-11-02", begindatum="2019-11-02",
         inleverdatum="2025-05-01", uitsteldatum="2026-11-02", uitstelreden="ART_5_16_LID_4"),
]  # fmt: skip

_PROFIELEN = {
    "hu": {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"},
    "uu": {"naam": "Universiteit Utrecht", "sector": "wo", "instellingscode": "21PD"},
    "universiteit leiden": {"naam": "Universiteit Leiden", "sector": "wo", "instellingscode": "21PB"},
    "roc midden nederland": {"naam": "ROC Midden Nederland", "sector": "mbo", "instellingscode": "25PZ"},
    "lege hogeschool": {"naam": "Lege Hogeschool", "sector": "hbo", "instellingscode": "99XX"},
}


def _versie(monkeypatch, last_modified: str | None) -> None:
    """Het DUO-laadpad met de fixture, als bestand dat DUO op `last_modified` verving: dat geeft het peilmoment."""

    def laad(dataset_id, resource=0, **_):
        assert (dataset_id, resource) == (accreditatie.DATASET, accreditatie.BESTAND)
        df = pd.DataFrame(_RIJEN)
        df.attrs["bron"] = {"last_modified": last_modified, "md5": None}
        return df

    monkeypatch.setattr("tools.duo._duo.load", laad)


@pytest.fixture
def tool(monkeypatch):
    _versie(monkeypatch, "2026-10-30T03:04:43")
    monkeypatch.setattr(
        accreditatie.instellingen, "instellingsprofiel", lambda naam: _PROFIELEN.get(naam.strip().lower())
    )
    return accreditatie.get_accreditatie


def test_de_datums_met_hun_betekenis_peilmoment_en_bron(tool):
    uit = json.loads(tool("HU", "Laboratoriumtechniek"))

    assert uit["instelling"] == {"naam": "Hogeschool Utrecht", "instellingscode": "25DW"}
    assert uit["opleiding"] == {
        "croho": "04181",
        "naam": "Laboratoriumtechniek",
        "niveau": ["hbo bachelor"],
        "vormen": ["deeltijd", "voltijd"],
    }
    assert {k: v["datum"] for k, v in uit["datums"].items()} == {
        "besluitdatum": "21-02-2025",
        "begindatum": "01-09-2025",
        "uiterste_indiening_volgende_beoordeling": "01-11-2099",
    }
    assert "NVAO" in uit["datums"]["besluitdatum"]["betekenis"]
    assert "actuele OCW-erkende opleiding" in uit["erkenning"]
    assert uit["bron"] == {
        "naam": "DUO, Overzicht Erkenningen ho",
        "url": documentatie_url(accreditatie.DATASET),
        "licentie": "CC0 1.0 (DUO, hergebruik open onderwijsdata)",  # één regel voor elke DUO-bron (#971)
        "data_key": "duo:overzicht-erkenningen-ho:0",
        "peilmoment": "versie van 30-10-2026",
    }


def test_elk_datumveld_heeft_een_eigen_betekenis(tool):
    uit = json.loads(tool("HU", "34035"))
    datums = uit["datums"]

    assert {k: v["datum"] for k, v in datums.items()} == {
        "besluitdatum": "03-06-2019",
        "begindatum": "03-06-2019",
        "uiterste_indiening_volgende_beoordeling": "01-05-2020",
        "uiterste_indiening_voorwaarden": "03-06-2021",
        "verlengd_tot": "02-05-2027",
        "intrekking": "01-01-2028",
        "afbouw": "01-09-2030",
        "vervaldatum_nieuwe_opleiding": "03-06-2025",
    }
    assert datums["verlengd_tot"]["grond"] == "artikel 5.16 lid 4 WHW"
    assert "voorwaarden" in datums["uiterste_indiening_voorwaarden"]["betekenis"]
    assert "intrekkingsbesluit" in datums["intrekking"]["betekenis"]
    assert "zittende studenten" in datums["afbouw"]["betekenis"]
    assert "alleen bij nieuwe opleidingen" in datums["vervaldatum_nieuwe_opleiding"]["betekenis"]


def test_de_inleverdatum_is_nooit_een_einddatum(tool):
    uit = json.loads(tool("HU", "34035"))
    inlever = uit["datums"]["uiterste_indiening_volgende_beoordeling"]

    assert "Geen einddatum" in inlever["betekenis"] and "nooit 'geaccrediteerd tot'" in inlever["betekenis"]
    # De datum staat onder geen andere sleutel, en geen sleutel noemt een einde.
    assert [k for k, v in uit["datums"].items() if v["datum"] == "01-05-2020"] == [
        "uiterste_indiening_volgende_beoordeling"
    ]
    assert not [k for k in uit["datums"] if ("tot" in k and k != "verlengd_tot") or "eind" in k]
    # Ligt hij in het verleden, dan zegt een noot dat de accreditatie daarmee niet verlopen is.
    assert "niet dat de accreditatie is verlopen" in uit["noot"]
    assert "verlopen" not in json.loads(tool("HU", "Laboratoriumtechniek"))["noot"]


def test_geen_oordeel_en_geen_ranglijst(tool):
    uit = json.loads(tool("UU", "Geneeskunde"))
    assert "geen oordeel van de NVAO" in uit["geen_oordeel"] and "(nog) niet in deze app" in uit["geen_oordeel"]
    assert "rangschik" in uit["noot"]
    assert not {"oordeel", "verdict", "decision"} & set(uit) and uit["opleiding"]["niveau"] == ["wo bachelor"]


@pytest.mark.parametrize("gevraagd", ["4181", "04181", " 04181 ", "laboratoriumtechniek"])
def test_croho_als_tekst_met_voorloopnullen(tool, gevraagd):
    assert json.loads(tool("HU", gevraagd))["opleiding"]["croho"] == "04181"


@pytest.mark.parametrize(
    ("waarde", "code"),
    [(4181, "04181"), (4181.0, "04181"), ("4181", "04181"), ("04181", "04181"), ("34035", "34035"), (None, None)],
)
def test_croho_normalisatie(waarde, code):
    assert accreditatie.croho(waarde) == code


def test_meer_opleidingen_met_dezelfde_naam_vraagt_om_de_code_met_het_niveau(tool):
    uit = tool("HU", "Bedrijfskunde")
    assert "Bedrijfskunde, hbo bachelor (34035)" in uit and "Bedrijfskunde, hbo associate degree (80074)" in uit
    assert not uit.startswith("{")


def test_een_alleen_historische_opleiding_is_geen_actuele_erkenning(tool):
    uit = tool("HU", "04568")
    assert "alleen nog als historische registratie (laatste registratie tot 01-01-2008)" in uit
    assert not uit.startswith("{")


def test_een_toekomstige_registratie_is_nog_geen_actuele_erkenning(tool):
    uit = json.loads(tool("HU", "Nieuwe opleiding"))
    assert "toekomstige registratie" in uit["erkenning"] and "01-09-2027" in uit["erkenning"]
    assert uit["datums"]["vervaldatum_nieuwe_opleiding"]["datum"] == "14-01-2032"


def test_tegenstrijdige_datums_per_vorm_geven_geen_gok(tool):
    uit = tool("HU", "ICT")
    assert "verschillende accreditatiedatums" in uit and not uit.startswith("{")


@pytest.mark.parametrize(
    ("instelling", "opleiding", "tekst"),
    [
        ("Hogeschool Nergens", "ICT", "Onbekende instelling"),
        ("HU", "Luchtvaart", "Geen opleiding 'Luchtvaart' bij deze instelling"),
        ("HU", "", "Geef de opleiding"),
        ("ROC Midden Nederland", "Verzorgende", "mbo-instelling"),
        ("Lege Hogeschool", "ICT", "staat niet in DUO, Overzicht Erkenningen ho"),
    ],
)
def test_zonder_accreditatie_een_vaste_melding(tool, instelling, opleiding, tekst):
    uit = tool(instelling, opleiding)
    assert tekst in uit and not uit.startswith("{")


def test_een_gewijzigd_formaat_faalt_gesloten(tool, monkeypatch):
    monkeypatch.setattr(
        "tools.duo._duo.load", lambda *a, **k: pd.DataFrame(_RIJEN).drop(columns=["ACCREDITATIE_INLEVERDATUM"])
    )
    uit = tool("HU", "Laboratoriumtechniek")
    assert "mist de kolommen ACCREDITATIE_INLEVERDATUM" in uit and not uit.startswith("{")


def test_de_tool_staat_in_de_dispatch_en_de_bron_onder_het_antwoord(tool):
    uit, _ = tools.dispatch(TOOL_GET_ACCREDITATIE, {"instelling": "HU", "opleiding": "Laboratoriumtechniek"})
    stap = (TOOL_GET_ACCREDITATIE, uit)

    regel = (
        "DUO · Overzicht Erkenningen ho, versie van 30-10-2026, bestand HO_Erkenningen_RIO (overzicht-erkenningen-ho)"
    )
    assert bronnen_van([stap]) == [regel]
    assert bronlinks_van([stap]) == {regel: documentatie_url(accreditatie.DATASET)}
    assert TOOL_GET_ACCREDITATIE in tools.LABELS


# ─── #1005: een verstreken termijn staat in code, niet in de rekenkunde van het model ────────────────────────────────

_N14_ZIN = (
    "De verlenging liep tot 02-11-2026; het DUO-overzicht van 10-11-2026 toont geen nieuwer besluit. "
    "De status na die datum staat niet in deze bron."
)


def test_een_verlenging_voor_het_peilmoment_is_verstreken_met_een_vaste_zin(tool, monkeypatch):
    _versie(monkeypatch, "2026-11-10T03:12:00")
    uit = json.loads(tool("Universiteit Leiden", "Psychologie"))

    assert uit["bron"]["peilmoment"] == "versie van 10-11-2026"
    verlengd = uit["datums"]["verlengd_tot"]
    assert verlengd["datum"] == "02-11-2026" and verlengd["verstreken"] is True
    assert verlengd["grond"] == "artikel 5.16 lid 4 WHW"
    assert _N14_ZIN in uit["noot"]
    assert uit["noot"].count("De verlenging liep tot") == 1


def test_een_verlenging_na_het_peilmoment_is_niet_verstreken(tool):
    uit = json.loads(tool("HU", "34035"))  # verlengd tot 02-05-2027, peilmoment 30-10-2026

    assert uit["datums"]["verlengd_tot"]["verstreken"] is False
    assert "De verlenging liep tot" not in uit["noot"]


def test_elke_einddatum_van_een_termijn_krijgt_verstreken_tegen_het_peilmoment(tool):
    datums = json.loads(tool("HU", "34035"))["datums"]

    assert {k: v.get("verstreken") for k, v in datums.items()} == {
        "besluitdatum": None,
        "begindatum": None,
        "uiterste_indiening_volgende_beoordeling": None,
        "uiterste_indiening_voorwaarden": None,
        "verlengd_tot": False,
        "intrekking": False,
        "afbouw": False,
        "vervaldatum_nieuwe_opleiding": True,  # 03-06-2025, vóór 30-10-2026
    }
    assert not [k for k in ("besluitdatum", "begindatum") if "verstreken" in datums[k]]


def test_een_verlenging_met_alleen_een_grond_heeft_geen_verstreken(tool):
    uit = json.loads(tool("UU", "Scheikunde"))

    assert uit["datums"]["verlengd_tot"] == {
        "datum": None,
        "betekenis": accreditatie.DATUMS["ACCREDITATIE_UITSTELDATUM"].betekenis,
        "grond": "artikel 5.16 lid 4 WHW",
    }
    assert "De verlenging liep tot" not in uit["noot"]


def test_de_uiterste_indiening_blijft_zoals_hij_was(tool, monkeypatch):
    _versie(monkeypatch, "2026-11-10T03:12:00")
    uit = json.loads(tool("Universiteit Leiden", "Psychologie"))

    assert uit["datums"]["uiterste_indiening_volgende_beoordeling"] == {
        "datum": "01-05-2025",
        "betekenis": accreditatie.DATUMS[accreditatie.INLEVERDATUM].betekenis,
    }
    assert (
        "De uiterste indiening voor de volgende beoordeling (01-05-2025) ligt vóór vandaag. Dat betekent niet dat de "
        "accreditatie is verlopen: de beoordeling kan lopen of verlengd zijn. Trek er geen conclusie uit over de status."
    ) in uit["noot"]
    assert "liep tot 01-05-2025" not in uit["noot"]


@pytest.mark.parametrize(
    ("peilmoment", "dag"),
    [
        ("versie van 10-11-2026", date(2026, 11, 10)),
        (None, date(2026, 1, 5)),
        ("", date(2026, 1, 5)),
        ("versie onbekend", date(2026, 1, 5)),
        ("versie van 31-02-2026", date(2026, 1, 5)),
    ],
)
def test_de_peildag_komt_uit_het_peilmoment_en_anders_vandaag(peilmoment, dag):
    assert accreditatie.peildag(peilmoment, date(2026, 1, 5)) == dag


class _Op10November(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 10)


def test_zonder_peilmoment_telt_vandaag(tool, monkeypatch):
    _versie(monkeypatch, None)
    monkeypatch.setattr(accreditatie, "date", _Op10November)
    uit = json.loads(tool("Universiteit Leiden", "Psychologie"))

    assert "peilmoment" not in uit["bron"]
    assert uit["datums"]["verlengd_tot"]["verstreken"] is True
    assert _N14_ZIN in uit["noot"]
