"""De actuele vacatures in de chat (#1226, #1227): get_vacatures (CBS 83599NED) en get_ontstane_vacatures (85081NED).

Alles uit de opgenomen OData-antwoorden (tests/fixtures/cbs/83599NED_provincies.json en 85081NED_beroepen.json), zonder
netwerk. Gelderland, in duizendtallen: alle economische activiteiten 41,6 (2025 kw4), 42,9, 43,9 en 42,6 (2026 kw3);
Q Gezondheids- en welzijnszorg 8,4, 8,7, 8,9 en 8,6. Ontstane vacatures, 08 ICT beroepen: 61,0 (2018) t/m 64,3 (2025).
Elk kwartaal vanaf 2022 en elk jaar 2018-2025 is voorlopig.

Een resultaat is een dataset zoals UWV en ROA (#577): de tabel staat in de store met laadaanroep en peilmoment, zodat
bronregel, citaties, snippet, herlaad en CSV-export meelopen. Hier staan die naden per tool.
"""

import json

import pandas as pd
import pytest

from agent import datasetcontext
from agent.bronvermelding import bronnen_van
from agent.meetwaarden import meetwaarden
from tests import cbs_83599ned
from tests.zoekuitkomst import treffers
from tools import catalog, csv_export, herlaad, snippet, store
from tools.schemas import TOOL_GET_ONTSTANE_VACATURES, TOOL_GET_VACATURES
from tools.vacatures import get_ontstane_vacatures, get_vacatures

pytestmark = pytest.mark.usefixtures("cbs_ontstane_vacatures")


def _rij(uit: dict, sectie: str, maat: str) -> dict:
    return next(r for r in uit["rijen"] if r["SECTIE"].startswith(sectie) and r["MAAT"] == maat)


# --- get_vacatures: openstaande vacatures per provincie ------------------------------------------------------------


def test_vacatures_in_gelderland_noemen_kwartaal_gemiddelde_status_en_bron():
    uit = json.loads(get_vacatures("Gelderland"))

    assert (uit["dataset"], uit["provincie"], uit["sectie"]) == (
        "83599NED",
        "Gelderland",
        "A-U Alle economische activiteiten",
    )
    assert uit["laatste_kwartaal"]["periode"] == "2026 3e kwartaal"
    assert (uit["laatste_kwartaal"]["vacatures"], uit["laatste_kwartaal"]["status"]) == (42_600, "voorlopig")
    assert uit["gemiddelde"]["periode"] == "2025 4e kwartaal t/m 2026 3e kwartaal"
    assert uit["gemiddelde"]["vacatures"] == round((41.6 + 42.9 + 43.9 + 42.6) / 4 * 1000)
    assert uit["gemiddelde"]["kwartalen"] == 4 and uit["gemiddelde"]["voorlopig"] is True
    assert uit["bron"] == {
        "naam": "CBS",
        "titel": "Openstaande vacatures; SBI 2008, regio",
        "dataset": "83599NED",
        "link": "https://opendata.cbs.nl/#/CBS/nl/dataset/83599NED/table",
        "licentie": "CC BY 4.0",
    }
    # Het totaal en de 19 secties A t/m S, elk met het laatste kwartaal en het gemiddelde.
    assert len(uit["rijen"]) == 2 * 20
    zorg = _rij(uit, "Q ", "laatste kwartaal")
    assert (zorg["VACATURES"], zorg["Perioden"], zorg["Periodestatus"]) == (8_600, "2026 3e kwartaal", "Voorlopig")


@pytest.mark.parametrize("sectie", ["Q", "q", "Gezondheids- en welzijnszorg", "Q Gezondheids- en welzijnszorg"])
def test_een_sectie_als_letter_of_naam(sectie):
    uit = json.loads(get_vacatures("Gelderland", sectie=sectie))

    assert uit["sectie"] == "Q Gezondheids- en welzijnszorg"
    assert uit["laatste_kwartaal"]["vacatures"] == 8_600
    assert uit["gemiddelde"]["vacatures"] == round((8.4 + 8.7 + 8.9 + 8.6) / 4 * 1000)
    # Het totaal staat erbij, zodat de sectie een deel van iets is.
    assert [r["SECTIE"][:2] for r in uit["rijen"]] == ["A-", "A-", "Q ", "Q "]
    assert uit["data_key"] == "cbs:83599NED:vacatures:gelderland:q"


