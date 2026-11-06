"""Personeel van de universiteiten uit WOPI (#936), op het synthetische proefbestand van `onderwijsbronnen.unl`.

Acceptatie van #936: "Hoeveel wetenschappelijk personeel heeft de Universiteit Utrecht?" geeft fte met peildatum,
de variant zonder GEZO en de vaste voorbehouden; een vraag over een hogeschool of mbo zegt dat er geen open bron is.
Controlewaarden (#731): UU 6.184,36 fte, waarvan 3.584,05 wetenschappelijk (zonder GEZO); landelijk 58.462,07
(zonder) en 61.371,30 (met GEZO), peildatum 31-12-2025.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pandas as pd
import pytest
from onderwijsbronnen import unl
from onderwijsbronnen.unl import proefbestand

import tools
from agent.bronvermelding import bronlinks_van, bronnen_van
from agent.grounding import bewijs_getallen
from core import config
from data import instellingen
from tools import catalog, snippet, store, wo_personeel
from tools.schemas import SCHEMA_GET_WO_PERSONEEL, TOOL_GET_WO_PERSONEEL, TOOL_SCHEMAS

ROOT = Path(__file__).resolve().parent.parent

# Het register (DUO) zoals instellingsprofiel het geeft; zonder netwerk.
_REGISTER = {
    "universiteit utrecht": ("Universiteit Utrecht", "wo", "21PD"),
    "uu": ("Universiteit Utrecht", "wo", "21PD"),
    "wageningen university": ("Wageningen University", "wo", "21PI"),
    "hogeschool utrecht": ("Hogeschool Utrecht", "hbo", "25DW"),
    "25dw": ("Hogeschool Utrecht", "hbo", "25DW"),  # het register kent ook BRIN-codes (#929)
    "roc midden nederland": ("ROC Midden Nederland", "mbo", "25PZ"),
    "theologische universiteit apeldoorn": ("Theologische Universiteit Apeldoorn", "wo", "21QO"),
}


def _profiel(naam: str) -> dict | None:
    gevonden = _REGISTER.get(" ".join(naam.split()).lower())
    if gevonden is None:
        return None
    return {"naam": gevonden[0], "sector": gevonden[1], "instellingscode": gevonden[2]}


@pytest.fixture(autouse=True)
def proefbestand_en_register(monkeypatch):
    monkeypatch.setattr(unl, "haal_op", proefbestand.standaard)
    monkeypatch.setattr(instellingen, "instellingsprofiel", _profiel)
    wo_personeel._wopi.cache_clear()
    yield
    wo_personeel._wopi.cache_clear()


def _uit(**kwargs) -> dict:
    return json.loads(wo_personeel.get_wo_personeel(**kwargs))


def _rij(**kwargs) -> dict:
    [rij] = _uit(**kwargs)["cijfers"]
    return rij


# --- acceptatie --------------------------------------------------------------------------------------------------


def test_wetenschappelijk_personeel_van_de_universiteit_utrecht():
    uit = _uit(instelling="Universiteit Utrecht", uitsplitsing="wp_obp")

    assert uit["instelling"] == {"naam": "Universiteit Utrecht", "brin": "21PD"}
    assert (uit["eenheid"], uit["gezo"]) == ("fte", "excl")
    [rij] = uit["cijfers"]
    assert rij == {
        "jaar": 2025,
        "peildatum": "31-12-2025",
        "totaal": 6184.36,
        "obp": 2600.31,
        "wetenschappelijk_personeel": 3584.05,
    }
    assert uit["voorbehouden"][:3] == [wo_personeel.PEILDATUM, wo_personeel.FTE_GEEN_PERSONEN, wo_personeel.UITGESLOTEN]
    assert wo_personeel.GEZO_UITLEG["excl"] in uit["voorbehouden"]
    assert uit["definitie"] == wo_personeel.WP
    assert (
        uit["bron"]["regel"] == "WOPI 2025, Universiteiten van Nederland, peildatum 31-12-2025, excl. sector Gezondheid"
    )


@pytest.mark.parametrize("uitsplitsing", [None, ""])
def test_de_algemene_personeelsvraag_geeft_wp_en_obp_naast_het_totaal(uitsplitsing):
    """#965: "Hoeveel personeel werkt er bij de UU?" gaf alleen 6.184,36 fte; WP en OBP horen er standaard bij."""
    standaard = _uit(instelling="Universiteit Utrecht")
    assert standaard["uitsplitsing"] == "wp_obp" and standaard["definitie"] == wo_personeel.WP
    assert standaard["cijfers"] == _uit(instelling="UU", uitsplitsing="wp_obp")["cijfers"]
    [rij] = standaard["cijfers"]
    assert (rij["totaal"], rij["wetenschappelijk_personeel"], rij["obp"]) == (6184.36, 3584.05, 2600.31)
    assert _uit(instelling="UU", uitsplitsing=uitsplitsing)["uitsplitsing"] == "wp_obp"
    # Alleen het totaal blijft mogelijk, op verzoek; personen kennen geen WP/OBP en houden het totaal als standaard.
    assert set(_rij(instelling="UU", uitsplitsing="geen")) == {"jaar", "peildatum", "totaal"}
    assert _uit(eenheid="personen")["uitsplitsing"] == "geen"
    # De herlaadaanroep in de store en de snippet noemen de uitsplitsing die de app koos.
    meta = store.meta(standaard["data_key"])
    assert meta is not None and meta.laad is not None and meta.laad[1]["uitsplitsing"] == "wp_obp"


