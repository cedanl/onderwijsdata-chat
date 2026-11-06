"""get_studiekeuze (#957): de Studiekeuzedatabase van LCSK in de chat.

Er staat geen data van LCSK in de repo; `onderwijsbronnen.skdb.proefbestand` bouwt een export met dezelfde vorm en
verzonnen getallen. Het register (DUO) staat hier als woordenboek, zonder netwerk.
"""

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pandas as pd
import pytest
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

import tools
from agent.bronvermelding import bronlinks_van, bronnen_van
from agent.grounding import bewijs_getallen
from agent.meetwaarden import meetwaarden
from core import config
from data import instellingen
from tools import beschikbaarheid, catalog, snippet, store, studiekeuze
from tools.schemas import SCHEMA_GET_STUDIEKEUZE, TOOL_GET_STUDIEKEUZE, TOOL_SCHEMAS

ROOT = Path(__file__).resolve().parent.parent

_REGISTER = {
    "hogeschool utrecht": ("Hogeschool Utrecht", "hbo", "25DW"),
    "hu": ("Hogeschool Utrecht", "hbo", "25DW"),
    "universiteit utrecht": ("Universiteit Utrecht", "wo", "21PD"),
    "roc midden nederland": ("ROC Midden Nederland", "mbo", "25PZ"),
}


def _profiel(naam: str) -> dict | None:
    gevonden = _REGISTER.get(" ".join(naam.split()).lower())
    return None if gevonden is None else {"naam": gevonden[0], "sector": gevonden[1], "instellingscode": gevonden[2]}


@pytest.fixture(autouse=True)
def proefexport_en_register(monkeypatch):
    monkeypatch.setattr(skdb, "haal_op", lambda *a, **k: proefbestand.standaard())
    monkeypatch.setattr(instellingen, "instellingsprofiel", _profiel)
    studiekeuze._export.cache_clear()
    yield
    studiekeuze._export.cache_clear()


def _uit(**kwargs) -> dict:
    return json.loads(studiekeuze.get_studiekeuze(**kwargs))


# --- acceptatie: de vijf weergaven ---------------------------------------------------------------------------------


def test_opleidingen_van_een_instelling_met_het_landelijke_oordeel_ernaast():
    uit = _uit(instelling="Hogeschool Utrecht", opleiding="ICT", vorm="voltijd")
    (rij,) = uit["rijen"]
    assert (rij["brin"], rij["croho"], rij["nse_oordeel"], rij["nse_oordeel_landelijk"]) == ("25DW", 30020, 3.61, 3.53)
    assert uit["instelling"] == {"naam": "Hogeschool Utrecht", "brin": "25DW"}
    assert uit["selectie"] == {"weergave": "opleidingen", "instelling": "25DW", "opleiding": "ICT", "vorm": "voltijd"}
    assert "nse_docenten" in rij  # weinig rijen: de NSE-thema's erbij
    assert any("Nationale Studenten Enquête 2026" in v for v in uit["voorbehouden"])
    assert any("collegejaar 2025-2026" in v for v in uit["voorbehouden"])
    assert uit["koppelen"] == studiekeuze.KOPPELEN


def test_een_afkorting_en_een_brin_code_geven_dezelfde_instelling():
    assert _uit(instelling="HU", opleiding="30020")["rijen"] == _uit(instelling="25dw", opleiding="30020")["rijen"]


def test_een_niet_bekostigde_hogeschool_staat_alleen_in_de_export():
    uit = _uit(instelling="Proefhogeschool", opleiding="ICT")
    assert uit["instelling"]["brin"] == "99XX" and uit["rijen"][0]["plaats"] == "'s-Hertogenbosch"


def test_een_oordeel_op_weinig_respondenten_markeert_de_code_als_onzeker():
    (onzeker,) = _uit(instelling="Proefhogeschool", opleiding="ICT")["rijen"]  # 15 respondenten
    assert onzeker["nse_onzeker"] is True
    (zeker,) = _uit(instelling="HU", opleiding="ICT", vorm="voltijd")["rijen"]  # 120 respondenten
    assert "nse_onzeker" not in zeker
    assert "nse_onzeker" not in store.get(_uit(instelling="Proefhogeschool", opleiding="ICT")["data_key"]).columns