def test_een_onbekende_sectie_noemt_de_secties():
    uit = get_vacatures("Gelderland", sectie="Ruimtevaart")
    assert uit.startswith("SBI-sectie 'Ruimtevaart' is onbekend") and "Q Gezondheids- en welzijnszorg" in uit


def test_een_lege_cel_is_geen_gegevens_geen_nul(monkeypatch):
    from tests import cbs_85081ned

    def zonder_zorg(bron):
        zorg = next(s["Key"] for s in bron["BedrijfstakkenBranchesSBI2008"] if s["Title"].startswith("Q "))
        for r in bron["TypedDataSet"]:
            if r["RegioS"].strip() == "PV25" and r["BedrijfstakkenBranchesSBI2008"] == zorg:
                r["OpenstaandeVacatures_1"] = None

    cbs_83599ned.zet_klaar(monkeypatch, zonder_zorg)
    cbs_85081ned.zet_klaar(monkeypatch)  # weer na de opname van 83599NED, zoals de fixture
    uit = json.loads(get_vacatures("Gelderland", sectie="Q"))

    assert uit["laatste_kwartaal"]["vacatures"] is None
    assert uit["laatste_kwartaal"]["status"] == "geen gegevens"
    assert _rij(uit, "Q ", "laatste kwartaal")["VACATURES"] is None
    assert pd.isna(store.get(uit["data_key"])["VACATURES"].iloc[2])  # leeg, geen 0
    assert "geen gegevens" in uit["geen_gegevens"]


# --- plaatsniveau: alleen provincie (#1226, criterium 5) ------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [{"gemeente": "Arnhem"}, {"provincie": "Arnhem"}, {"provincie": "Gelderland", "gemeente": "Arnhem"}],
)
def test_een_gemeente_krijgt_de_provincie_waarin_ze_ligt(args):
    uit = json.loads(get_vacatures(**args))

    assert uit["provincie"] == "Gelderland"
    assert "gaan tot provincie" in uit["plaatsniveau"]
    assert "Gelderland" in uit["plaatsniveau"] and "Arnhem" in uit["plaatsniveau"]


def test_een_woonplaats_krijgt_de_provincie_van_haar_gemeente():
    uit = json.loads(get_vacatures(gemeente="Doorwerth"))  # een woonplaats in de gemeente Renkum
    assert uit["provincie"] == "Gelderland" and "Doorwerth ligt in Gelderland" in uit["plaatsniveau"]


def test_een_plaats_in_twee_provincies_laat_de_keuze_aan_de_gebruiker():
    # Velp ligt in Rheden (Gelderland) en in Land van Cuijk (Noord-Brabant): de app kiest niet.
    uit = get_vacatures(gemeente="Velp")
    assert "gaan tot provincie" in uit and "Gelderland of Noord-Brabant: kies een provincie" in uit


def test_een_arbeidsmarktregio_krijgt_de_provincie_waar_ze_grotendeels_ligt():
    uit = json.loads(get_vacatures(regio="Rijk van Nijmegen"))

    assert uit["provincie"] == "Gelderland"
    assert "Arbeidsmarktregio Rijk van Nijmegen ligt grotendeels in Gelderland (ook in Limburg)" in uit["plaatsniveau"]
    assert "niet voor arbeidsmarktregio Rijk van Nijmegen" in uit["plaatsniveau"]


@pytest.mark.parametrize("args", [{"provincie": "Atlantis"}, {"gemeente": "Atlantis"}, {}])
def test_een_onbekende_plaats_biedt_de_provincies_aan(args):
    uit = get_vacatures(**args)

    assert "gaan tot provincie" in uit
    assert "Gelderland" in uit and "Fryslân" in uit  # de keuzelijst van 83599NED
    with pytest.raises(ValueError):
        json.loads(uit)