def test_het_schema_noemt_wp_obp_als_standaard():
    beschrijving = SCHEMA_GET_WO_PERSONEEL["function"]["parameters"]["properties"]["uitsplitsing"]["description"]
    assert beschrijving.startswith("wp_obp (standaard bij fte")
    assert "geen (alleen het totaal" in beschrijving


@pytest.mark.parametrize(
    "instelling", ["Hogeschool Utrecht", "25DW", "ROC Midden Nederland", "hbo", "mbo", "hogescholen"]
)
def test_een_hogeschool_of_mbo_heeft_geen_open_bron(instelling):
    uit = wo_personeel.get_wo_personeel(instelling=instelling)

    assert wo_personeel.GEEN_OPEN_BRON_HO_MBO in uit
    assert not any(c.isdigit() for c in uit.replace("25DW", "").replace("25PZ", ""))


# --- controlewaarden en varianten --------------------------------------------------------------------------------


def test_landelijk_zonder_gezo_is_de_standaard():
    uit = _uit()
    assert uit["instelling"] == "landelijk" and uit["landelijk"] == wo_personeel.LANDELIJK_UITLEG
    assert uit["cijfers"][0]["totaal"] == 58462.07


def test_met_gezo_alleen_op_verzoek_en_dan_in_de_bronregel():
    uit = _uit(gezo="incl")
    assert uit["cijfers"][0]["totaal"] == 61371.30
    assert uit["bron"]["regel"].endswith("incl. sector Gezondheid")
    assert wo_personeel.GEZO_UITLEG["incl"] in uit["voorbehouden"]


@pytest.mark.parametrize("gezo", ["beide", "excl+incl", "gemengd"])
def test_nooit_gemengd(gezo):
    assert "nooit beide of gemengd" in wo_personeel.get_wo_personeel(gezo=gezo)


def test_brin_en_naam_uit_wopi_zonder_register(monkeypatch):
    assert _uit(instelling="21pd")["instelling"]["brin"] == "21PD"
    monkeypatch.setattr(instellingen, "instellingsprofiel", lambda naam: None)  # register niet geladen
    assert _uit(instelling="universiteit utrecht")["instelling"]["brin"] == "21PD"


def test_een_wo_naam_uit_duo_die_anders_is_in_wopi():
    """WOPI zegt 'Wageningen Universiteit', DUO 'Wageningen University': koppelen gaat op BRIN."""
    assert _uit(instelling="Wageningen University")["instelling"] == {"naam": "Wageningen Universiteit", "brin": "21PI"}