def test_studie_met_arbeidsmarkt():
    uit = _uit(weergave="studie", opleiding="ICT")
    assert [(r["vorm"], r["salaris_mediaan_bruto_maand"]) for r in uit["rijen"]] == [
        ("voltijd", 3295),
        ("deeltijd", None),
    ]
    assert studiekeuze.ARBEIDSMARKT in uit["voorbehouden"]


def test_toelating_per_opleiding_met_vaste_zin():
    uit = _uit(weergave="toelating", opleiding="Psychologie")
    (rij,) = uit["rijen"]
    assert (rij["havo"], rij["vwo"]) == ("Niet toelaatbaar", "Vwo met profiel EM, CM, NG, NT.")
    assert uit["voorbehouden"] == [studiekeuze.TOELATING]
    assert "vraagt een opleiding" in studiekeuze.get_studiekeuze(weergave="toelating")


def test_wat_een_andere_bron_leidend_heeft_staat_er_niet_in():
    """Afspraken #878: aantallen studenten (DUO), collegegeld, accreditatie en de aansluiting studie-baan (ROA)."""
    uit = _uit(instelling="HU", opleiding="ICT", vorm="voltijd")
    assert not {"studenten", "eerstejaars", "collegegeld_wettelijk", "accreditatiebesluit"} & set(uit["rijen"][0])
    assert studiekeuze.ANDERE_BRON in uit["voorbehouden"]
    studie = _uit(weergave="studie", opleiding="ICT")["rijen"][0]
    assert "aansluiting_studie_baan" not in studie and studie["roa_opleidingstype"] == "hbo - ict"
    assert "kan niet" in studiekeuze.get_studiekeuze(opleiding="ICT", sorteer="studenten")


def test_numerus_fixus_en_doorstroom():
    nf = _uit(weergave="numerus_fixus", instelling="21PB")
    assert [(r["studiejaar"], r["capaciteit"]) for r in nf["rijen"]] == [(2026, 60), (2027, 71)]
    mbo = _uit(weergave="doorstroom_mbo_hbo", mbo_opleiding="verpleeg")
    assert [r["hbo_studie"] for r in mbo["rijen"]] == ["Opleiding tot Verpleegkundige", "ICT"]
    assert studiekeuze.DOORSTROOM_MBO in mbo["voorbehouden"]
    bm = _uit(weergave="doorstroom_bachelor_master", opleiding="Psychologie")  # alleen bachelors
    assert [r["master"] for r in bm["rijen"]] == ["Psychology", "Psychologie"]


def test_een_rangorde_krijgt_haar_voorbehoud():
    uit = _uit(opleiding="ICT", vorm="voltijd", sorteer="oordeel")
    assert [r["instelling"] for r in uit["rijen"]] == ["Proefhogeschool Particulier", "Hogeschool Utrecht"]
    assert studiekeuze.RANGORDE in uit["voorbehouden"]
    assert studiekeuze.RANGORDE not in _uit(opleiding="ICT")["voorbehouden"]


def test_veel_rijen_worden_afgekapt_met_de_hele_tabel_in_de_store(monkeypatch):
    monkeypatch.setattr(studiekeuze, "MAX_RIJEN", 1)
    uit = _uit(opleiding="ICT")
    assert uit["aantal_rijen"] == 3 and len(uit["rijen"]) == 1 and "afgekapt" in uit
    assert "nse_docenten" not in uit["rijen"][0]
    assert len(store.get(uit["data_key"])) == 3