# --- de dataset: store, bronregel, citaties, CSV, herlaad, snippet ---------------------------------------------------


def test_de_tabel_staat_in_de_store_met_laadaanroep_en_peilmoment():
    uit = json.loads(get_vacatures("gelderland", sectie="Q"))
    known = store.meta(uit["data_key"])

    assert known is not None
    assert (known.bron, known.dataset, known.periodekolom) == ("cbs", "83599NED", "Perioden")
    assert known.laad == (TOOL_GET_VACATURES, {"provincie": "Gelderland", "sectie": "Q"})
    assert known.peilmoment == "laatste kwartaal 2026 3e kwartaal"
    tabel = store.get(uit["data_key"])
    assert list(tabel.columns) == ["PROVINCIE", "SECTIE", "MAAT", "Perioden", "Periodestatus", "VACATURES"]
    assert tabel.to_dict("records") == uit["rijen"]


def test_de_bronregel_noemt_tabel_kwartaal_en_voorlopig():
    resultaat = get_vacatures("Gelderland")
    (regel,) = bronnen_van([(TOOL_GET_VACATURES, resultaat)])

    assert regel.startswith(
        "CBS · Openstaande vacatures; SBI 2008, regio, laatste kwartaal 2026 3e kwartaal (83599NED)"
    )
    assert "voorlopig" in regel


def test_de_citaties_wijzen_de_rij_aan():
    resultaat = get_vacatures("Gelderland", sectie="Q")
    waarden = meetwaarden(resultaat, TOOL_GET_VACATURES)

    zorg = next(w for w in waarden if "8600" in w.cijfers)
    assert zorg.data_key == json.loads(resultaat)["data_key"] and zorg.rij == 2
    assert "Sectie: Q Gezondheids- en welzijnszorg" in zorg.selectie


def test_de_csv_export_is_de_tabel_van_het_antwoord():
    resultaat = get_vacatures("Gelderland")
    assert csv_export.export_key(TOOL_GET_VACATURES, resultaat) == json.loads(resultaat)["data_key"]


def test_het_recept_laadt_dezelfde_tabel_opnieuw():
    uit = json.loads(get_vacatures("Gelderland", sectie="Q"))
    key = uit["data_key"]
    recept = herlaad.recept(key, {"name": TOOL_GET_VACATURES, "arguments": {"provincie": "Gelderland", "sectie": "Q"}})
    assert recept == {"laad": [TOOL_GET_VACATURES, {"provincie": "Gelderland", "sectie": "Q"}]}

    voor = store.get(key).copy()
    store.clear()
    assert herlaad.herlaad(key, recept).gelukt
    pd.testing.assert_frame_equal(store.get(key), voor)


def _snippet_df(tool: str, args: dict) -> tuple[str, pd.DataFrame, dict]:
    resultaat = {TOOL_GET_VACATURES: get_vacatures, TOOL_GET_ONTSTANE_VACATURES: get_ontstane_vacatures}[tool](**args)
    code = snippet.generate(tool, args, resultaat)
    assert code is not None
    ruimte: dict = {}
    exec(compile(code, "<snippet>", "exec"), ruimte)  # de CBS-client staat op de opname (fixture)
    return code, ruimte["df"], json.loads(resultaat)


@pytest.mark.parametrize(
    "args", [{"provincie": "Gelderland"}, {"provincie": "Fryslân", "sectie": "P"}, {"gemeente": "Arnhem"}]
)
def test_de_snippet_geeft_dezelfde_tabel_als_de_app(args):
    """Equivalentie (#945): de snippet haalt 83599NED met de CBS-client op en rekent zoals data/vacatures_cbs.py."""
    code, df, uit = _snippet_df(TOOL_GET_VACATURES, args)
    pd.testing.assert_frame_equal(df, store.get(uit["data_key"]))
    assert "from onderwijsbronnen.cbs import client" in code and "CC BY 4.0" in code