@pytest.mark.parametrize("instelling", ["Theologische Universiteit Apeldoorn", "23BF", "00dv"])
def test_de_vier_wo_instellingen_buiten_wopi_krijgen_een_vaste_melding_geen_nul(instelling):
    uit = wo_personeel.get_wo_personeel(instelling=instelling)
    assert "geen lid van Universiteiten van Nederland" in uit and "ook geen 0" in uit
    assert not uit.startswith("{")


def test_een_onbekende_instelling_is_geen_gok():
    uit = wo_personeel.get_wo_personeel(instelling="Universiteit van Nergens")
    assert uit.startswith("Onbekende instelling") and "Universiteit Utrecht" in uit


def test_wp_obp_functie_en_totaal_komen_uit_dezelfde_records():
    functie = _rij(instelling="UU", uitsplitsing="functie")
    codes = set(wo_personeel.FUNCTIES)
    assert round(sum(v for k, v in functie.items() if k in codes), 2) == functie["totaal"] == 6184.36
    assert set(_uit(uitsplitsing="functie")["functies"]) == codes


def test_vast_en_tijdelijk_met_het_aandeel_uit_code():
    rij = _rij(instelling="UU", uitsplitsing="vast_tijdelijk")
    assert round(rij["vast"] + rij["tijdelijk"], 2) == rij["totaal"]
    assert rij["aandeel_tijdelijk_procent"] == round(100 * rij["tijdelijk"] / rij["totaal"], 1)


def test_geslacht_geeft_vrouwen_en_aandeel_maar_geen_mannen():
    uit = _uit(instelling="UU", uitsplitsing="geslacht")
    [rij] = uit["cijfers"]
    assert rij["aandeel_vrouwen_procent"] == round(100 * rij["vrouwen"] / rij["totaal"], 1)
    assert not any("man" in k for k in rij)
    assert "Leid geen aantal mannen af" in uit["noot"]


def test_personen_per_universiteit_en_per_leeftijd():
    uit = _uit(eenheid="personen")
    assert uit["cijfers"][0]["totaal"] == 66723
    assert wo_personeel.PERSONEN in uit["voorbehouden"] and wo_personeel.FTE_GEEN_PERSONEN not in uit["voorbehouden"]
    rij = _rij(instelling="UU", eenheid="personen", uitsplitsing="leeftijd")
    assert rij["totaal"] == 7076 and rij["<25"] == 1000
    assert _rij(eenheid="personen", gezo="incl")["totaal"] == 70266


@pytest.mark.parametrize(
    ("args", "melding"),
    [
        ({"eenheid": "personen", "uitsplitsing": "functie"}, "Met eenheid 'fte' kan het wel"),
        ({"uitsplitsing": "leeftijd"}, "Met eenheid 'personen' kan het wel"),
        ({"uitsplitsing": "hoop"}, "HOOP-gebied"),
        ({"eenheid": "koppen"}, "bestaat niet"),
    ],
)
def test_wat_het_bestand_niet_heeft_is_een_weigering(args, melding):
    uit = wo_personeel.get_wo_personeel(**args)
    assert melding in uit and not uit.startswith("{")


# --- jaren en breuken in de reeks --------------------------------------------------------------------------------


def test_een_reeks_loopt_over_alle_jaren_van_de_editie():
    assert [r["jaar"] for r in _uit(reeks=True)["cijfers"]] == [2002, 2005, 2024, 2025]


def test_met_gezo_begint_de_reeks_in_2006_en_een_jaar_ervoor_wordt_geweigerd():
    uit = _uit(reeks=True, gezo="incl")
    assert [r["jaar"] for r in uit["cijfers"]] == [2024, 2025]
    assert "begint in 2006" in uit["noot"]
    assert "niet vergelijkbaar" in wo_personeel.get_wo_personeel(jaar=2005, gezo="incl")


def test_vast_tijdelijk_bestaat_pas_vanaf_2003():
    assert [r["jaar"] for r in _uit(reeks=True, uitsplitsing="vast_tijdelijk")["cijfers"]] == [2005, 2024, 2025]
    assert "pas vanaf 2003" in wo_personeel.get_wo_personeel(jaar=2002, uitsplitsing="vast_tijdelijk")