# --- weigeringen en meldingen ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "verwacht"),
    [
        ({"instelling": "ROC Midden Nederland"}, "is een mbo-instelling"),
        ({"instelling": "mbo"}, "alleen opleidingen van hogescholen en universiteiten"),
        ({"soort_ho": "mbo", "opleiding": "ICT"}, "alleen opleidingen van hogescholen en universiteiten"),
        ({"instelling": "Universiteit Utrecht"}, "staat niet in de Studiekeuzedatabase"),
        ({"instelling": "12AB"}, "staat niet in de Studiekeuzedatabase"),
        ({"instelling": "Hogeschool"}, "Meer instellingen passen"),
        ({"instelling": "Nergenshogeschool"}, "Onbekende instelling"),
        ({}, "Geef een instelling, een opleiding of een plaats"),
        ({"weergave": "ranglijst"}, "bestaat niet"),
        ({"opleiding": "ICT", "sorteer": "prijs"}, "kan niet"),
        ({"opleiding": "ICT", "vorm": "avond"}, "vorm is"),
        ({"weergave": "studie"}, "vraagt een opleiding"),
        ({"weergave": "studie", "opleiding": "Psychologie"}, "Meer studies passen"),
        ({"weergave": "studie", "opleiding": "Sterrenkunde"}, "Geen studie"),
        ({"weergave": "doorstroom_mbo_hbo"}, "vraagt een mbo_opleiding"),
    ],
)
def test_een_vraag_die_niet_kan_geeft_een_vaste_melding_zonder_cijfers(args, verwacht):
    melding = studiekeuze.get_studiekeuze(**args)
    assert verwacht in melding
    with pytest.raises(ValueError):
        json.loads(melding)


def test_geen_rijen_is_een_melding_zonder_data_key():
    uit = _uit(instelling="21PB", opleiding="ICT")
    assert uit["rijen"] == [] and "data_key" not in uit and "Noem geen getal" in uit["melding"]


def test_zonder_sleutel_een_melding(monkeypatch):
    monkeypatch.undo()  # de echte haal_op: zonder sleutel geen request
    monkeypatch.setattr(config, "STUDIEKEUZEDATABASE_API_KEY", None)
    monkeypatch.delenv(skdb.SLEUTEL_ENV, raising=False)
    studiekeuze._export.cache_clear()
    assert "niet beschikbaar (geen sleutel)" in studiekeuze.get_studiekeuze(opleiding="ICT")


def test_een_geweigerde_sleutel_is_een_bronfout_zonder_de_sleutel(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(config, "STUDIEKEUZEDATABASE_API_KEY", "geheime-sleutel")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(401, text="Token is invalid"))
    studiekeuze._export.cache_clear()
    melding = studiekeuze.get_studiekeuze(opleiding="ICT")
    assert "weigert de sleutel (HTTP 401)" in melding and "geheime-sleutel" not in melding


# --- naden: bronregel, citaties, store, snippet ---------------------------------------------------------------------


def test_de_bronregel_noemt_versie_en_de_verplichte_zin_van_lcsk():
    stap = (TOOL_GET_STUDIEKEUZE, studiekeuze.get_studiekeuze(instelling="HU", opleiding="ICT"))
    # Versie en NSE-jaar (art. 4.2), de herkomst van het studieverloop (#878) en de verplichte zin met de link (art. 4.1).
    regel = (
        "Studiekeuzedatabase 26.6 (NSE 2026; studieverloop uit 1cijferHO 2025, bewerkt door LCSK), Landelijk Centrum "
        "Studiekeuze, export van 2026-11-06. Er is gebruik gemaakt van de data van Landelijk Centrum Studiekeuze."
    )
    assert bronnen_van([stap]) == [regel]
    assert bronlinks_van([stap]) == {regel: "https://lcsk.nl/over-ons/studiekeuzedata-raadplegen/"}


@pytest.mark.parametrize(
    ("args", "herkomst"),
    [
        ({"weergave": "studie", "opleiding": "ICT"}, "arbeidsmarkt uit CBS-microdata en de NAE/HBO-monitor"),
        ({"weergave": "toelating", "opleiding": "ICT"}, "vooropleidingseisen uit de regeling (RATHO)"),
        ({"weergave": "doorstroom_mbo_hbo", "mbo_opleiding": "verpleeg"}, "doorstroombestand mbo-hbo"),
    ],
)
def test_de_bronregel_noemt_de_oorspronkelijke_bron_van_de_weergave(args, herkomst):
    regel = _uit(**args)["bron"]["regel"]
    assert herkomst in regel and regel.endswith(skdb.VERPLICHTE_ZIN)