def test_een_melding_geeft_geen_tabel_en_geen_snippet():
    melding = get_vacatures("Atlantis")
    assert snippet.generate(TOOL_GET_VACATURES, {"provincie": "Atlantis"}, melding) is None


def test_de_bronnenlijst_van_het_rapport_noemt_de_tabel():
    recipe = [{"name": TOOL_GET_VACATURES, "arguments": {"provincie": "Gelderland"}}]
    (bron,) = datasetcontext.sources_from_recipe(recipe)
    assert bron == "CBS — Openstaande vacatures; SBI 2008, regio (83599NED), laatste kwartaal 2026 3e kwartaal"


# --- get_ontstane_vacatures: per beroep, landelijk (#1227) ----------------------------------------------------------


def _reeks(uit: dict, beroep: str) -> dict:
    return next(r for r in uit["reeksen"] if r["beroep"].startswith(beroep))


def test_ontstane_vacatures_per_segment_met_jaren_status_en_bron():
    uit = json.loads(get_ontstane_vacatures())

    assert (uit["dataset"], uit["niveau"]) == ("85081NED", "segment")
    assert [j["jaar"] for j in uit["jaren"]] == [str(j) for j in range(2018, 2026)]
    assert {j["status"] for j in uit["jaren"]} == {"voorlopig"}
    assert uit["bron"]["licentie"] == "CC BY 4.0" and uit["bron"]["link"].endswith("/85081NED/table")
    assert "landelijk" in uit["landelijk"].lower()
    assert "x 1 000" in uit["telling"]  # de eenheid uit de metadata, niet geraden
    assert uit["reeksen"][0]["beroep"] == "Totaal"
    assert _reeks(uit, "Totaal")["per_jaar"]["2025"] == 1_417_000
    assert {r["niveau"] for r in uit["reeksen"][1:]} == {"segment"}
    docenten = _reeks(uit, "011 ")
    assert docenten["klasse"] == "01 Pedagogische beroepen"


def test_ontstane_vacatures_per_klasse():
    uit = json.loads(get_ontstane_vacatures(niveau="klasse"))
    assert [r["beroep"][:2] for r in uit["reeksen"][1:]] == [
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "10",
        "11",
        "12",
    ]
    assert _reeks(uit, "08 ")["per_jaar"]["2025"] == 64_300


def test_een_klasse_geeft_ook_haar_segmenten():
    uit = json.loads(get_ontstane_vacatures(beroep="ICT beroepen"))

    assert uit["beroep"] == "08 ICT beroepen"
    assert [r["beroep"][:3] for r in uit["reeksen"]] == ["Tot", "08 ", "081", "082"]
    assert _reeks(uit, "08 ")["per_jaar"] == {
        "2018": 61_000,
        "2019": 69_500,
        "2020": 65_900,
        "2021": 87_400,
        "2022": 89_700,
        "2023": 77_500,
        "2024": 66_100,
        "2025": 64_300,
    }
    alleen_klasse = json.loads(get_ontstane_vacatures(beroep="08", niveau="klasse"))
    assert [r["beroep"][:3] for r in alleen_klasse["reeksen"]] == ["Tot", "08 "]


def test_een_lege_cel_is_null_geen_nul():
    uit = json.loads(get_ontstane_vacatures(beroep="013"))
    assert set(_reeks(uit, "013 ")["per_jaar"].values()) == {None}
    assert store.get(uit["data_key"])["ONTSTANE_VACATURES"].iloc[8:].isna().all()


@pytest.mark.parametrize(
    ("args", "begin"),
    [
        ({"beroep": "Astronauten"}, "Beroep 'Astronauten' staat niet"),
        ({"niveau": "sector"}, "Niveau 'sector' is onbekend"),
    ],
)
def test_een_onbekend_beroep_of_niveau_is_een_melding(args, begin):
    assert get_ontstane_vacatures(**args).startswith(begin)