def test_docent_en_onderzoeker_vanaf_2005_in_een_noot():
    assert "pas vanaf 2005" in _uit(reeks=True, uitsplitsing="functie")["noot"]
    assert "noot" not in _uit(jaar=2025, uitsplitsing="functie")


@pytest.mark.parametrize("jaar", [1990, 2030, "vorig jaar"])
def test_een_jaar_buiten_de_editie_geeft_geen_getal(jaar):
    uit = wo_personeel.get_wo_personeel(jaar=jaar)
    assert "Noem geen getal" in uit or "geen jaar" in uit


# --- fouten bij de bron ------------------------------------------------------------------------------------------


def test_een_afwijkend_bestand_geeft_een_bronfout(monkeypatch):
    def kapot():
        inhoud = proefbestand.maak({"DL schaal uni": []})
        return inhoud, proefbestand.herkomst(inhoud)

    monkeypatch.setattr(unl, "haal_op", kapot)
    uit = wo_personeel.get_wo_personeel()
    assert "bron_fout" in uit and "wijkt af van de bekende opbouw" in uit


def test_een_onbereikbare_bron_geeft_een_bronfout(monkeypatch):
    def onbereikbaar():
        raise httpx.ConnectError("geen verbinding")

    monkeypatch.setattr(unl, "haal_op", onbereikbaar)
    assert "niet bereikbaar" in wo_personeel.get_wo_personeel()


def test_het_bestand_wordt_een_keer_per_ttl_opgehaald(monkeypatch):
    aanroepen = []

    def tel():
        aanroepen.append(1)
        return proefbestand.standaard()

    monkeypatch.setattr(unl, "haal_op", tel)
    wo_personeel.get_wo_personeel()
    wo_personeel.get_wo_personeel(instelling="UU")
    assert len(aanroepen) == 1


# --- naden: bronregel, getalcontrole, snippet, catalogus, vlag ---------------------------------------------------


def test_de_vaste_bronregel_staat_onder_het_antwoord():
    stap = (TOOL_GET_WO_PERSONEEL, wo_personeel.get_wo_personeel(instelling="UU", gezo="incl"))
    regel = "WOPI 2025, Universiteiten van Nederland, peildatum 31-12-2025, incl. sector Gezondheid"
    assert bronnen_van([stap]) == [regel]
    assert bronlinks_van([stap]) == {regel: unl.PAGINA}


def test_de_getallen_zijn_bewijs_voor_de_getalcontrole():
    assert {"6184", "3584"} <= bewijs_getallen(wo_personeel.get_wo_personeel(instelling="UU", uitsplitsing="wp_obp"))


def _snippet_df(args: dict, monkeypatch):
    """Draai de snippet zoals een gebruiker, met `unl.haal_op` op het proefbestand (geen netwerk)."""
    resultaat = wo_personeel.get_wo_personeel(**args)
    code = snippet.generate(TOOL_GET_WO_PERSONEEL, args, resultaat)
    assert code is not None
    monkeypatch.setattr(unl.wopi, "haal_op", proefbestand.standaard)
    ruimte: dict = {}
    exec(compile(code, "<snippet>", "exec"), ruimte)
    return code, ruimte["df"], json.loads(resultaat)


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"instelling": "Universiteit Utrecht", "uitsplitsing": "wp_obp"},
        {"instelling": "uu", "gezo": "incl", "uitsplitsing": "functie"},
        {"reeks": True, "uitsplitsing": "functie"},
        {"instelling": "21pd", "reeks": True, "uitsplitsing": "vast_tijdelijk"},
        {"instelling": "Wageningen University", "uitsplitsing": "geslacht"},
        {"eenheid": "personen", "uitsplitsing": "leeftijd", "reeks": True},
        {"eenheid": "personen", "uitsplitsing": "geslacht", "gezo": "incl"},
    ],
    ids=lambda a: ",".join(f"{k}={v}" for k, v in a.items()) or "standaard",
)
def test_de_snippet_rekent_hetzelfde_als_de_app(args, monkeypatch, capsys):
    """Equivalentie (#945): de snippet laadt met de keuze van de app (BRIN, jaren) en geeft dezelfde cijfers, en precies
    de tabel die de app in de store zet en exporteert (#956)."""
    code, df, uit = _snippet_df(args, monkeypatch)

    selectie = ("instelling", "eenheid", "gezo")
    verwacht = [{k: v for k, v in rij.items() if k != "peildatum"} for rij in uit["cijfers"]]
    gekregen = json.loads(df.drop(columns=list(selectie)).to_json(orient="records"))
    assert gekregen == verwacht
    pd.testing.assert_frame_equal(df, store.get(uit["data_key"]))
    assert "from onderwijsbronnen import unl" in code
    assert "# Gemaakt met onderwijsbronnen" in code, "de snippetkop noemt het pakket en de installatieregel"
    assert uit["bron"]["regel"] in code
    if isinstance(uit["instelling"], dict):
        assert f'== "{uit["instelling"]["brin"]}"' in code  # de BRIN van de app, niet de naam uit de vraag