def test_elk_getal_is_een_citatie_met_instelling_opleiding_en_vorm():
    resultaat = studiekeuze.get_studiekeuze(instelling="HU", opleiding="ICT", vorm="voltijd")
    assert {"70", "45"} <= bewijs_getallen(resultaat)  # doorstroom jaar 2 en diplomarendement
    waarden = {w.maat: w for w in meetwaarden(resultaat, TOOL_GET_STUDIEKEUZE)}
    oordeel = waarden["nse_oordeel"]
    assert oordeel.selectie == ("Instelling: Hogeschool Utrecht", "Opleiding: ICT", "Vorm: voltijd", "Plaats: Utrecht")
    assert oordeel.data_key == json.loads(resultaat)["data_key"]
    assert oordeel.bron is not None and oordeel.bron.endswith(skdb.VERPLICHTE_ZIN)
    assert waarden["doorstroom_jaar2_pct"].eenheid == "%"
    assert "croho" not in waarden and "studiecode" not in waarden  # een code is geen maat


def test_de_tabel_staat_met_haar_laadaanroep_in_de_store():
    uit = _uit(instelling="Hogeschool Utrecht", opleiding="ICT")
    meta = store.meta(uit["data_key"])
    assert meta is not None
    assert (meta.bron, meta.dataset) == ("skdb", studiekeuze.DATASET)
    assert meta.laad == (TOOL_GET_STUDIEKEUZE, uit["selectie"])
    assert meta.peilmoment == f"versie 26.6; {skdb.VERPLICHTE_ZIN} ({skdb.DOCUMENTATIE})"
    assert meta.instellingen == ("25DW",)
    # De kop van een CSV-export noemt de bron met de verplichte zin.
    assert skdb.VERPLICHTE_ZIN in store.herkomst(uit["data_key"])[0]
    # Herladen met de laadaanroep geeft dezelfde rijen.
    assert _uit(**uit["selectie"])["rijen"] == uit["rijen"]


def _snippet_df(args: dict, monkeypatch):
    resultaat = studiekeuze.get_studiekeuze(**args)
    uit = json.loads(resultaat)
    code = snippet.generate(TOOL_GET_STUDIEKEUZE, uit["selectie"], resultaat)
    assert code is not None
    ruimte: dict = {}
    exec(compile(code, "<snippet>", "exec"), ruimte)  # skdb.haal_op staat op de proefexport (fixture)
    return code, ruimte["df"], uit


@pytest.mark.parametrize(
    "args",
    [
        {"instelling": "Hogeschool Utrecht", "opleiding": "ICT"},
        {"opleiding": "30020", "vorm": "voltijd", "sorteer": "oordeel"},
        {"instelling": "21PB", "alleen_numerus_fixus": True},
        {"weergave": "studie", "opleiding": "ICT"},
        {"weergave": "numerus_fixus", "instelling": "Universiteit Leiden"},
        {"weergave": "doorstroom_mbo_hbo", "mbo_opleiding": "verpleeg"},
        {"weergave": "doorstroom_bachelor_master", "opleiding": "56604"},
    ],
)
def test_de_snippet_geeft_dezelfde_tabel_als_de_app(args, monkeypatch):
    """Equivalentie (#945): de snippet roept dezelfde pakketfunctie aan met de keuze van de app (BRIN, code)."""
    code, df, uit = _snippet_df(args, monkeypatch)
    pd.testing.assert_frame_equal(df, store.get(uit["data_key"]))
    assert "STUDIEKEUZEDATABASE_API_KEY" in code and skdb.VERPLICHTE_ZIN in code
    assert "geheim" not in code
    if uit["selectie"].get("instelling"):
        assert f'brin="{uit["selectie"]["instelling"]}"' in code  # de BRIN van de app, niet de naam uit de vraag