def test_de_ontstane_vacatures_zijn_een_dataset():
    uit = json.loads(get_ontstane_vacatures(beroep="08"))
    known = store.meta(uit["data_key"])

    assert uit["data_key"] == "cbs:85081NED:ontstaan:segment:08"
    assert known is not None and known.laad == (TOOL_GET_ONTSTANE_VACATURES, {"niveau": "segment", "beroep": "08"})
    assert known.peilmoment == "jaren 2018 t/m 2025"
    tabel = store.get(uit["data_key"])
    assert list(tabel.columns) == ["BEROEP", "NIVEAU", "KLASSE", "Perioden", "Periodestatus", "ONTSTANE_VACATURES"]
    assert len(tabel) == 4 * 8
    (regel,) = bronnen_van([(TOOL_GET_ONTSTANE_VACATURES, json.dumps(uit))])
    assert "(85081NED)" in regel and "voorlopig" in regel
    assert csv_export.export_key(TOOL_GET_ONTSTANE_VACATURES, json.dumps(uit)) == uit["data_key"]


def test_de_citaties_van_de_ontstane_vacatures_wijzen_beroep_jaar_en_rij_aan():
    resultaat = get_ontstane_vacatures(beroep="08")
    waarden = meetwaarden(resultaat, TOOL_GET_ONTSTANE_VACATURES)
    ict = next(w for w in waarden if "64300" in w.cijfers)

    assert ict.selectie == ("Beroep: 08 ICT beroepen", "Jaar: 2025")
    assert ict.data_key is not None
    tabel = store.get(ict.data_key)
    assert ict.rij is not None and tabel.iloc[ict.rij]["ONTSTANE_VACATURES"] == 64_300


@pytest.mark.parametrize(
    "args", [{}, {"niveau": "klasse"}, {"beroep": "10"}, {"beroep": "072"}, {"beroep": "08", "niveau": "klasse"}]
)
def test_de_snippet_van_de_ontstane_vacatures_geeft_dezelfde_tabel(args):
    code, df, uit = _snippet_df(TOOL_GET_ONTSTANE_VACATURES, args)
    pd.testing.assert_frame_equal(df, store.get(uit["data_key"]))
    assert "client.properties(dataset)" in code  # de eenheid uit de metadata


def test_het_recept_van_de_ontstane_vacatures():
    uit = json.loads(get_ontstane_vacatures(beroep="ICT beroepen"))
    key = uit["data_key"]
    recept = herlaad.recept(key, {"name": TOOL_GET_ONTSTANE_VACATURES, "arguments": {"beroep": "ICT beroepen"}})
    assert recept == {"laad": [TOOL_GET_ONTSTANE_VACATURES, {"niveau": "segment", "beroep": "08"}]}
    voor = store.get(key).copy()
    store.clear()
    assert herlaad.herlaad(key, recept).gelukt
    pd.testing.assert_frame_equal(store.get(key), voor)


# --- catalogus en scope ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dataset", "tool"), [("83599NED", TOOL_GET_VACATURES), ("85081NED", TOOL_GET_ONTSTANE_VACATURES)]
)
def test_de_catalogus_wijst_naar_de_eigen_tool(dataset, tool):
    assert catalog.eigen_tool(dataset) == tool and catalog.ophaaltool(dataset) == tool
    assert catalog.scope_blokkade(dataset) is None  # de arbeidsmarktkant van het chatprofiel
    details = json.loads(catalog.dataset_details(dataset))
    assert details["via_tool"] == tool and tool in details["melding"]


def test_search_catalog_verwijst_naar_get_ontstane_vacatures():
    hit = next(
        h
        for h in treffers(catalog.search_catalog("ontstane vacatures beroep", top_n=15))
        if h.get("dataset_id") == "85081NED"
    )
    assert hit["via_tool"] == TOOL_GET_ONTSTANE_VACATURES


def test_search_catalog_verwijst_naar_get_vacatures():
    hit = next(
        h
        for h in treffers(catalog.search_catalog("openstaande vacatures provincie", top_n=15))
        if h.get("dataset_id") == "83599NED"
    )
    assert hit["via_tool"] == TOOL_GET_VACATURES