def test_een_weigering_geeft_geen_snippet():
    weigering = wo_personeel.get_wo_personeel(instelling="Hogeschool Utrecht")
    assert snippet.generate(TOOL_GET_WO_PERSONEEL, {"instelling": "Hogeschool Utrecht"}, weigering) is None


def test_unl_staat_niet_in_de_zoekcatalogus_van_de_chat():
    assert not any(r.get("_unl_id") for r in catalog._rio_duo_alles())


def test_zonder_vlag_staat_de_tool_niet_in_de_toolset():
    assert config.WO_PERSONEEL_ENABLED is False
    assert SCHEMA_GET_WO_PERSONEEL not in TOOL_SCHEMAS
    melding, _ = tools.dispatch(TOOL_GET_WO_PERSONEEL, {})
    assert melding == f"Onbekende tool: {TOOL_GET_WO_PERSONEEL}"


def test_met_vlag_staat_de_tool_in_de_toolset_en_de_dispatch():
    """In een eigen proces: de vlag wordt bij import gelezen, en herladen zou de andere tests raken."""
    code = (
        "import tools; from tools.schemas import TOOL_SCHEMAS, SCHEMA_GET_WO_PERSONEEL;"
        "assert SCHEMA_GET_WO_PERSONEEL in TOOL_SCHEMAS; assert 'get_wo_personeel' in tools._HANDLERS;"
        "assert 'get_wo_personeel' in tools.LABELS; print('ok')"
    )
    omgeving = {**os.environ, "ENABLE_WO_PERSONEEL": "true"}
    uit = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=omgeving, capture_output=True, text=True, timeout=120
    )
    assert uit.returncode == 0, uit.stderr[-2000:]
    assert uit.stdout.strip().endswith("ok")


def test_het_schema_past_op_de_handler():
    params = SCHEMA_GET_WO_PERSONEEL["function"]["parameters"]
    import inspect

    signatuur = inspect.signature(wo_personeel.get_wo_personeel).parameters
    assert set(params["properties"]) <= set(signatuur)
    assert params["properties"]["uitsplitsing"]["enum"] == list(wo_personeel.UITSPLITSINGEN)
    assert params["properties"]["eenheid"]["enum"] == list(wo_personeel.EENHEDEN)
    assert params["properties"]["gezo"]["enum"] == list(unl.GEZO)
    beschrijving = SCHEMA_GET_WO_PERSONEEL["function"]["description"]
    assert "hogeschool" in beschrijving and "geen open bron" in beschrijving and "gezo='excl'" in beschrijving


def test_de_vlag_staat_alleen_op_test_aan():
    def vlag(omgeving: str) -> str | None:
        tekst = (ROOT / "manifests" / omgeving / "values.yaml").read_text(encoding="utf-8")
        regels = tekst.splitlines()
        for i, regel in enumerate(regels):
            if regel.strip() == "- name: ENABLE_WO_PERSONEEL":
                return regels[i + 1].split(":", 1)[1].strip().strip('"')
        return None

    assert vlag("test") == "true"
    assert vlag("playground") is None and vlag("production") is None