def test_een_weigering_geeft_geen_snippet():
    melding = studiekeuze.get_studiekeuze(instelling="ROC Midden Nederland")
    assert snippet.generate(TOOL_GET_STUDIEKEUZE, {"instelling": "ROC Midden Nederland"}, melding) is None


# --- toolset, catalogus en omgeving ----------------------------------------------------------------------------------


def test_zonder_sleutel_staat_de_tool_niet_in_de_toolset():
    assert config.STUDIEKEUZEDATABASE_API_KEY is None
    assert SCHEMA_GET_STUDIEKEUZE not in TOOL_SCHEMAS
    assert tools.dispatch(TOOL_GET_STUDIEKEUZE, {})[0] == f"Onbekende tool: {TOOL_GET_STUDIEKEUZE}"
    assert not any(r.get("_skdb_id") for r in catalog._rio_duo_alles())


def test_met_sleutel_staat_de_tool_in_de_toolset_en_de_dispatch():
    """In een eigen proces: de sleutel wordt bij import gelezen."""
    code = (
        "import tools; from tools.schemas import TOOL_SCHEMAS, SCHEMA_GET_STUDIEKEUZE;"
        "assert SCHEMA_GET_STUDIEKEUZE in TOOL_SCHEMAS; assert 'get_studiekeuze' in tools._HANDLERS;"
        "assert 'get_studiekeuze' in tools.LABELS; print('ok')"
    )
    omgeving = {**os.environ, "STUDIEKEUZEDATABASE_API_KEY": "proefsleutel"}
    uit = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=omgeving, capture_output=True, text=True, timeout=120
    )
    assert uit.returncode == 0, uit.stderr[-2000:]
    assert uit.stdout.strip().endswith("ok")


def test_met_sleutel_vindt_de_catalogus_de_bron_als_via_tool(monkeypatch):
    monkeypatch.setattr(config, "STUDIEKEUZEDATABASE_API_KEY", "proefsleutel")
    for gecached in (catalog._rio_duo_alles, catalog._rio_duo, catalog.catalogus_digest):
        gecached.cache_clear()
    try:
        assert beschikbaarheid.bronnen()["studiekeuze"] is True
        assert beschikbaarheid.tool(TOOL_GET_STUDIEKEUZE) is True
        kandidaten = json.loads(catalog.search_catalog("tevredenheid studenten nse opleiding numerus fixus"))[
            "kandidaten"
        ]
        assert ("studiekeuzedatabase", "via_tool") in [(k["dataset_id"], k.get("status")) for k in kandidaten]
        details = json.loads(catalog.dataset_details("skdb:studiekeuzedatabase"))
        assert (details["status"], details["via_tool"]) == ("via_tool", TOOL_GET_STUDIEKEUZE)
        assert catalog.via_tool_aantallen()["LCSK"] == 1
    finally:
        monkeypatch.undo()
        for gecached in (catalog._rio_duo_alles, catalog._rio_duo, catalog.catalogus_digest):
            gecached.cache_clear()


def test_het_schema_past_op_de_handler():
    params = SCHEMA_GET_STUDIEKEUZE["function"]["parameters"]["properties"]
    assert set(params) <= set(inspect.signature(studiekeuze.get_studiekeuze).parameters)
    assert params["weergave"]["enum"] == list(studiekeuze.WEERGAVEN)
    assert params["sorteer"]["enum"] == list(skdb.SORTERINGEN)
    assert params["vorm"]["enum"] == list(skdb.VORMEN.values())


def test_de_sleutel_staat_op_test_en_playground_en_nergens_anders():
    def sleutel(omgeving: str) -> str | None:
        regels = (ROOT / "manifests" / omgeving / "values.yaml").read_text(encoding="utf-8").splitlines()
        for i, regel in enumerate(regels):
            if regel.strip() == "- name: STUDIEKEUZEDATABASE_API_KEY":
                return "\n".join(regels[i : i + 6])
        return None

    for omgeving in ("test", "playground"):
        blok = sleutel(omgeving)
        assert blok and "key: STUDIEKEUZEDATABASE_API_KEY" in blok and "optional: true" in blok
    assert sleutel("production") is None and sleutel("development") is None
