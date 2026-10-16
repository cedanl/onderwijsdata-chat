"""Een UWV- of ROA-resultaat is een dataset in de store (#577).

Het rapport van 8 oktober zei "geen vacaturegegevens geladen" terwijl de chat 40.512 UWV-vacatures
toonde: de arbeidsmarkttools gaven geen data_key en zetten niets in de store, dus voor het rapport
(build_dataset_context), het recept, de bronnenlijst, de citaties, de snippet en de export
bestonden ze niet. Nu staat de tabel achter elk resultaat in de store, met laadaanroep en
peildatum of versie in haar KeyMeta, en loopt alles mee dat op een data_key werkt.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent import manifest
from agent.bronvermelding import bronnen_van
from agent.citaties import citaties
from agent.dashboard import _build_recipe, _reload_call_from_key, _sources_from_recipe, build_dataset_context
from agent.figuurbron import figuurbron
from agent.meetwaarden import meetwaarden
from agent.session_data import record_data_key
from data import arbeidsmarkt
from tools import herlaad, snippet, store
from tools.arbeidsmarkt import ROA_ID, UWV_ID, get_roa_benchmark, get_uwv_vacatures
from tools.plot import create_plot
from tools.query import query_data

_UWV = pd.DataFrame(
    {
        "PEILDATUM": ["16-05-2023"] * 4,
        "PROVINCIE": ["Utrecht", "Utrecht", "Utrecht", "Gelderland"],
        "GEMEENTE": ["Utrecht", "Amersfoort", "Utrecht", "Arnhem"],
        "BEROEPENCLUSTER": ["Zorg en welzijn", "ICT", "ICT", "ICT"],
        "AANTAL": [900, 200, 100, 50],
    }
)
_ITA = "ITA toekomstige arbeidsmarktsituatie in 2030"


def _roa_rij(regio, niveau, onderwerp, perc=None, typering=None, thema=arbeidsmarkt._ROA_SIS):
    return {
        "regionaam": regio,
        "thema": thema,
        "aggregatieniveau": arbeidsmarkt._ROA_SECTOR if " - " in niveau else arbeidsmarkt._ROA_NIVEAU,
        "detailniveau": niveau,
        "onderwerp": onderwerp,
        "perc": perc,
        "aantal": None,
        "typering": typering,
        "versie": "v20251218",
    }


_ROA = pd.DataFrame(
    [
        _roa_rij("Nederland", "Mbo4", "werkloosheid", perc="3"),
        _roa_rij("Nederland", "Mbo4", _ITA, typering="redelijk", thema=arbeidsmarkt._ROA_PROGNOSE),
        _roa_rij("Midden-Utrecht", "Mbo4", _ITA, typering="goed", thema=arbeidsmarkt._ROA_PROGNOSE),
        _roa_rij("Nederland", "Mbo4 - techniek en ict", _ITA, typering="slecht", thema=arbeidsmarkt._ROA_PROGNOSE),
    ]
)
_TITELS = {UWV_ID: "UWV Open Match", ROA_ID: "AIS tot 2030"}
_UWV_CALL = {"name": "get_uwv_vacatures", "arguments": {"provincie": "utrecht", "sector": "GEZONDHEIDSZORG"}}


@pytest.fixture
def bronnen():
    with (
        patch.object(arbeidsmarkt, "_uwv", return_value=_UWV),
        patch.object(arbeidsmarkt, "_roa", return_value=_ROA),
        patch("tools.arbeidsmarkt.scope_blokkade", return_value=None),
        patch("agent.selectie.bron_titel", side_effect=lambda d: _TITELS.get(d, d)),
        patch("agent.dashboard.bron_titel", side_effect=lambda d: _TITELS.get(d, d)),
        patch("agent.figuurbron.bron_titel", side_effect=lambda d: _TITELS.get(d, d)),
    ):
        yield


# ── De tabel in de store ─────────────────────────────────────────────────────


def test_uwv_resultaat_is_een_tabel_in_de_store_met_een_data_key(bronnen):
    uit = json.loads(get_uwv_vacatures("Utrecht"))

    assert uit["data_key"] == "uwv:utrecht"
    tabel = store.get("uwv:utrecht")
    assert tabel.to_dict("records") == [
        {"PROVINCIE": "Utrecht", "BEROEPENCLUSTER": "Zorg en welzijn", "VACATURES": 900},
        {"PROVINCIE": "Utrecht", "BEROEPENCLUSTER": "ICT", "VACATURES": 300},
    ]
    known = store.meta("uwv:utrecht")
    assert known is not None
    assert (known.bron, known.dataset, known.volledig) == ("uwv", UWV_ID, True)
    assert known.laad == ("get_uwv_vacatures", {"provincie": "Utrecht"})
    assert known.peilmoment == "peildatum 2023-05-16"
    # De rest van het resultaat blijft zoals het was.
    assert uit["totaal_vacatures"] == 1200 and uit["peildatum"] == "2023-05-16"


def test_sector_en_spelling_delen_dezelfde_tabel(bronnen):
    # Een sector is een zicht op dezelfde clusters, geen andere selectie; de spelling van de bron wint.
    met_sector = json.loads(get_uwv_vacatures("utrecht", sector="GEZONDHEIDSZORG"))

    assert met_sector["data_key"] == "uwv:utrecht"
    assert met_sector["provincie"] == "Utrecht"
    known = store.meta("uwv:utrecht")
    assert known is not None and known.laad == ("get_uwv_vacatures", {"provincie": "Utrecht"})
    assert store.get("uwv:utrecht")["PROVINCIE"].unique().tolist() == ["Utrecht"]


def test_gemeente_krijgt_een_eigen_tabel(bronnen):
    uit = json.loads(get_uwv_vacatures("Utrecht", gemeente="amersfoort"))

    assert uit["data_key"] == "uwv:utrecht:amersfoort"
    assert store.get("uwv:utrecht:amersfoort").to_dict("records") == [
        {"PROVINCIE": "Utrecht", "GEMEENTE": "Amersfoort", "BEROEPENCLUSTER": "ICT", "VACATURES": 200}
    ]
    known = store.meta("uwv:utrecht:amersfoort")
    assert known is not None
    assert known.laad == ("get_uwv_vacatures", {"provincie": "Utrecht", "gemeente": "Amersfoort"})


def test_roa_resultaat_is_een_tabel_met_elk_cijfer_als_rij(bronnen):
    uit = json.loads(get_roa_benchmark(regio="midden-utrecht"))

    assert uit["data_key"] == "roa:midden-utrecht"
    tabel = store.get("roa:midden-utrecht")
    assert tabel.columns.tolist() == [
        "ONDERDEEL",
        "REGIO",
        "OPLEIDING",
        "INDICATOR",
        "PERCENTAGE",
        "AANTAL",
        "TYPERING",
    ]
    rijen = {(r["ONDERDEEL"], r["REGIO"], r["OPLEIDING"], r["INDICATOR"]): r for r in tabel.to_dict("records")}
    # Schoolverlaters zijn er alleen landelijk: die rij heet landelijk, de prognose regionaal.
    assert rijen[("Schoolverlaters (SIS 2024)", "Nederland", "Mbo4", "werkloosheid")]["PERCENTAGE"] == 3
    assert rijen[("Prognose tot 2030", "Midden-Utrecht", "Mbo4", _ITA)]["TYPERING"] == "goed"
    known = store.meta("roa:midden-utrecht")
    assert known is not None
    assert (known.bron, known.dataset, known.peilmoment) == ("roa", ROA_ID, "versie v20251218")
    assert known.laad == ("get_roa_benchmark", {"regio": "midden-utrecht"})


def test_roa_sector_en_provincie_in_de_key(bronnen):
    assert (
        json.loads(get_roa_benchmark(sector="Mbo4 - techniek en ict"))["data_key"]
        == "roa:nederland:mbo4-techniek-en-ict"
    )
    assert len(store.get("roa:nederland:mbo4-techniek-en-ict")) == 1


def test_query_en_plot_werken_op_de_tabel(bronnen):
    key = json.loads(get_uwv_vacatures("Utrecht"))["data_key"]

    selectie = json.loads(query_data(key, filters={"BEROEPENCLUSTER": "ICT"}))
    assert selectie["rijen"] == [{"PROVINCIE": "Utrecht", "BEROEPENCLUSTER": "ICT", "VACATURES": 300}]
    tekst, figuur = create_plot(data_key=key, chart_type="bar", x="BEROEPENCLUSTER", y="VACATURES", title="Vacatures")
    assert figuur is not None and "aangemaakt" in tekst
    assert figuur.layout.meta["herkomst"] == [f"bron: UWV, dataset {UWV_ID}"]


# ── Wat op een data_key werkt, loopt mee ─────────────────────────────────────


def test_het_rapport_ziet_de_vacaturetabel(bronnen):
    session: dict = {"username": None}
    resultaat = get_uwv_vacatures("Utrecht", sector="GEZONDHEIDSZORG")
    record_data_key(session, resultaat, _UWV_CALL)

    context = build_dataset_context(session)

    [dataset] = context["datasets"]
    assert dataset["data_key"] == "uwv:utrecht" and dataset["row_count"] == 2
    assert [c["naam"] for c in dataset["columns"]] == ["PROVINCIE", "BEROEPENCLUSTER", "VACATURES"]
    assert dataset["herkomst"] == [_UWV_CALL]


def test_bronnenlijst_van_rapport_en_dashboard_noemt_uwv_en_roa_met_peilmoment(bronnen):
    session: dict = {"username": None}
    record_data_key(
        session, get_uwv_vacatures("Utrecht"), {"name": "get_uwv_vacatures", "arguments": {"provincie": "Utrecht"}}
    )
    record_data_key(session, get_roa_benchmark(), {"name": "get_roa_benchmark", "arguments": {}})

    recept = _build_recipe(build_dataset_context(session)["datasets"])

    assert [c["name"] for c in recept] == ["get_uwv_vacatures", "get_roa_benchmark"]
    assert _sources_from_recipe(recept) == [
        "UWV — UWV Open Match (uwv-open-match-data), peildatum 2023-05-16",
        "ROA — AIS tot 2030 (ais2030), versie v20251218",
    ]


def test_citatie_wijst_naar_de_tabel_met_bron_en_peildatum(bronnen):
    resultaat = get_uwv_vacatures("Utrecht")

    [totaal] = citaties("Utrecht telt 1.200 vacatures.", [("get_uwv_vacatures", resultaat)])
    cluster = next(w for w in meetwaarden(resultaat) if "Beroepencluster: Zorg en welzijn" in w.selectie)

    assert totaal["vastgesteld"] and totaal["data_key"] == "uwv:utrecht"
    assert totaal["bron"] == "UWV · UWV Open Match, peildatum 2023-05-16"
    assert cluster.data_key == "uwv:utrecht" and cluster.bron is None
    assert cluster.selectie == ("Provincie: Utrecht", "Beroepencluster: Zorg en welzijn")


def test_bronnenblok_onder_het_antwoord_noemt_de_tabel_een_keer(bronnen):
    resultaat = get_uwv_vacatures("Utrecht")
    selectie = query_data("uwv:utrecht", filters={"BEROEPENCLUSTER": "ICT"})

    assert bronnen_van([("get_uwv_vacatures", resultaat), ("query_data", selectie)]) == [
        "UWV · UWV Open Match, peildatum 2023-05-16 (uwv-open-match-data)"
    ]


def test_recept_haalt_de_tabel_terug_na_een_herstart(bronnen):
    key = json.loads(get_uwv_vacatures("Utrecht"))["data_key"]
    recept = herlaad.recept(key, {"name": "get_uwv_vacatures", "arguments": {"provincie": "utrecht"}})
    assert recept == {"laad": ["get_uwv_vacatures", {"provincie": "Utrecht"}]}
    voor = store.get(key)
    store.clear()

    uitkomst = herlaad.herlaad(key, recept)

    assert uitkomst.gelukt and uitkomst.herladen
    pd.testing.assert_frame_equal(store.get(key), voor)
    known = store.meta(key)
    assert known is not None and known.peilmoment == "peildatum 2023-05-16"


def test_snippet_laadt_de_tabel_zonder_store(bronnen):
    uwv = json.loads(get_uwv_vacatures("Utrecht", gemeente="Amersfoort"))["data_key"]
    roa = json.loads(get_roa_benchmark(sector="Mbo4 - techniek en ict", regio="midden-utrecht"))["data_key"]

    regels_uwv = snippet._laadregels(uwv)
    regels_roa = snippet._laadregels(roa)

    assert "from riodata import uwv" in regels_uwv
    assert 'df = df[df["PROVINCIE"].str.lower() == "utrecht"]' in regels_uwv
    assert 'df = df[df["GEMEENTE"].str.lower() == "amersfoort"]' in regels_uwv
    assert 'df = df.rename(columns={"AANTAL": "VACATURES"})' in regels_uwv
    assert "from riodata import roa" in regels_roa
    assert 'df = df[df["detailniveau"] == "Mbo4 - techniek en ict"]' in regels_roa
    assert any("midden-utrecht" in r for r in regels_roa)


def test_manifest_en_bronregel_noemen_het_peilmoment(bronnen):
    key = json.loads(get_uwv_vacatures("Utrecht"))["data_key"]

    assert manifest._data_as_of([key]) == [{"bron": "uwv", "dataset": UWV_ID, "peilmoment": "peildatum 2023-05-16"}]
    with patch(
        "agent.figuurbron.documentatie_url", return_value="https://data.overheid.nl/dataset/uwv-open-match-data"
    ):
        bron = figuurbron(key) or {}
    assert bron["tekst"] == "UWV · UWV Open Match (uwv-open-match-data), peildatum 2023-05-16"


def test_een_key_zonder_herkomst_laadt_niet_blind_opnieuw():
    # Een arbeidsmarktkey draagt zijn aanroep in zijn herkomst en recept, niet omkeerbaar in zijn naam.
    assert _reload_call_from_key("uwv:utrecht") is None
    assert snippet._bron_van_key("roa:nederland") is None


def test_een_ouder_resultaat_zonder_data_key_houdt_de_bron_in_woorden():
    oud = json.dumps(
        {
            "bron": "UWV Open Match",
            "dataset": UWV_ID,
            "peildatum": "2023-05-16",
            "provincie": "Utrecht",
            "totaal_vacatures": 1200,
        }
    )

    [citatie] = citaties("Er zijn 1.200 vacatures.", [("get_uwv_vacatures", oud)])

    assert citatie["bron"] == "UWV Open Match, 2023-05-16" and "data_key" not in citatie
    assert bronnen_van([("get_uwv_vacatures", oud)]) == ["UWV Open Match, 2023-05-16"]
